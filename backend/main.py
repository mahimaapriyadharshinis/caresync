"""
FastAPI backend — the northbound entry point hospitals report resource
changes through. This is the "INPUT: DATA COLLECTION" box in the
project architecture: every POST here becomes a ResourceUpdate, which
the Adaptive Sync Engine scores before deciding whether — and how
urgently — to push it across the network.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from ambulance.router import choose_hospital, rank_hospitals
from deployment_config import HOSPITAL_MACS
from sync_engine import AdaptiveSyncEngine, ResourceType, ResourceUpdate, SyncTier

from . import evaluation_store
from .congestion import CongestionProvider
from .controller_client import ControllerClient
from .schemas import HospitalStateOut, ResourceUpdateIn, SyncDecisionOut
from .storage import get_store

app = FastAPI(title="CARESync Backend", version="0.1.0")

engine = AdaptiveSyncEngine()
store = get_store()
congestion = CongestionProvider()
controller = ControllerClient()


@app.post("/hospitals/{hospital_id}/update", response_model=SyncDecisionOut)
async def report_update(hospital_id: str, payload: ResourceUpdateIn) -> SyncDecisionOut:
    state = await store.get_state(hospital_id)
    previous_value = state.get(payload.resource.value, payload.new_value)

    try:
        update = ResourceUpdate(
            hospital_id=hospital_id,
            resource=payload.resource,
            previous_value=previous_value,
            new_value=payload.new_value,
            capacity=payload.capacity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    score = engine.evaluate(update, congestion.get(hospital_id))

    mac = HOSPITAL_MACS.get(hospital_id)
    if mac is not None:
        if score.tier == SyncTier.CRITICAL:
            controller.mark_critical(mac)
        else:
            controller.clear_critical(mac)

    await store.set_value(hospital_id, payload.resource.value, payload.new_value, payload.capacity)
    await store.record_decision(update, score)

    return SyncDecisionOut(
        hospital_id=hospital_id,
        resource=payload.resource,
        previous_value=previous_value,
        new_value=payload.new_value,
        magnitude=score.magnitude,
        congestion=score.congestion,
        urgency=score.urgency,
        tier=score.tier,
        reason=score.reason,
        timestamp=update.timestamp,
    )


@app.get("/hospitals/{hospital_id}", response_model=HospitalStateOut)
async def get_hospital(hospital_id: str) -> HospitalStateOut:
    state = await store.get_state(hospital_id)
    if not state:
        raise HTTPException(status_code=404, detail="unknown hospital or no updates yet")
    return HospitalStateOut(hospital_id=hospital_id, resources=state)


@app.get("/decisions")
async def list_decisions(limit: int = 50) -> list[dict]:
    return await store.recent_decisions(limit)


@app.put("/network/congestion/{hospital_id}")
async def set_congestion(hospital_id: str, value: float) -> dict:
    if not 0.0 <= value <= 1.0:
        raise HTTPException(status_code=400, detail="value must be within 0..1")
    congestion.set(hospital_id, value)
    return {"hospital_id": hospital_id, "congestion": value}


@app.get("/evaluation/latest")
async def evaluation_latest() -> dict:
    result = await evaluation_store.latest_run()
    if result is None:
        raise HTTPException(status_code=404, detail="no evaluation runs yet — run evaluation/run_comparison.py")
    return result


@app.get("/evaluation/runs")
async def evaluation_runs(limit: int = 20) -> list[dict]:
    return await evaluation_store.recent_runs(limit)


@app.get("/ambulance/recommend")
async def ambulance_recommend(resource: ResourceType) -> dict:
    """The scenario from the project's own motivation slide, made
    concrete: given the latest known state of every hospital, which one
    should an ambulance be routed to for `resource`?"""
    states = await store.all_states()
    ranked = rank_hospitals(states, resource.value)
    if not ranked:
        raise HTTPException(
            status_code=404,
            detail=f"no hospital currently has capacity for {resource.value}",
        )
    return {
        "resource": resource.value,
        "recommended_hospital": choose_hospital(states, resource.value),
        "ranked_hospitals": [{"hospital_id": h, "remaining": v} for h, v in ranked],
    }
