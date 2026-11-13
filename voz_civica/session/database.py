"""
voz_civica/session/database.py

Espelha civic_framework/database.py do gov-analise: SQLite com WAL,
upsert idempotente (aqui por hash do áudio, não por id de recurso externo),
e uma tabela de auditoria separada que registra TODA tentativa de captura
— sucesso ou falha — não só as sessões que terminaram bem.
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from voz_civica.config import DATA_ROOT

log = logging.getLogger(__name__)

DB_PATH = DATA_ROOT / "voz_civica.db"


SCHEMA_SQL = """
-- Uma linha por sessão de conversa transcrita com sucesso
CREATE TABLE IF NOT EXISTS sessions (
    uid              TEXT PRIMARY KEY,   -- session_id
    audio_sha256     TEXT UNIQUE,        -- garante idempotência (não duplica ao re-transcrever)
    captured_at      TEXT NOT NULL,      -- ISO 8601
    duration_s       REAL,
    samplerate       INTEGER,
    source_kind      TEXT,               -- "microphone" | "file"
    audio_path       TEXT,
    transcript_text  TEXT,
    reply_text       TEXT,               -- preenchido a partir do Estágio 4 (resposta do LLM)
    language         TEXT,
    model_name       TEXT,
    raw_json         TEXT                -- payload completo, para auditoria
);

-- Registro de toda tentativa de captura, inclusive falhas — não só sucesso
CREATE TABLE IF NOT EXISTS capture_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT,
    started_at    TEXT NOT NULL,
    status        TEXT NOT NULL,   -- "ok" | "error" | "discarded_noise"
    error_message TEXT
);

-- Relatos cidadãos extraídos da conversa, de forma estruturada. Escopo
-- amplo: reclamação de infraestrutura, opinião sobre lei/política, ou
-- necessidade de serviço público — não só "denúncia" no sentido estrito.
-- SÓ-BACKEND: nenhum código de resposta da IA lê esta tabela de volta pra
-- repassar pra OUTRA pessoa — o que ela recebe de volta (via
-- extra_instructions) é só o estado atual DESSA MESMA conversa, pra saber
-- o que ainda falta perguntar. `confirmado` só vira 1 depois que o cidadão
-- validou o resumo lido de volta.
CREATE TABLE IF NOT EXISTS relatos (
    id                TEXT PRIMARY KEY,   -- conversation_id da conversa que originou
    tipo_relato       TEXT,               -- reclamação de infra | opinião sobre lei | necessidade de serviço | outro
    tema              TEXT,               -- assunto específico
    descricao         TEXT,
    local             TEXT,               -- rua/bairro, quando se aplica
    posicao           TEXT,               -- concorda/discorda/neutro, quando se aplica
    confirmado        INTEGER NOT NULL DEFAULT 0,
    criado_em         TEXT NOT NULL,
    atualizado_em     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_captured_at ON sessions (captured_at);
CREATE INDEX IF NOT EXISTS idx_capture_runs_session ON capture_runs (session_id);
CREATE INDEX IF NOT EXISTS idx_relatos_criado_em ON relatos (criado_em);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Context manager para conexão SQLite com commit automático."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Cria o schema se ainda não existir."""
    with _conn() as con:
        con.executescript(SCHEMA_SQL)
    log.info(f"Banco inicializado: {DB_PATH}")


def log_capture_run(session_id: str, started_at: str, status: str, error_message: Optional[str] = None) -> None:
    """Registra uma tentativa de captura — chamado em toda execução, sucesso ou falha."""
    with _conn() as con:
        con.execute(
            "INSERT INTO capture_runs (session_id, started_at, status, error_message) VALUES (?,?,?,?)",
            (session_id, started_at, status, error_message),
        )


def upsert_session(
    session_id: str,
    audio_sha256: str,
    captured_at: str,
    duration_s: float,
    samplerate: int,
    source_kind: str,
    audio_path: str,
    transcript_text: str,
    language: str,
    model_name: str,
    raw_json: str,
    reply_text: Optional[str] = None,
) -> None:
    """
    Insere ou atualiza uma sessão. Upsert por `audio_sha256`: re-rodar a
    transcrição sobre o mesmo áudio (ex: depois de trocar de modelo)
    atualiza a linha em vez de duplicar.
    """
    with _conn() as con:
        con.execute(
            """
            INSERT INTO sessions (
                uid, audio_sha256, captured_at, duration_s, samplerate,
                source_kind, audio_path, transcript_text, reply_text, language, model_name, raw_json
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(audio_sha256) DO UPDATE SET
                transcript_text=excluded.transcript_text,
                reply_text=excluded.reply_text,
                language=excluded.language,
                model_name=excluded.model_name,
                raw_json=excluded.raw_json
            """,
            (
                session_id, audio_sha256, captured_at, duration_s, samplerate,
                source_kind, audio_path, transcript_text, reply_text, language, model_name, raw_json,
            ),
        )
    log.info(f"Sessão {session_id} upserted (hash={audio_sha256[:8]})")


def query_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """Retorna as sessões mais recentes."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM sessions ORDER BY captured_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_relato(
    conversation_id: str,
    tipo_relato: Optional[str],
    tema: Optional[str],
    descricao: Optional[str],
    local: Optional[str],
    posicao: Optional[str],
    timestamp: str,
    confirmado: bool = False,
) -> None:
    """
    Insere ou atualiza o relato associado a uma conversa. Chamado só pelo
    extrator (voz_civica.respond.extractor), nunca pelo caminho de geração
    de resposta — é por isso que a IA nunca "lê" isso de volta pra repassar
    pra outra pessoa. `confirmado` só fica True depois que o cidadão validou.
    """
    with _conn() as con:
        con.execute(
            """
            INSERT INTO relatos (
                id, tipo_relato, tema, descricao, local, posicao,
                confirmado, criado_em, atualizado_em
            )
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                tipo_relato=excluded.tipo_relato,
                tema=excluded.tema,
                descricao=excluded.descricao,
                local=excluded.local,
                posicao=excluded.posicao,
                confirmado=excluded.confirmado,
                atualizado_em=excluded.atualizado_em
            """,
            (
                conversation_id, tipo_relato, tema, descricao, local, posicao,
                int(confirmado), timestamp, timestamp,
            ),
        )
    log.info(f"Relato {conversation_id} upserted (confirmado={confirmado})")


def query_relatos(limit: int = 100) -> List[Dict[str, Any]]:
    """Ferramenta de gerência — consulta direta ao banco, fora do caminho da IA."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM relatos ORDER BY atualizado_em DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def query_capture_runs(session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Retorna o histórico de tentativas de captura (para auditoria/depuração)."""
    with _conn() as con:
        if session_id:
            rows = con.execute(
                "SELECT * FROM capture_runs WHERE session_id=? ORDER BY started_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM capture_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"✅ Banco criado em: {DB_PATH}")
