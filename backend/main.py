"""
FastAPI backend — the northbound entry point hospitals report resource
changes through. This is the "INPUT: DATA COLLECTION" box in the
project architecture: every POST here becomes a ResourceUpdate, which
the Adaptive Sync Engine scores before deciding whether — and how
urgently — to push it across the network.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from sync_engine import AdaptiveSyncEngine, ResourceUpdate

from .congestion import CongestionProvider
from .schemas import HospitalStateOut, ResourceUpdateIn, SyncDecisionOut
from .storage import get_store

app = FastAPI(title="CARESync Backend", version="0.1.0")

engine = AdaptiveSyncEngine()
store = get_store()
congestion = CongestionProvider()


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
