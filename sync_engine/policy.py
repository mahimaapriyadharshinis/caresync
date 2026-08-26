"""
Decision policy: turns (magnitude, congestion) into a SyncTier.

This is the three-way branch from the project's decision flow:

    resource update
          |
    magnitude large? --yes--> CRITICAL    (sync now, highest priority)
          | no
    network congested? --yes--> CONGESTED (queue, sync once link clears)
          | no
    ROUTINE (batch into next periodic interval)
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import SyncTier


@dataclass(frozen=True)
class Thresholds:
    """
    Tunable cutoffs.

    Defaults are deliberately conservative: a resource hitting zero
    always scores magnitude=1.0 (see scorer.compute_magnitude) and is
    therefore always CRITICAL regardless of these numbers.
    """

    critical_magnitude: float = 0.5
    congested_network: float = 0.6


DEFAULT_THRESHOLDS = Thresholds()


def decide_tier(
    magnitude: float,
    congestion: float,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> tuple[SyncTier, str]:
    if magnitude >= thresholds.critical_magnitude:
        return SyncTier.CRITICAL, (
            f"magnitude {magnitude:.2f} >= critical threshold "
            f"{thresholds.critical_magnitude:.2f}"
        )
    if congestion >= thresholds.congested_network:
        return SyncTier.CONGESTED, (
            f"magnitude {magnitude:.2f} below critical threshold, but "
            f"network congestion {congestion:.2f} >= "
            f"{thresholds.congested_network:.2f}"
        )
    return SyncTier.ROUTINE, (
        f"magnitude {magnitude:.2f} and congestion {congestion:.2f} both "
        "below thresholds — batched"
    )
