"""
voz_civica/orchestrator.py

Loop central que liga as camadas: fonte de áudio -> VAD -> transcrição ->
resposta (LLM local) -> log (JSON + SQLite) -> terminal/UI. TTS (Estágio 5)
ainda não existe — a resposta só é impressa, ainda não falada.
"""

import hashlib
import uuid
from datetime import datetime, timezone

import numpy as np
import soundfile as sf
from rich.console import Console

from voz_civica.audio import playback
from voz_civica.audio.sources.base import AudioSource
from voz_civica.audio.vad import SileroVAD, VadState
from voz_civica.config import DATA_ROOT, settings
from voz_civica.respond.base import ResponderBackend
from voz_civica.respond.extractor import RelatoExtractor
from voz_civica.session import database
from voz_civica.session.collector import SessionCollector
from voz_civica.stt.transcriber import Transcriber
from voz_civica.tts.synthesizer import PiperSynthesizer
from voz_civica.ui.state import SharedUiState

console = Console()

RAW_AUDIO_ROOT = DATA_ROOT / "raw_audio"


def _sha256_of(samples: np.ndarray) -> str:
    return hashlib.sha256(samples.tobytes()).hexdigest()


def _save_and_log_turn(
    samples: np.ndarray,
    samplerate: int,
    duration_s: float,
    source_kind: str,
    transcript_text: str,
    language: str,
    collector: SessionCollector,
    reply_text: str | None = None,
) -> str:
    """Persiste o áudio, o JSON de sessão e o registro no SQLite de um turno. Retorna o session_id."""
    session_id = uuid.uuid4().hex[:12]
    captured_at = datetime.now(tz=timezone.utc).isoformat()

    RAW_AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
    audio_path = RAW_AUDIO_ROOT / f"{session_id}.wav"
    sf.write(audio_path, samples, samplerate)

    audio_sha256 = _sha256_of(samples)

    payload = {
        "_meta": {
            "session_id": session_id,
            "captured_at": captured_at,
            "duration_s": duration_s,
            "samplerate": samplerate,
            "source_kind": source_kind,
            "audio_sha256": audio_sha256,
            "model_name": settings.whisper_model_size,
            "schema_version": "1.0",
        },
        "audio_path": str(audio_path),
        "transcript": {"text": transcript_text, "language": language},
        "reply": {"text": reply_text} if reply_text is not None else None,
    }

    collector.save(session_id=session_id, payload=payload)

    database.upsert_session(
        session_id=session_id,
        audio_sha256=audio_sha256,
        captured_at=captured_at,
        duration_s=duration_s,
        samplerate=samplerate,
        source_kind=source_kind,
        audio_path=str(audio_path),
        transcript_text=transcript_text,
        language=language,
        model_name=settings.whisper_model_size,
        raw_json=str(payload),
        reply_text=reply_text,
    )
    database.log_capture_run(session_id=session_id, started_at=captured_at, status="ok")

    return session_id


def listen_and_transcribe(
    source: AudioSource,
    ui_state: SharedUiState | None = None,
    responder: ResponderBackend | None = None,
    synthesizer: PiperSynthesizer | None = None,
    extractor: RelatoExtractor | None = None,
) -> None:
    """
    Escuta continuamente `source`, transcreve cada fala detectada pelo VAD,
    opcionalmente gera uma resposta (Estágio 4, `responder`) e a fala em voz
    alta (Estágio 5, `synthesizer`), registra cada turno (áudio + JSON +
    SQLite) e imprime tudo no terminal. Roda até ser interrompido (Ctrl+C)
    ou até a fonte esgotar (no caso de um arquivo).

    `ui_state`, se informado (Estágio 3+), recebe amplitude real a cada
    frame e as transições de estado — incluindo "thinking" real (tempo
    genuíno de espera do LLM) e "speaking_ai" real (tempo genuíno da
    reprodução) quando `responder`/`synthesizer` estão presentes.

    Anti-feedback (Estágio 5): antes e depois de tocar a resposta, o áudio
    pendente na fonte é descartado (`source.drain_pending()`) — sem isso, o
    microfone escuta a própria IA falando e dispara uma nova transcrição.

    `extractor`, se informado, roda a cada turno numa chamada ISOLADA da que
    gera `reply_text`. O que ela extrai (tipo de relato, tema, descrição,
    local, posição) nunca entra em `conversation_history` como fato gravado
    — em vez disso, o estado atual (o que falta perguntar, ou o resumo pra
    confirmar) é passado como `extra_instructions` pro `responder`, só pra
    ele saber o que fazer NESSA conversa. A IA nunca recebe de volta relato
    de OUTRA conversa — só a dela mesma, enquanto ela ainda está rolando.

    Fluxo de coleta: se falta campo, a IA pergunta um por vez. Quando todos
    os campos obrigatórios estão completos, ela lê um resumo e pergunta se
    pode salvar — só quando o cidadão confirma
    (`extractor.check_confirmation`) é que `relatos.confirmado` vira 1 no
    banco.

    Limitação conhecida: `conversation_history`/`conversation_id` duram até
    o processo reiniciar — hoje é 1 pessoa por execução; separar por pessoa
    dentro de uma sessão longa (pro futuro quiosque) ainda não existe.
    """
    database.init_db()
    collector = SessionCollector()
    vad = SileroVAD()
    transcriber = Transcriber()
    conversation_history: list[dict] = []
    conversation_id = uuid.uuid4().hex[:12]
    awaiting_confirmation = False
    relato_confirmado = False

    console.print("[bold cyan]voz-civica[/bold cyan] — escutando... (Ctrl+C pra sair)")

    last_state = VadState.NOT_SPEAKING
    for frame, prob, state, utterance in vad.process_stream(source.stream_frames()):
        if ui_state is not None:
            amplitude = min(1.0, float(np.sqrt(np.mean(frame**2))) * 8.0)
            ui_state.update(
                state="speaking_user" if state == VadState.SPEAKING else "listening",
                amplitude=amplitude,
            )

        if state == VadState.SPEAKING and last_state == VadState.NOT_SPEAKING:
            console.print("[dim]... ouvindo[/dim]")
        last_state = state

        if utterance is not None:
            if utterance.duration_s < 0.3:
                # trecho curto demais pra ser fala real — provável falso-positivo do VAD
                database.log_capture_run(
                    session_id="", started_at=datetime.now(tz=timezone.utc).isoformat(),
                    status="discarded_noise", error_message=f"duration_s={utterance.duration_s:.2f}",
                )
                continue

            if ui_state is not None:
                ui_state.update(state="thinking", amplitude=0.0)

            result = transcriber.transcribe(utterance.samples)
            if not result.text.strip():
                console.print("[dim](fala detectada, mas transcrição vazia — ruído?)[/dim]")
                database.log_capture_run(
                    session_id="", started_at=datetime.now(tz=timezone.utc).isoformat(),
                    status="discarded_noise", error_message="transcricao_vazia",
                )
                if ui_state is not None:
                    ui_state.update(state="listening", amplitude=0.0)
                continue

            console.print(
                f"[green]>[/green] {result.text}  "
                f"[dim]({utterance.duration_s:.1f}s áudio, {result.duration_ms}ms transcrição)[/dim]"
            )

            reply_text: str | None = None
            if responder is not None:
                # Estado "thinking" já está ativo — o tempo real de espera do
                # LLM local (8-15s nessa CPU, ver plano) fica visível na UI.
                conversation_history.append({"role": "user", "content": result.text})

                extra_instructions: str | None = None
                if extractor is not None:
                    # Se na resposta ANTERIOR a gente pediu confirmação, o que
                    # o cidadão acabou de dizer pode ser essa confirmação —
                    # checa isso ANTES de decidir a próxima instrução.
                    just_confirmed = False
                    if awaiting_confirmation:
                        just_confirmed = extractor.check_confirmation(conversation_history)
                        if just_confirmed:
                            relato_confirmado = True
                            awaiting_confirmation = False

                    # Chamada ISOLADA — o estado extraído só volta pra IA como
                    # orientação da conversa ATUAL, nunca é persistido como
                    # "fato dito pela IA" em conversation_history.
                    relato = extractor.extract(conversation_history)

                    if not relato.is_empty:
                        if just_confirmed:
                            extra_instructions = (
                                "O cidadão CONFIRMOU que os dados estão certos. Agradeça "
                                "e diga que foi registrado."
                            )
                        elif relato.is_complete:
                            extra_instructions = (
                                f"Você já tem todos os dados do relato: {relato.resumo_legivel()}. "
                                "Repita esse resumo pro cidadão em linguagem natural e pergunte se "
                                "está tudo certo e se pode salvar/enviar. NÃO diga que já foi salvo."
                            )
                            awaiting_confirmation = True
                        else:
                            faltando = ", ".join(relato.campos_faltando)
                            extra_instructions = (
                                f"Você está coletando os dados de um relato cidadão (pode ser "
                                f"reclamação, opinião sobre lei, ou necessidade de serviço). Já "
                                f"sabemos: {relato.resumo_legivel()}. Ainda falta saber: {faltando}. "
                                "Pergunte por UM desses campos que falta, de forma natural. Só "
                                "pergunte local se for algo físico, e posição (concorda/discorda) "
                                "se for opinião sobre lei/política — não force campo que não faz sentido."
                            )
                            awaiting_confirmation = False

                        database.upsert_relato(
                            conversation_id=conversation_id,
                            tipo_relato=relato.tipo_relato,
                            tema=relato.tema,
                            descricao=relato.descricao,
                            local=relato.local,
                            posicao=relato.posicao,
                            timestamp=datetime.now(tz=timezone.utc).isoformat(),
                            confirmado=relato_confirmado,
                        )

                reply_text = responder.generate_reply(conversation_history, extra_instructions=extra_instructions)
                conversation_history.append({"role": "assistant", "content": reply_text})

                console.print(f"[cyan]<[/cyan] {reply_text}")

                if synthesizer is not None:
                    # Anti-feedback: descarta o que o mic captou até agora
                    # (ex: ruído durante o "thinking") antes de tocar,
                    # pra não confundir isso com o início da próxima fala.
                    source.drain_pending()

                    if ui_state is not None:
                        ui_state.update(state="speaking_ai", amplitude=0.5)

                    audio = synthesizer.synthesize(reply_text)
                    playback.play(audio.samples, audio.samplerate)

                    # Anti-feedback: descarta o que o mic captou ENQUANTO a
                    # IA falava — sem isso, ela se autoescuta e dispara uma
                    # transcrição da própria voz.
                    source.drain_pending()

                if ui_state is not None:
                    ui_state.update(state="listening", amplitude=0.0)
            elif ui_state is not None:
                ui_state.update(state="listening", amplitude=0.0)

            session_id = _save_and_log_turn(
                samples=utterance.samples,
                samplerate=utterance.samplerate,
                duration_s=utterance.duration_s,
                source_kind=source.__class__.__name__,
                transcript_text=result.text,
                language=result.language,
                collector=collector,
                reply_text=reply_text,
            )
            console.print(f"[dim](sessão {session_id})[/dim]")


def run_live(
    source: AudioSource,
    host: str = "127.0.0.1",
    port: int = 8000,
    responder: ResponderBackend | None = None,
    synthesizer: PiperSynthesizer | None = None,
    extractor: RelatoExtractor | None = None,
) -> None:
    """
    Roda a captura+transcrição(+resposta+voz) numa thread de fundo, e serve
    a UI pulsante (FastAPI/WebSocket) na thread principal. A thread de fundo
    é quem realmente decide quando o processo acaba (Ctrl+C) — o servidor
    uvicorn é só a vitrine.
    """
    import threading

    import uvicorn

    from voz_civica.ui.server import build_app

    ui_state = SharedUiState()

    capture_thread = threading.Thread(
        target=listen_and_transcribe,
        args=(source, ui_state, responder, synthesizer, extractor),
        daemon=True,
    )
    capture_thread.start()

    app = build_app(ui_state)
    console.print(f"[bold cyan]voz-civica[/bold cyan] — UI em [underline]http://{host}:{port}[/underline]")
    uvicorn.run(app, host=host, port=port, log_level="warning")
