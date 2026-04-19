from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_openapi_routes_registered() -> None:
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
        paths = set(spec["paths"].keys())
        for expected in {"/chat", "/chat/stream", "/rag/ingest", "/rag/query", "/extract"}:
            assert expected in paths, f"missing route: {expected}"
