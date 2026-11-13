"""
voz_civica/audio/playback.py

Reprodução de áudio (saída) via sounddevice — usado pra tocar a resposta
sintetizada pelo Piper.
"""

import numpy as np
import sounddevice as sd


def play(samples: np.ndarray, samplerate: int) -> None:
    """Toca o áudio e bloqueia até terminar (uso simples e previsível pro anti-feedback)."""
    sd.play(samples, samplerate)
    sd.wait()
