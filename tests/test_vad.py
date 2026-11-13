"""
tests/test_vad.py

Cobre o bug encontrado durante o teste manual: se o stream acaba com fala
em andamento (sem silêncio final suficiente pra disparar SPEECH_END), o VAD
tem que liberar essa fala em vez de descartá-la silenciosamente.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

from voz_civica.audio.sources.wavfile import FileSource
from voz_civica.audio.vad import SileroVAD
from voz_civica.config import settings

FIXTURE = Path(__file__).parent / "fixtures" / "sample_speech.wav"


def test_flushes_pending_utterance_at_end_of_stream():
    """A fixture sample_speech.wav termina sem silêncio de sobra — regressão do bug real."""
    vad = SileroVAD()
    source = FileSource(FIXTURE)

    utterances = [u for _, _, _, u in vad.process_stream(source.stream_frames()) if u is not None]

    assert len(utterances) == 1
    assert utterances[0].duration_s > 1.0


def test_pure_silence_never_emits_utterance(tmp_path):
    samplerate = settings.sample_rate
    silence = np.zeros(samplerate * 2, dtype="float32")  # 2s de silêncio puro
    path = tmp_path / "silence.wav"
    sf.write(path, silence, samplerate)

    vad = SileroVAD()
    source = FileSource(path)

    utterances = [u for _, _, _, u in vad.process_stream(source.stream_frames()) if u is not None]

    assert utterances == []
