"""
voz_civica/tts/synthesizer.py

Síntese de voz local via Piper — CPU-real-time, sem depender de torch pra
inferência (usa ONNX Runtime). Voz PT-BR baixada via
scripts/download_piper_voice.py para models/piper/<voice>.onnx.
"""

from dataclasses import dataclass
from typing import Iterator

import numpy as np
from piper import PiperVoice

from voz_civica.config import MODELS_ROOT, settings


@dataclass
class SynthesizedAudio:
    samples: np.ndarray  # float32 mono
    samplerate: int


class PiperSynthesizer:
    def __init__(self, voice: str | None = None):
        voice_name = voice or settings.piper_voice
        model_path = MODELS_ROOT / "piper" / f"{voice_name}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Voz do Piper não encontrada em {model_path}. Rode: "
                f"poetry run python scripts/download_piper_voice.py {voice_name}"
            )
        self._voice = PiperVoice.load(model_path)

    def synthesize(self, text: str) -> SynthesizedAudio:
        """Sintetiza o texto inteiro de uma vez e retorna como um único array."""
        chunks = list(self._voice.synthesize(text))
        if not chunks:
            return SynthesizedAudio(samples=np.zeros(0, dtype="float32"), samplerate=self._voice.config.sample_rate)

        samples = np.concatenate([c.audio_float_array for c in chunks])
        return SynthesizedAudio(samples=samples, samplerate=chunks[0].sample_rate)

    def synthesize_stream(self, text: str) -> Iterator[SynthesizedAudio]:
        """Sintetiza e libera cada trecho (frase) assim que fica pronto — pra tocar com menos espera."""
        for chunk in self._voice.synthesize(text):
            yield SynthesizedAudio(samples=chunk.audio_float_array, samplerate=chunk.sample_rate)
