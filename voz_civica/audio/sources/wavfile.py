"""
voz_civica/audio/sources/wavfile.py

Fonte de áudio a partir de um arquivo .wav existente — usada em testes
automatizados (tests/fixtures/sample_speech.wav) e em `voz-civica capture
--file` pra exercitar todo o pipeline sem depender do microfone.

Reamostra automaticamente para o sample rate do projeto se o arquivo vier
em outra taxa, e fatia em frames do mesmo tamanho que o microfone entregaria,
pra que o VAD veja exatamente o mesmo formato de entrada nos dois casos.
"""

from pathlib import Path
from typing import Iterator

import numpy as np
import soundfile as sf

from voz_civica.audio.sources.base import AudioSource
from voz_civica.config import settings


class FileSource(AudioSource):
    """Lê um arquivo de áudio e o expõe como um stream de frames, como se fosse ao vivo."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._frame_size = settings.frame_size
        self._samplerate = settings.sample_rate

    @property
    def samplerate(self) -> int:
        return self._samplerate

    def stream_frames(self) -> Iterator[np.ndarray]:
        data, file_samplerate = sf.read(self._path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)  # downmix se estéreo

        if file_samplerate != self._samplerate:
            # Reamostragem simples por interpolação linear — suficiente para
            # fixtures de teste; não é o caminho usado com áudio real de mic.
            duration_s = len(mono) / file_samplerate
            n_target = int(duration_s * self._samplerate)
            x_original = np.linspace(0, duration_s, num=len(mono))
            x_target = np.linspace(0, duration_s, num=n_target)
            mono = np.interp(x_target, x_original, mono).astype("float32")

        for start in range(0, len(mono), self._frame_size):
            chunk = mono[start : start + self._frame_size]
            if len(chunk) < self._frame_size:
                # último frame incompleto — preenche com zero (silêncio) até o tamanho fixo
                chunk = np.pad(chunk, (0, self._frame_size - len(chunk)))
            yield chunk
