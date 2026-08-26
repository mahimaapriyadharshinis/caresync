"""
Runs the Phase 5 comparison: replays one synthetic event trace through
continuous, periodic, and adaptive sync, and reports the communication
overhead and staleness for each — the numbers the project's own
Grafana dashboard is built to visualize.

    python3 -m evaluation.run_comparison [--events N] [--seed N] [--mongo-url URL]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

from simulation.event_generator import GeneratorConfig, SyntheticEventGenerator

from .network_conditions import congestion_at
from .strategies import StrategyResult, run_adaptive, run_continuous, run_periodic


def summarize(result: StrategyResult) -> dict:
    return {
        "strategy": result.name,
        "messages_sent": result.messages_sent,
        "avg_staleness_seconds": round(result.avg_staleness, 2),
        "max_staleness_seconds": round(result.max_staleness, 2),
        "events_delivered": len(result.deliveries),
    }


def run(num_events: int, seed: int, num_hospitals: int) -> dict:
    generator = SyntheticEventGenerator(GeneratorConfig(seed=seed))
    events = list(generator.stream(num_events))

    continuous = run_continuous(events, num_hospitals)
    periodic = run_periodic(events, num_hospitals)
    adaptive = run_adaptive(events, num_hospitals, congestion_at)

    critical = [d for d in adaptive.deliveries if d.tier == "critical"]
    periodic_by_key = {(d.hospital_id, d.resource, d.event_time): d.staleness for d in periodic.deliveries}
    periodic_staleness_for_critical_events = [
        periodic_by_key[(d.hospital_id, d.resource, d.event_time)] for d in critical
    ]

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "num_events": num_events,
        "seed": seed,
        "num_hospitals": num_hospitals,
        "strategies": [summarize(continuous), summarize(periodic), summarize(adaptive)],
        "critical_events": len(critical),
        "adaptive_critical_avg_staleness_seconds": (
            round(sum(d.staleness for d in critical) / len(critical), 2) if critical else 0.0
        ),
        # what periodic sync would have made those SAME critical events
        # wait, for comparison — the headline number
        "periodic_would_be_staleness_for_critical_events_seconds": (
            round(sum(periodic_staleness_for_critical_events) / len(periodic_staleness_for_critical_events), 2)
            if periodic_staleness_for_critical_events
            else 0.0
        ),
    }


async def _persist(result: dict, mongo_url: str) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(mongo_url)
    await client["caresync"]["evaluation_runs"].insert_one(dict(result))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare continuous, periodic, and adaptive sync strategies.")
    parser.add_argument("--events", type=int, default=300)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--hospitals", type=int, default=3)
    parser.add_argument("--mongo-url", default=None, help="e.g. mongodb://localhost:27017")
    args = parser.parse_args()

    result = run(args.events, args.seed, args.hospitals)
    print(json.dumps(result, indent=2))

    if args.mongo_url:
        asyncio.run(_persist(result, args.mongo_url))
        print(f"\nPersisted to {args.mongo_url} (caresync.evaluation_runs)")


if __name__ == "__main__":
    main()
