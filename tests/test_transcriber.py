"""
tests/test_transcriber.py

A fixture sample_speech.wav foi gerada com o Piper (voz sintética PT-BR),
não é fala humana gravada — mas serve bem pra teste automatizado porque o
texto de origem é conhecido exatamente. Comparação por similaridade difusa
(não exata), já que a saída do Whisper pode variar em pontuação/capitalização
entre versões do modelo.
"""

from difflib import SequenceMatcher
from pathlib import Path

from voz_civica.audio.sources.wavfile import FileSource
from voz_civica.audio.vad import SileroVAD
from voz_civica.stt.transcriber import Transcriber

FIXTURE = Path(__file__).parent / "fixtures" / "sample_speech.wav"
EXPECTED_TEXT = "Olá, isso é um teste do assistente de voz."


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def test_transcribes_known_fixture_reasonably_well():
    vad = SileroVAD()
    transcriber = Transcriber()
    source = FileSource(FIXTURE)

    utterances = [u for _, _, _, u in vad.process_stream(source.stream_frames()) if u is not None]

    assert len(utterances) == 1, "esperava exatamente uma fala detectada no fixture"

    result = transcriber.transcribe(utterances[0].samples)
    assert _similarity(result.text, EXPECTED_TEXT) > 0.85, f"transcrição muito diferente: {result.text!r}"
