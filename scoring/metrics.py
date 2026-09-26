"""Metrics derived from a model's type, price and market size (step 2 of the Czech scoring)."""

from __future__ import annotations

from dataclasses import dataclass

from analyzer import CzechAssumptions, quick_metrics
from data_loader import BusinessModel

# mrr_status values
COMPARABLE = "comparable"  # SaaS / service: recurring revenue = customers x price
MARKETPLACE_GMV = "marketplace_gmv"  # marketplace with take rate and GMV: MRR = take_rate x GMV
MARKETPLACE_NO_GMV = "marketplace_no_gmv"  # marketplace without GMV data: not comparable
NOT_RECURRING = "not_recurring"  # physical D2C / offline retail: revenue is sales, not MRR
MEDIA_ADS = "media_ads"  # advertising-funded media: revenue follows audience size, not customers x price

MRR_STATUS_LABELS = {
    COMPARABLE: "Recurring revenue (comparable)",
    MARKETPLACE_GMV: "Marketplace: take rate x GMV",
    MARKETPLACE_NO_GMV: "Marketplace without GMV data - MRR not comparable",
    NOT_RECURRING: "Physical / retail sales - not SaaS MRR",
    MEDIA_ADS: "Advertising revenue - depends on audience, not SaaS MRR",
}


@dataclass(frozen=True)
class DerivedMetrics:
    price_czk: int
    mrr_heuristic_czk: int  # the base engine's month-12 figure, always available for reference
    mrr_czk_m12: int | None  # comparable month-12 MRR; None when not comparable
    mrr_status: str
    customers_needed: int | None  # customers required to reach the month-12 MRR (saas/service)
    sam_share_12m: float | None  # customers_needed / SAM

    @property
    def comparable(self) -> bool:
        return self.mrr_czk_m12 is not None


def derived_metrics(m: BusinessModel, a: CzechAssumptions, quick: dict | None = None) -> DerivedMetrics:
    q = quick or quick_metrics(m, a)
    price, heuristic = q["price_czk"], q["mrr_czk_m12"]
    model_type = m.model_type or "saas"

    if model_type in ("d2c_physical", "offline_retail"):
        mrr, status = None, NOT_RECURRING
    elif model_type == "media_ads":
        mrr, status = None, MEDIA_ADS
    elif model_type == "marketplace":
        if m.take_rate is not None and m.gmv_estimate:
            mrr, status = round(m.take_rate * m.gmv_estimate), MARKETPLACE_GMV
        else:
            mrr, status = None, MARKETPLACE_NO_GMV
    else:
        mrr, status = heuristic, COMPARABLE

    customers = round(mrr / price) if status == COMPARABLE and price > 0 else None
    share = customers / m.sam_estimate if customers is not None and m.sam_estimate else None
    return DerivedMetrics(price_czk=price, mrr_heuristic_czk=heuristic, mrr_czk_m12=mrr, mrr_status=status,
                          customers_needed=customers, sam_share_12m=share)
