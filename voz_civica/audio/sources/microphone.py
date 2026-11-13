"""
voz_civica/audio/sources/microphone.py

Fonte de áudio ao vivo via microfone (PortAudio, através de sounddevice).

Nota de thread-safety (ver plano — Risco #5): o callback do sounddevice roda
numa thread de áudio separada da thread/loop principal. Aqui usamos uma
queue.Queue simples (thread-safe por padrão) como ponte entre o callback e
o gerador consumido pelo resto do pipeline — evita o bug sutil de áudio
cortado que apareceria se o callback tentasse tocar em estado do asyncio
loop diretamente.
"""

import queue
from typing import Iterator

import numpy as np
import sounddevice as sd

from voz_civica.audio.sources.base import AudioSource
from voz_civica.config import settings


class MicrophoneSource(AudioSource):
    """Captura contínua do microfone padrão do sistema (ou de um device_id específico)."""

    def __init__(self, device: int | str | None = None):
        self._device = device
        self._samplerate = settings.sample_rate
        self._frame_size = settings.frame_size
        self._queue: queue.Queue[np.ndarray] = queue.Queue()

    @property
    def samplerate(self) -> int:
        return self._samplerate

    def _on_audio(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            # xruns/overflow do PortAudio — não derruba o processo, só loga via print
            # (logging estruturado de falha de captura acontece na camada de sessão, não aqui)
            print(f"[microphone] status do stream: {status}")
        # indata vem como (frames, channels) float32; mono -> squeeze pra 1D
        self._queue.put(indata[:, 0].copy())

    def stream_frames(self) -> Iterator[np.ndarray]:
        with sd.InputStream(
            samplerate=self._samplerate,
            blocksize=self._frame_size,
            channels=1,
            dtype="float32",
            device=self._device,
            callback=self._on_audio,
        ):
            while True:
                yield self._queue.get()

    def drain_pending(self) -> None:
        """Descarta frames acumulados na fila (ex: captados enquanto a IA falava)."""
        drained = 0
        while True:
            try:
                self._queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        if drained:
            print(f"[microphone] descartados {drained} frames pendentes (anti-feedback)")
