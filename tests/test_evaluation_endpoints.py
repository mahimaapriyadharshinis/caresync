from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_evaluation_latest_is_404_without_mongo():
    """MONGO_URL isn't set under the test suite, so evaluation_store has
    nothing to read from — must fail cleanly, not crash."""
    resp = client.get("/evaluation/latest")
    assert resp.status_code == 404


def test_evaluation_runs_is_empty_list_without_mongo():
    resp = client.get("/evaluation/runs")
    assert resp.status_code == 200
    assert resp.json() == []
