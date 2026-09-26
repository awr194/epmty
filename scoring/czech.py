"""Czech-adjusted feasibility score.

The base feasibility score (analyzer.quick_metrics) says how good a model is in general.
czech_adjusted_score() subtracts Czech-specific frictions and explains each deduction,
so the card can show exactly what moved the number.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field

from data_loader import BusinessModel
from scoring.config import DEFAULT_WEIGHTS, CzechScoreWeights
from scoring.metrics import DerivedMetrics


@dataclass(frozen=True)
class Adjustment:
    factor: str
    points: float  # <= 0: points removed from the base score
    detail: str


@dataclass(frozen=True)
class CzechScore:
    base: int
    score: int
    breakdown: list[Adjustment] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def delta(self) -> int:
        return self.score - self.base


_MONTHS_RU = ["", "янв.", "февр.", "март", "апр.", "май", "июнь", "июль", "авг.", "сент.", "окт.", "нояб.", "дек."]
_MONTHS_RU_FULL = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
                   "октября", "ноября", "декабря"]

# Texts shown in the breakdown. Factor names are also the keys used by tests (English).
_TX = {
    "en": {
        "incumbents": "Local incumbents", "incumbents_d": "{n} incumbent(s): {names}{more}", "more": " +{n} more",
        "share": "Share of market needed", "share_d": "{c:,} customers = {s:.1%} of SAM within 12 months",
        "legal": "Legal complexity", "legal_d": "Level {lvl}/5",
        "integr": "Complex integrations",
        "support": "Czech-language support", "support_d": "Customers expect support in Czech",
        "season": "Seasonal (peak {peaks}): launch by {month}.",
        "not_comparable": "MRR is not comparable with SaaS models for this model type - judge it on unit economics.",
        "no_sam": "No SAM estimate - market-share check skipped.",
    },
    "ru": {
        "incumbents": "Местные конкуренты", "incumbents_d": "конкурентов: {n} — {names}{more}", "more": " и ещё {n}",
        "share": "Нужная доля рынка", "share_d": "{c:,} клиентов = {s:.1%} SAM за 12 месяцев",
        "legal": "Юридическая сложность", "legal_d": "Уровень {lvl}/5",
        "integr": "Сложные интеграции",
        "support": "Поддержка на чешском", "support_d": "Клиенты ждут поддержки на чешском",
        "season": "Сезонность (пик: {peaks}): запускайтесь до {month}.",
        "not_comparable": "Для этого типа модели MRR не сопоставим с SaaS — оценивайте по юнит-экономике.",
        "no_sam": "Нет оценки размера рынка — проверка доли рынка пропущена.",
    },
}


def _incumbents(m: BusinessModel, w: CzechScoreWeights, tx: dict) -> Adjustment | None:
    if not m.local_incumbents:
        return None
    total = sum(max(1, min(3, i.strength)) for i in m.local_incumbents)
    pts = min(w.incumbent_cap, total * w.incumbent_points_per_strength)
    names = ", ".join(f"{i.name} ({i.strength})" for i in m.local_incumbents[:4])
    more = tx["more"].format(n=len(m.local_incumbents) - 4) if len(m.local_incumbents) > 4 else ""
    return Adjustment(tx["incumbents"], -pts, tx["incumbents_d"].format(n=len(m.local_incumbents), names=names,
                                                                          more=more))


def _sam_share(metrics: DerivedMetrics, w: CzechScoreWeights, tx: dict) -> Adjustment | None:
    share = metrics.sam_share_12m
    if share is None or share <= w.sam_soft:
        return None
    if share <= w.sam_hard:
        pts = w.sam_soft_penalty * (share - w.sam_soft) / (w.sam_hard - w.sam_soft)
    else:
        pts = w.sam_soft_penalty + w.sam_hard_penalty * min(1.0, (share - w.sam_hard) / w.sam_hard)
    return Adjustment(tx["share"], -pts, tx["share_d"].format(c=metrics.customers_needed, s=share))


def _legal(m: BusinessModel, w: CzechScoreWeights, tx: dict) -> Adjustment | None:
    level = m.legal_complexity if m.legal_complexity is not None else m.regulatory
    if level <= 1:
        return None
    return Adjustment(tx["legal"], -(level - 1) * w.legal_points_per_level, tx["legal_d"].format(lvl=level))


def _integrations(m: BusinessModel, w: CzechScoreWeights, tx: dict) -> Adjustment | None:
    hard = [i for i in m.required_integrations if i in w.complex_integrations]
    if not hard:
        return None
    return Adjustment(tx["integr"], -min(w.integration_cap, len(hard) * w.integration_points_each), ", ".join(hard))


def _support(m: BusinessModel, w: CzechScoreWeights, tx: dict) -> Adjustment | None:
    if not (m.czech_support_required and w.solo_founder):
        return None
    return Adjustment(tx["support"], -w.czech_support_penalty, tx["support_d"])


def _recommendations(m: BusinessModel, metrics: DerivedMetrics, w: CzechScoreWeights, tx: dict,
                     lang: str) -> list[str]:
    recs = []
    peaks = m.seasonality.peak_months
    if peaks:
        launch = m.seasonality.launch_by_month
        if launch is None:
            first = min(p for p in peaks if p >= 9) if (1 in peaks and 12 in peaks) else peaks[0]
            launch = (first - 1 - w.season_lead_months) % 12 + 1
        abbr = _MONTHS_RU if lang == "ru" else calendar.month_abbr
        full = _MONTHS_RU_FULL if lang == "ru" else calendar.month_name
        recs.append(tx["season"].format(peaks=", ".join(abbr[p] for p in peaks), month=full[launch]))
    if not metrics.comparable:
        recs.append(tx["not_comparable"])
    if metrics.sam_share_12m is None and metrics.comparable:
        recs.append(tx["no_sam"])
    return recs


def czech_adjusted_score(base: int, m: BusinessModel, metrics: DerivedMetrics,
                         weights: CzechScoreWeights = DEFAULT_WEIGHTS, lang: str = "en") -> CzechScore:
    """Base feasibility minus Czech frictions, clamped to 0-100, with a per-factor breakdown.
    `lang` ('en' | 'ru') only changes the explanatory texts, never the numbers."""
    tx = _TX.get(lang, _TX["en"])
    breakdown = [adj for adj in (_incumbents(m, weights, tx), _sam_share(metrics, weights, tx),
                                 _legal(m, weights, tx), _integrations(m, weights, tx), _support(m, weights, tx))
                 if adj is not None]
    score = round(max(0.0, min(100.0, base + sum(a.points for a in breakdown))))
    return CzechScore(base=base, score=score, breakdown=breakdown,
                      recommendations=_recommendations(m, metrics, weights, tx, lang))


def to_context(result: CzechScore, m: BusinessModel, metrics: DerivedMetrics) -> dict:
    """Plain-dict view of the rule-based Czech score, passed to the LLM prompt and the offline report."""
    return {
        "base_score": result.base,
        "czech_adjusted_score": result.score,
        "adjustments": [{"factor": a.factor, "points": a.points, "detail": a.detail} for a in result.breakdown],
        "recommendations": result.recommendations,
        "model_type": m.model_type,
        "mrr_status": metrics.mrr_status,
        "customers_needed": metrics.customers_needed,
        "sam_share_12m": metrics.sam_share_12m,
        "sam_estimate": m.sam_estimate,
        "sam_source": m.sam_source,
    }
