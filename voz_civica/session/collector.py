"""
voz_civica/session/collector.py

Espelha civic_framework/collector.py do gov-analise: um arquivo JSON por
sessão de conversa, com versionamento por data. Aqui, em vez de "um arquivo
por recurso por dia" (dados agregados de muitos registros), é "um arquivo
por sessão de fala" (um turno de conversa) — mesmo formato de envelope
_meta + payload, mesma ideia de snapshot imutável e navegável por data.

Design:
- Um arquivo JSON por sessão: data/sessions/<YYYYMMDD>/<session_id>.json
- Metadata da sessão salva junto (timestamp, duração, contadores)
- Fonte de verdade imutável — o SQLite (database.py) é só índice/consulta
  sobre isso, não substitui o JSON.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from voz_civica.config import DATA_ROOT

log = logging.getLogger(__name__)

SESSIONS_ROOT = DATA_ROOT / "sessions"


class SessionCollector:
    """
    Persiste cada turno de conversa em JSON versionado por data.

    Uso:
        collector = SessionCollector()
        collector.save(session_id="abc123", payload={...})
    """

    def __init__(self):
        SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)

    def _today(self) -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y%m%d")

    def save(self, session_id: str, payload: Dict[str, Any]) -> Path:
        """
        Salva o payload de uma sessão (já deve conter o bloco `_meta`).
        Retorna o caminho do arquivo salvo.
        """
        hoje = self._today()
        destino = SESSIONS_ROOT / hoje
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f"{session_id}.json"

        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        log.info(f"Sessão {session_id} salva → {arquivo}")
        return arquivo

    def list_snapshots(self, data: Optional[str] = None) -> List[str]:
        """
        Lista session_ids disponíveis. `data` filtra por um dia (YYYYMMDD);
        None lista todos os dias.
        """
        if data:
            path = SESSIONS_ROOT / data
            if not path.exists():
                return []
            return sorted(f.stem for f in path.glob("*.json"))

        all_ids = []
        if not SESSIONS_ROOT.exists():
            return []
        for day_dir in sorted(SESSIONS_ROOT.iterdir()):
            if day_dir.is_dir():
                all_ids.extend(sorted(f.stem for f in day_dir.glob("*.json")))
        return all_ids

    def load_snapshot(self, session_id: str, data: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Carrega o payload de uma sessão. Se `data` (YYYYMMDD) não for
        informado, procura em todos os dias.
        """
        if data:
            arquivo = SESSIONS_ROOT / data / f"{session_id}.json"
            if not arquivo.exists():
                return None
            with open(arquivo, encoding="utf-8") as f:
                return json.load(f)

        if not SESSIONS_ROOT.exists():
            return None
        for day_dir in SESSIONS_ROOT.iterdir():
            candidate = day_dir / f"{session_id}.json"
            if candidate.exists():
                with open(candidate, encoding="utf-8") as f:
                    return json.load(f)
        return None
