"""
voz_civica/config.py

Configuração central do projeto — sample rate, limiares do VAD, escolha de
modelo, caminhos de dados. Tudo local, sem chave de API (o projeto não usa
nenhum serviço pago).
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
MODELS_ROOT = PROJECT_ROOT / "models"


class Settings(BaseSettings):
    # Áudio
    sample_rate: int = 16_000
    frame_size: int = 512  # ~32ms a 16kHz — tamanho nativo do Silero VAD

    # VAD
    vad_speech_threshold: float = 0.5
    vad_start_frames: int = 3        # frames consecutivos acima do limiar → SPEECH_START
    vad_silence_timeout_ms: int = 800  # silêncio contínuo → SPEECH_END
    vad_preroll_ms: int = 250         # áudio mantido antes do SPEECH_START

    # STT
    whisper_model_size: str = "small"
    whisper_compute_type: str = "int8"
    whisper_device: str = "cpu"
    whisper_language: str = "pt"
    # "Primeia" o vocabulário esperado — reduz erro em termos de denúncia
    # cidadã que o Whisper "small" confunde com palavra parecida em inglês
    # (ex: "poste" -> "post"). Ver Estágio 6, ajuste pós-teste real.
    whisper_initial_prompt: str = (
        "Relato de problema na rua: buraco, poste, calçada, árvore caída, "
        "iluminação pública, coleta de lixo, esgoto, asfalto."
    )

    # Resposta (LLM local via Ollama — sem nuvem, sem custo)
    ollama_model: str = "llama3.2:3b"

    # TTS
    piper_voice: str = "pt_BR-faber-medium"

    model_config = SettingsConfigDict(env_prefix="VOZ_CIVICA_")


settings = Settings()
