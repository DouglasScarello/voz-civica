"""Testes do playback em blocos — a amplitude publicada é o que move o orb da UI.

Não abrem dispositivo de áudio real: substituem o OutputStream por um fake,
então rodam em qualquer máquina (inclusive CI sem placa de som).
"""

import numpy as np
import pytest

from voz_civica.audio import playback


class FakeStream:
    """Imita o suficiente de sd.OutputStream para o teste."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.blocks_written = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, block: np.ndarray) -> None:
        self.blocks_written += len(block)


@pytest.fixture
def fake_stream(monkeypatch):
    created = []

    def factory(**kwargs):
        stream = FakeStream(**kwargs)
        created.append(stream)
        return stream

    monkeypatch.setattr(playback.sd, "OutputStream", factory)
    return created


def test_block_level_satura_em_um():
    assert playback.block_level(np.zeros(100, dtype="float32")) == 0.0
    assert playback.block_level(np.full(100, 0.01, dtype="float32")) == pytest.approx(0.08)
    assert playback.block_level(np.full(100, 0.9, dtype="float32")) == 1.0


def test_play_stream_normaliza_pelo_pico_da_fala(fake_stream):
    sr = 16_000
    quiet = np.full(sr // 2, 0.01, dtype="float32")
    loud = np.full(sr // 2, 0.5, dtype="float32")
    samples = np.concatenate([quiet, quiet, loud, loud])

    levels: list[float] = []
    aborted = playback.play_stream(samples, sr, on_level=levels.append, block_ms=100)

    assert aborted is False
    assert fake_stream[0].blocks_written == len(samples)

    # último nível é sempre 0.0 (fim da fala -> orb volta ao repouso)
    assert levels[-1] == 0.0
    corpo = levels[:-1]

    # normalizado pelo pico: o trecho alto chega a 1.0 e o baixo fica bem abaixo
    assert max(corpo) == pytest.approx(1.0)
    assert min(corpo) < 0.3
    # e existe dinâmica de verdade, não dois valores
    assert len(set(round(v, 3) for v in corpo)) >= 2


def test_play_stream_aborta_entre_blocos(fake_stream):
    sr = 16_000
    samples = np.full(sr * 2, 0.3, dtype="float32")
    calls = {"n": 0}

    def should_abort() -> bool:
        calls["n"] += 1
        return calls["n"] > 3

    levels: list[float] = []
    aborted = playback.play_stream(
        samples, sr, on_level=levels.append, should_abort=should_abort, block_ms=100
    )

    assert aborted is True
    assert fake_stream[0].blocks_written < len(samples)
    assert levels[-1] == 0.0


def test_play_stream_audio_vazio_nao_abre_stream(fake_stream):
    levels: list[float] = []
    aborted = playback.play_stream(np.zeros(0, dtype="float32"), 16_000, on_level=levels.append)

    assert aborted is False
    assert levels == [0.0]
    assert fake_stream == []
