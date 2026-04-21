from app.session import SessionStore


def test_session_store_persists_jsonl(tmp_path) -> None:
    storage_dir = tmp_path / "sessions"

    store = SessionStore(max_turns=20, ttl_seconds=3600, storage_dir=str(storage_dir))
    session_id = "user:42/demo"
    store.append(
        session_id,
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ],
    )

    restored = SessionStore(max_turns=20, ttl_seconds=3600, storage_dir=str(storage_dir))
    history = restored.get(session_id)

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi"
