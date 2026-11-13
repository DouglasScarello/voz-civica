"""
voz_civica/audio/playback.py

Reprodução de áudio (saída) via sounddevice — usado pra tocar a resposta
sintetizada pelo Piper.

A reprodução é feita em blocos (não num `sd.play` único) por dois motivos:
1. medir a amplitude real de cada bloco e publicá-la, para a UI pulsar no
   ritmo da voz que está sendo falada;
2. permitir abortar a fala no meio (botão "parar fala"), checando um
   callback entre blocos.
"""

from typing import Callable

import numpy as np
import sounddevice as sd

# ganho de segurança para casos de áudio muito baixo
_LEVEL_GAIN = 8.0


def _rms(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))


def block_level(block: np.ndarray, gain: float = _LEVEL_GAIN) -> float:
    """RMS de um bloco normalizado para 0.0–1.0 (satura em 1.0)."""
    return min(1.0, _rms(block) * gain)


def play(samples: np.ndarray, samplerate: int) -> None:
    """Toca o áudio e bloqueia até terminar (uso simples e previsível pro anti-feedback)."""
    sd.play(samples, samplerate)
    sd.wait()


def play_stream(
    samples: np.ndarray,
    samplerate: int,
    on_level: Callable[[float], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
    block_ms: int = 50,
) -> bool:
    """
    Toca `samples` em blocos, chamando `on_level(0.0–1.0)` a cada bloco com a
    amplitude real do trecho reproduzido. Retorna True se foi abortado.

    A amplitude é normalizada pelo pico da própria fala (e não por um ganho
    fixo): sem isso, voz sintetizada satura perto de 1.0 e o pulso perde
    dinâmica. A curva `** 0.6` é perceptual — aproxima o nível do que o
    ouvido percebe como volume.

    `should_abort` é consultado entre blocos — é o que permite ao botão
    "parar fala" interromper a resposta no meio.
    """
    if samples.size == 0:
        if on_level is not None:
            on_level(0.0)
        return False

    block_size = max(1, int(samplerate * block_ms / 1000))
    blocks = [samples[i : i + block_size] for i in range(0, len(samples), block_size)]
    peak = max((_rms(b) for b in blocks), default=0.0)

    aborted = False
    with sd.OutputStream(samplerate=samplerate, channels=1, dtype="float32") as stream:
        for block in blocks:
            if should_abort is not None and should_abort():
                aborted = True
                break
            stream.write(block.reshape(-1, 1))
            if on_level is not None:
                level = (_rms(block) / peak) ** 0.6 if peak > 0 else 0.0
                on_level(min(1.0, level))

    if on_level is not None:
        on_level(0.0)
    return aborted

