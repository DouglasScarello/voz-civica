from voz_civica.session import database


def test_upsert_session_idempotent_by_audio_hash(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()

    kwargs = dict(
        session_id="s1",
        audio_sha256="deadbeef",
        captured_at="2026-01-01T00:00:00Z",
        duration_s=1.5,
        samplerate=16000,
        source_kind="file",
        audio_path="/tmp/x.wav",
        transcript_text="oi",
        language="pt",
        model_name="small",
        raw_json="{}",
    )
    database.upsert_session(**kwargs)
    kwargs["transcript_text"] = "oi, atualizado"
    database.upsert_session(**kwargs)

    sessions = database.query_sessions()
    assert len(sessions) == 1
    assert sessions[0]["transcript_text"] == "oi, atualizado"


def test_capture_runs_logs_every_attempt_including_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()

    database.log_capture_run(session_id="s1", started_at="2026-01-01T00:00:00Z", status="ok")
    database.log_capture_run(
        session_id="", started_at="2026-01-01T00:00:01Z", status="error", error_message="mic desconectado"
    )

    runs = database.query_capture_runs()
    assert len(runs) == 2
    statuses = {r["status"] for r in runs}
    assert statuses == {"ok", "error"}
