from voz_civica.audio.sources.wavfile import FileSource
from voz_civica.config import settings


def test_file_source_yields_fixed_size_frames(synthetic_tone_wav):
    source = FileSource(synthetic_tone_wav)
    frames = list(source.stream_frames())

    assert len(frames) > 0
    for frame in frames:
        assert len(frame) == settings.frame_size


def test_file_source_samplerate_matches_config(synthetic_tone_wav):
    source = FileSource(synthetic_tone_wav)
    assert source.samplerate == settings.sample_rate
