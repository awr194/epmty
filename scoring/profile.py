"""Founder profile: hard filters and score settings for picking a shortlist (step 11).

The default profile is the project owner's (2026-09-27): basic coding skills (no-code preferred),
native Czech speaker, part-time next to a job, OSVČ (živnost) already registered, no large offline
business, goal: a side income of at least 30 000 CZK a month.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from data_loader import BusinessModel
from scoring.config import DEFAULT_WEIGHTS, CzechScoreWeights


@dataclass(frozen=True)
class FounderProfile:
    max_build_complexity: int = 3  # 1-5; 4+ needs real engineering, not no-code
    max_legal_complexity: int = 3  # 1-5; 4+ (licences, health, ČNB) is too much part-time
    excluded_types: tuple[str, ...] = ("offline_retail", "d2c_physical", "service")  # offline / own hours
    native_czech: bool = True  # Czech-language support costs a native speaker nothing extra
    target_net_czk: int = 30_000  # monthly side income wanted
    # Monthly costs on top of the net goal: paušální daň band 1 plus tools, rounded (verify each year).
    overhead_czk: int = 15_000
    max_customers: int = 300  # customers a part-time founder can sell to and support
    notes: tuple[str, ...] = field(default=(
        "basic coding - no-code preferred", "native Czech speaker", "part-time next to a job",
        "OSVČ (živnost) already registered", "no large offline business", "goal: 30 000+ CZK/month net"))

    @property
    def target_mrr_czk(self) -> int:
        return self.target_net_czk + self.overhead_czk

    def weights(self, base: CzechScoreWeights = DEFAULT_WEIGHTS) -> CzechScoreWeights:
        # A native speaker pays no language premium for support; the time it takes is covered by
        # max_customers instead.
        return replace(base, solo_founder=not self.native_czech)

    def customers_for_goal(self, price_czk: int) -> int | None:
        return math.ceil(self.target_mrr_czk / price_czk) if price_czk > 0 else None

    def rejection(self, m: BusinessModel, price_czk: int) -> tuple[str, str] | None:
        """(reason code, detail) when the model does not fit the profile, None when it does."""
        legal = m.legal_complexity or m.regulatory
        need = self.customers_for_goal(price_czk)
        checks = [
            (m.needs_rethink_for_cz, "rethink", "needs rethink for CZ"),
            (m.model_type in self.excluded_types, "type", f"type {m.model_type}"),
            (m.complexity > self.max_build_complexity, "build", f"build complexity {m.complexity}/5"),
            (legal > self.max_legal_complexity, "legal", f"legal complexity {legal}/5"),
            (need is None or need > self.max_customers, "customers", f"needs {need} customers for the goal"),
        ]
        return next(((code, detail) for failed, code, detail in checks if failed), None)


OWNER_PROFILE = FounderProfile()
