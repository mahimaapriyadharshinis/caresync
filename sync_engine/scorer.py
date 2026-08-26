"""
Scores a ResourceUpdate for urgency.

Pure math, no network calls — this module never imports Ryu, Mininet,
or anything network-facing, so it can be unit tested on its own.
"""
from __future__ import annotations

from .models import ResourceUpdate

# How much weight congestion gets in the blended urgency number, relative
# to the resource-change magnitude. This blended score is used for
# logging/ranking only — the actual CRITICAL/CONGESTED/ROUTINE decision
# comes from policy.decide_tier(), which treats the two signals as
# separate questions rather than averaging them.
CONGESTION_WEIGHT = 0.35
MAGNITUDE_WEIGHT = 1.0 - CONGESTION_WEIGHT


def compute_magnitude(update: ResourceUpdate) -> float:
    """
    Normalize a resource change to 0..1.

    A resource hitting zero is always maximum magnitude, regardless of
    capacity — an empty ICU is an empty ICU whether the hospital has
    5 beds or 50.
    """
    if update.hit_zero:
        return 1.0

    relative_drop = max(0, -update.delta) / update.capacity
    return min(1.0, relative_drop)


def compute_urgency(magnitude: float, congestion: float) -> float:
    """Blend magnitude and congestion into one 0..1 score for logging."""
    return round(MAGNITUDE_WEIGHT * magnitude + CONGESTION_WEIGHT * congestion, 4)
