"""
voz_civica/cli.py

Ponto de entrada `poetry run voz-civica`. Usa argparse (biblioteca padrão,
sem dependência nova) em vez de typer/click.
"""

import argparse
import sys

from voz_civica.config import settings


def _add_common_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--respond",
        action="store_true",
        help="Gera resposta via LLM local (Ollama) depois de cada transcrição (Estágio 4)",
    )
    sub.add_argument(
        "--speak",
        action="store_true",
        help="Fala a resposta em voz alta via Piper, com anti-feedback (Estágio 5). Implica --respond.",
    )
    sub.add_argument(
        "--model",
        default=settings.ollama_model,
        help=f"Modelo Ollama a usar (padrão: {settings.ollama_model})",
    )
    sub.add_argument(
        "--voice",
        default=settings.piper_voice,
        help=f"Voz do Piper a usar (padrão: {settings.piper_voice})",
    )


def _build_responder(args):
    if not (args.respond or args.speak):
        return None
    from voz_civica.respond.local_llm import OllamaResponder

    return OllamaResponder(model=args.model)


def _build_synthesizer(args):
    if not args.speak:
        return None
    from voz_civica.tts.synthesizer import PiperSynthesizer

    return PiperSynthesizer(voice=args.voice)


def _build_extractor(args):
    # Sempre que há conversa, o relato é extraído pro backend — não é um
    # opt-in separado, é o próprio motivo da conversa existir. Nunca é lido
    # de volta pela IA (voz_civica/respond/extractor.py).
    if not (args.respond or args.speak):
        return None
    from voz_civica.respond.extractor import RelatoExtractor

    return RelatoExtractor(model=args.model)


def main() -> None:
    parser = argparse.ArgumentParser(prog="voz-civica")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Escuta contínua e transcrição (Estágio 1+)")
    capture.add_argument(
        "--file",
        help="Em vez do microfone, roda o pipeline sobre um arquivo .wav existente",
    )
    capture.add_argument(
        "--device",
        help="Índice ou nome do dispositivo de captura (padrão: dispositivo default do sistema)",
    )
    _add_common_args(capture)

    live = subparsers.add_parser("live", help="Captura + UI pulsante no navegador (Estágio 3+)")
    live.add_argument("--device", help="Índice ou nome do dispositivo de captura")
    live.add_argument("--host", default="127.0.0.1")
    live.add_argument("--port", type=int, default=8000)
    _add_common_args(live)

    args = parser.parse_args()

    if args.command == "capture":
        from voz_civica.orchestrator import listen_and_transcribe

        if args.file:
            from voz_civica.audio.sources.wavfile import FileSource

            source = FileSource(args.file)
        else:
            from voz_civica.audio.sources.microphone import MicrophoneSource

            source = MicrophoneSource(device=args.device)

        try:
            listen_and_transcribe(
                source,
                responder=_build_responder(args),
                synthesizer=_build_synthesizer(args),
                extractor=_build_extractor(args),
            )
        except KeyboardInterrupt:
            print("\nEncerrado.")
            sys.exit(0)

    elif args.command == "live":
        from voz_civica.audio.sources.microphone import MicrophoneSource
        from voz_civica.orchestrator import run_live

        source = MicrophoneSource(device=args.device)

        try:
            run_live(
                source,
                host=args.host,
                port=args.port,
                responder=_build_responder(args),
                synthesizer=_build_synthesizer(args),
                extractor=_build_extractor(args),
            )
        except KeyboardInterrupt:
            print("\nEncerrado.")
            sys.exit(0)


if __name__ == "__main__":
    main()
