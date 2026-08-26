"""
Deterministic synthetic congestion signal for the strategy comparison:
alternates calm and busy windows so the adaptive engine's CONGESTED
tier actually gets exercised during evaluation, rather than never
firing on an otherwise-idle simulated network.
"""
from __future__ import annotations

CALM = 0.1
BUSY = 0.85
WINDOW_SECONDS = 600.0  # 10 minutes: first half calm, second half busy


def congestion_at(t: float) -> float:
    phase = t % WINDOW_SECONDS
    return BUSY if phase >= WINDOW_SECONDS / 2 else CALM
