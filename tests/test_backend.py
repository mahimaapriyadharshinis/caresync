from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_first_update_has_no_baseline_and_is_routine():
    resp = client.post(
        "/hospitals/hosp-a/update",
        json={"resource": "icu_beds", "new_value": 8, "capacity": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["tier"] == "routine"


def test_update_dropping_icu_to_zero_is_critical():
    client.post(
        "/hospitals/hosp-b/update",
        json={"resource": "icu_beds", "new_value": 3, "capacity": 10},
    )
    resp = client.post(
        "/hospitals/hosp-b/update",
        json={"resource": "icu_beds", "new_value": 0, "capacity": 10},
    )
    assert resp.json()["tier"] == "critical"
    assert resp.json()["previous_value"] == 3


def test_congestion_can_be_set_and_affects_decision():
    client.put("/network/congestion/hosp-c", params={"value": 0.9})
    client.post(
        "/hospitals/hosp-c/update",
        json={"resource": "icu_beds", "new_value": 14, "capacity": 20},
    )
    resp = client.post(
        "/hospitals/hosp-c/update",
        json={"resource": "icu_beds", "new_value": 13, "capacity": 20},
    )
    assert resp.json()["tier"] == "congested"


def test_unknown_hospital_returns_404():
    resp = client.get("/hospitals/does-not-exist")
    assert resp.status_code == 404


def test_decisions_log_is_populated():
    client.post(
        "/hospitals/hosp-d/update",
        json={"resource": "ventilators", "new_value": 5, "capacity": 5},
    )
    resp = client.get("/decisions")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_value_exceeding_capacity_is_rejected_with_400():
    resp = client.post(
        "/hospitals/hosp-e/update",
        json={"resource": "icu_beds", "new_value": 12, "capacity": 10},
    )
    assert resp.status_code == 400


def test_invalid_congestion_value_is_rejected():
    resp = client.put("/network/congestion/hosp-a", params={"value": 1.5})
    assert resp.status_code == 400


def test_known_hospital_triggers_controller_hook_without_raising():
    """hospA is in deployment_config.HOSPITAL_MACS, so this exercises the
    controller-notification branch. CONTROLLER_URL is unset in tests, so
    the client is disabled and this must be a silent no-op."""
    client.post("/hospitals/hospA/update", json={"resource": "icu_beds", "new_value": 3, "capacity": 10})
    resp = client.post("/hospitals/hospA/update", json={"resource": "icu_beds", "new_value": 0, "capacity": 10})
    assert resp.json()["tier"] == "critical"
