from voz_civica.session.collector import SessionCollector


def test_save_and_load_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr("voz_civica.session.collector.SESSIONS_ROOT", tmp_path / "sessions")

    collector = SessionCollector()
    payload = {"_meta": {"session_id": "abc123", "captured_at": "2026-01-01T00:00:00Z"}, "transcript": {"text": "oi"}}
    collector.save(session_id="abc123", payload=payload)

    loaded = collector.load_snapshot("abc123")
    assert loaded == payload


def test_list_snapshots_returns_saved_ids(monkeypatch, tmp_path):
    monkeypatch.setattr("voz_civica.session.collector.SESSIONS_ROOT", tmp_path / "sessions")

    collector = SessionCollector()
    collector.save(session_id="s1", payload={"_meta": {}})
    collector.save(session_id="s2", payload={"_meta": {}})

    ids = collector.list_snapshots()
    assert set(ids) == {"s1", "s2"}
