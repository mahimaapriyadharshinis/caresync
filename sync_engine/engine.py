"""
The Adaptive Sync Engine.

Wires scorer + policy into the single entry point the rest of the system
calls. This is the "PROCESSING: AI / CORE ALGORITHM" box in the project
architecture — it evaluates resource change, congestion, and urgency,
and hands the decision to the SDN controller layer.
"""
from __future__ import annotations

from .models import ResourceUpdate, ScoreResult
from .policy import DEFAULT_THRESHOLDS, Thresholds, decide_tier
from .scorer import compute_magnitude, compute_urgency


class AdaptiveSyncEngine:
    def __init__(self, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> None:
        self.thresholds = thresholds

    def evaluate(self, update: ResourceUpdate, congestion: float) -> ScoreResult:
        """Score one resource update and decide how urgently to sync it.

        `congestion` is a 0..1 reading of current network load, supplied
        by the caller (controller/congestion_monitor.py polls this from
        the switches in the real deployment).
        """
        if not 0.0 <= congestion <= 1.0:
            raise ValueError("congestion must be within 0..1")

        magnitude = compute_magnitude(update)
        urgency = compute_urgency(magnitude, congestion)
        tier, reason = decide_tier(magnitude, congestion, self.thresholds)

        return ScoreResult(
            magnitude=magnitude,
            congestion=round(congestion, 4),
            urgency=urgency,
            tier=tier,
            reason=reason,
        )
