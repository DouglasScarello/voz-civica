"""
tests/conftest.py

Fixtures compartilhadas. Como não há sintetizador de voz (espeak-ng/festival)
instalado nesta máquina ainda, os testes de fiação (sources, collector,
database) usam um tom sintético gerado em runtime — suficiente para validar
o encanamento sem depender de fala real. O teste de qualidade de
transcrição (test_transcriber.py) precisa de uma fixture com fala humana de
verdade, gravada manualmente — ver nota nesse arquivo.
"""

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def synthetic_tone_wav(tmp_path):
    """Gera um .wav curto com um tom senoidal — só pra testar o encanamento de I/O, não STT."""
    samplerate = 16_000
    duration_s = 1.0
    freq_hz = 440.0
    t = np.linspace(0, duration_s, int(samplerate * duration_s), endpoint=False)
    samples = 0.3 * np.sin(2 * np.pi * freq_hz * t).astype("float32")

    path = tmp_path / "tone.wav"
    sf.write(path, samples, samplerate)
    return path
