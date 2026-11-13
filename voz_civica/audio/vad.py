"""
voz_civica/audio/vad.py

Detecção de atividade de voz (VAD) via Silero — decide, frame a frame,
quando o usuário começa e termina de falar, pra permitir escuta contínua
sem push-to-talk.

torch (CPU) já está instalado nessa máquina para outros fins — o modelo do
Silero é minúsculo e roda em bem menos de 1ms por frame, então usá-lo em vez
do webrtcvad (mais grosseiro, mais falso-positivo com ruído de ambiente) não
tem custo real aqui. Ver plano (Estágio 1) para a justificativa completa.

Máquina de estados:
    NOT_SPEAKING --(N frames acima do limiar)--> SPEAKING
    SPEAKING --(timeout de silêncio contínuo)--> NOT_SPEAKING, emite Utterance
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

import numpy as np
import torch

from voz_civica.config import settings


class VadState(Enum):
    NOT_SPEAKING = "not_speaking"
    SPEAKING = "speaking"


@dataclass
class Utterance:
    """Um trecho de fala completo, do início ao fim detectado pelo VAD."""

    samples: np.ndarray  # float32 mono, concatenado (pre-roll + fala + silêncio final)
    samplerate: int
    duration_s: float


@dataclass
class _VadRuntimeState:
    state: VadState = VadState.NOT_SPEAKING
    consecutive_speech_frames: int = 0
    consecutive_silence_frames: int = 0
    preroll: deque = field(default_factory=lambda: deque(maxlen=0))
    utterance_frames: list = field(default_factory=list)


class SileroVAD:
    """
    Envolve o modelo Silero VAD e mantém a máquina de estados de
    início/fim de fala sobre um fluxo contínuo de frames.
    """

    def __init__(self):
        self._model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self._model.eval()

        frame_duration_s = settings.frame_size / settings.sample_rate
        preroll_frames = max(1, int((settings.vad_preroll_ms / 1000) / frame_duration_s))
        silence_timeout_frames = max(1, int((settings.vad_silence_timeout_ms / 1000) / frame_duration_s))

        self._preroll_frames = preroll_frames
        self._silence_timeout_frames = silence_timeout_frames

    def speech_probability(self, frame: np.ndarray) -> float:
        """Probabilidade [0,1] de que o frame contém fala."""
        tensor = torch.from_numpy(frame).float()
        with torch.no_grad():
            return float(self._model(tensor, settings.sample_rate).item())

    def process_stream(
        self, frames: Iterator[np.ndarray]
    ) -> Iterator[tuple[np.ndarray, float, VadState, Utterance | None]]:
        """
        Consome um stream de frames e produz, para cada frame:
        (frame_bruto, probabilidade_de_fala, estado_atual, utterance_ou_None)

        `frame_bruto` é devolvido pra quem quiser calcular amplitude (ex: UI
        pulsante) sem duplicar a leitura do stream. `utterance_ou_None` só
        vem preenchido no frame exato em que uma fala termina (SPEECH_END).
        """
        rt = _VadRuntimeState(preroll=deque(maxlen=self._preroll_frames))

        for frame in frames:
            prob = self.speech_probability(frame)
            is_speech = prob >= settings.vad_speech_threshold
            utterance: Utterance | None = None

            if rt.state == VadState.NOT_SPEAKING:
                rt.preroll.append(frame)
                if is_speech:
                    rt.consecutive_speech_frames += 1
                else:
                    rt.consecutive_speech_frames = 0

                if rt.consecutive_speech_frames >= settings.vad_start_frames:
                    rt.state = VadState.SPEAKING
                    rt.utterance_frames = list(rt.preroll)
                    rt.consecutive_silence_frames = 0

            elif rt.state == VadState.SPEAKING:
                rt.utterance_frames.append(frame)
                if is_speech:
                    rt.consecutive_silence_frames = 0
                else:
                    rt.consecutive_silence_frames += 1

                if rt.consecutive_silence_frames >= self._silence_timeout_frames:
                    samples = np.concatenate(rt.utterance_frames)
                    utterance = Utterance(
                        samples=samples,
                        samplerate=settings.sample_rate,
                        duration_s=len(samples) / settings.sample_rate,
                    )
                    rt.state = VadState.NOT_SPEAKING
                    rt.consecutive_speech_frames = 0
                    rt.utterance_frames = []
                    rt.preroll.clear()

            yield frame, prob, rt.state, utterance

        # O stream acabou (fim de arquivo — num microfone ao vivo isso nunca
        # acontece). Se ainda havia uma fala em andamento sem silêncio final
        # suficiente pra disparar SPEECH_END, libera ela agora em vez de
        # descartar silenciosamente.
        if rt.state == VadState.SPEAKING and rt.utterance_frames:
            samples = np.concatenate(rt.utterance_frames)
            utterance = Utterance(
                samples=samples,
                samplerate=settings.sample_rate,
                duration_s=len(samples) / settings.sample_rate,
            )
            empty_frame = np.zeros(settings.frame_size, dtype=np.float32)
            yield empty_frame, 0.0, VadState.NOT_SPEAKING, utterance
