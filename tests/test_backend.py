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


def test_ambulance_recommends_the_hospital_with_most_capacity():
    # other tests in this file leave icu_beds state behind for other
    # hospital IDs in the same shared store, so assert this pair's
    # relative order rather than an absolute top pick
    client.post("/hospitals/amb-test-x/update", json={"resource": "icu_beds", "new_value": 2, "capacity": 10})
    client.post("/hospitals/amb-test-y/update", json={"resource": "icu_beds", "new_value": 9, "capacity": 10})

    resp = client.get("/ambulance/recommend", params={"resource": "icu_beds"})
    assert resp.status_code == 200
    ranked = resp.json()["ranked_hospitals"]
    values = {h["hospital_id"]: h["remaining"] for h in ranked}
    assert values["amb-test-x"] == 2
    assert values["amb-test-y"] == 9

    ids_in_order = [h["hospital_id"] for h in ranked]
    assert ids_in_order.index("amb-test-y") < ids_in_order.index("amb-test-x")


def test_ambulance_never_recommends_a_hospital_at_zero():
    # the store is shared across this whole test file, so assert the
    # local invariant (these two never show up) rather than a global
    # 404 — some other test may well have left a different hospital
    # with nonzero capacity for this resource
    client.post("/hospitals/amb-zero-a/update", json={"resource": "ventilators", "new_value": 0, "capacity": 5})
    client.post("/hospitals/amb-zero-b/update", json={"resource": "ventilators", "new_value": 0, "capacity": 5})

    resp = client.get("/ambulance/recommend", params={"resource": "ventilators"})
    if resp.status_code == 200:
        recommended_ids = {h["hospital_id"] for h in resp.json()["ranked_hospitals"]}
        assert "amb-zero-a" not in recommended_ids
        assert "amb-zero-b" not in recommended_ids
    else:
        assert resp.status_code == 404
