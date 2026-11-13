"""
scripts/download_piper_voice.py

Baixa uma voz do Piper do repositório rhasspy/piper-voices (Hugging Face) e
guarda achatada em models/piper/<voice>.onnx (+.onnx.json), pra o caminho
ficar previsível independente da estrutura de diretórios do repo de origem.

Uso:
    poetry run python scripts/download_piper_voice.py pt_BR-faber-medium
"""

import shutil
import sys

from huggingface_hub import hf_hub_download

from voz_civica.config import MODELS_ROOT


def download(voice: str) -> None:
    # "pt_BR-faber-medium" -> lang="pt", region="BR", speaker="faber", quality="medium"
    lang_region, speaker, quality = voice.split("-")
    lang = lang_region.split("_")[0]

    dest_dir = MODELS_ROOT / "piper"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for ext in [".onnx", ".onnx.json"]:
        remote_path = f"{lang}/{lang_region}/{speaker}/{quality}/{voice}{ext}"
        downloaded = hf_hub_download(repo_id="rhasspy/piper-voices", filename=remote_path)
        shutil.copy(downloaded, dest_dir / f"{voice}{ext}")
        print(f"OK: {dest_dir / f'{voice}{ext}'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/download_piper_voice.py <voice>  (ex: pt_BR-faber-medium)")
        sys.exit(1)
    download(sys.argv[1])
