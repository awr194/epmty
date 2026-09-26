"""Tunable weights for the Czech-adjusted score. The sidebar sliders map 1:1 onto these fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CzechScoreWeights:
    # Local incumbents: points per unit of strength (1-3), capped.
    incumbent_points_per_strength: float = 4.0
    incumbent_cap: float = 25.0

    # Share of SAM needed within 12 months: no penalty up to `sam_soft`; just above it a fixed
    # `sam_step_penalty` (crossing the threshold must be visible), plus a linear part up to
    # `sam_soft_penalty` at `sam_hard`, then a steep extra penalty (full at 2x sam_hard).
    sam_soft: float = 0.02
    sam_hard: float = 0.10
    sam_step_penalty: float = 3.0
    sam_soft_penalty: float = 8.0
    sam_hard_penalty: float = 20.0
    # A heuristic SAM (no ČSÚ / official source) is a guess: its share penalty is scaled by this.
    heuristic_sam_confidence: float = 0.75

    # Legal complexity 1-5: points per level above 1.
    legal_points_per_level: float = 3.0

    # Integrations that need significant work (accounting systems, identity, e-invoicing).
    complex_integrations: tuple[str, ...] = ("Pohoda", "Money S3", "ABRA", "Bank iD", "ISDOC")
    integration_points_each: float = 3.0
    integration_cap: float = 12.0

    # Czech-language support is a real cost for a solo founder. Full penalty where customers are
    # many or non-technical (B2C, local SMB categories); reduced for other B2B segments, whose
    # customers usually accept English or occasional support.
    solo_founder: bool = True
    czech_support_penalty: float = 3.0
    czech_support_penalty_other_b2b: float = 1.0

    # Months of lead time before a seasonal peak (used for the recommendation only).
    season_lead_months: int = 2


DEFAULT_WEIGHTS = CzechScoreWeights()
