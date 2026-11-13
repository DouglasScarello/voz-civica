"""
voz_civica/stt/transcriber.py

Transcrição local via faster-whisper (CTranslate2, quantização int8) —
escolhido no lugar do openai-whisper puro porque roda em CPU sem CUDA de
forma bem mais leve, e no lugar do whisper.cpp porque é pip-instalável
puro Python, sem depender de um binário C++ compilado separadamente.

Modelo padrão: "small"/int8/cpu (ver voz_civica.config) — mais preciso que
"base", ainda leve o suficiente pra rodar nessa máquina sem GPU dedicada.
"""

from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from voz_civica.config import settings


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_ms: int


class Transcriber:
    def __init__(self):
        self._model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        """
        samples: float32 mono a settings.sample_rate (16kHz), já segmentado
        pelo VAD como uma única fala (utterance).
        """
        import time

        start = time.monotonic()
        segments, info = self._model.transcribe(
            samples,
            language=settings.whisper_language,
            beam_size=5,
            initial_prompt=settings.whisper_initial_prompt,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        duration_ms = int((time.monotonic() - start) * 1000)

        return TranscriptionResult(
            text=text,
            language=info.language,
            duration_ms=duration_ms,
        )
