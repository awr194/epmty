"""Czech localisation & adaptation engine.

Three engines produce the same `CzechReport` schema:

  * "mock"   - deterministic heuristic engine. Runs offline and instantly, using the
               Czech hints stored on each BusinessModel plus the market assumptions
               below. Also used to compute the quick scores shown on the dashboard.
  * "claude" - Anthropic API with structured outputs.
  * "gemini" - Google Gemini API with a JSON response schema.

For both LLM engines the heuristic report is passed in as a baseline so the model
refines real numbers instead of inventing tax figures from scratch. Any API failure
falls back to "mock".
"""

from __future__ import annotations

import json
import math
import re
import os
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from data_loader import BusinessModel
from i18n import tr, tr_list

DEFAULT_CLAUDE_MODEL = "claude-opus-5"
CLAUDE_MODELS = ["claude-opus-5", "claude-sonnet-5"]
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.5-flash"]


# --------------------------------------------------------------------------- #
# Market assumptions (editable from the sidebar)
# --------------------------------------------------------------------------- #

class CzechAssumptions(BaseModel):
    usd_czk: float = 23.0
    ppp_b2b: float = 0.75  # Czech B2B price as share of US price
    ppp_b2c: float = 0.60  # Czech B2C price as share of US price
    # Paušální daň (flat tax incl. social + health insurance). Rounded 2026
    # figures - verify on financnisprava.cz before relying on them.
    pausal_band1: int = 10_000
    pausal_band2: int = 17_000
    pausal_band3: int = 27_000
    sro_accounting: int = 4_000  # external accountant, monthly
    sro_fixed_other: int = 1_000  # registered office, bank account, misc.
    corporate_tax: float = 0.21
    vat_rate: float = 0.21
    vat_threshold: int = 2_000_000  # annual turnover for mandatory VAT registration
    payment_fee: float = 0.015  # Comgate / GoPay / Stripe blended


# --------------------------------------------------------------------------- #
# Report schema (shared by both engines, used as the Claude output format)
# --------------------------------------------------------------------------- #

class ScoreFactor(BaseModel):
    factor: str
    score: int  # 0-100
    weight: float  # 0-1, weights sum to 1
    rationale: str


class TargetAudience(BaseModel):
    segment: str
    size_estimate: str
    pain_point: str
    willingness_to_pay: str


class PriceTier(BaseModel):
    name: str
    price_czk: int
    billing: str
    includes: str


class CostItem(BaseModel):
    item: str
    czk_per_month: int
    note: str


class UnitEconomics(BaseModel):
    price_tiers: list[PriceTier]
    arpu_czk: int
    customers_m3: int
    customers_m6: int
    customers_m12: int
    mrr_czk_m12: int
    monthly_costs: list[CostItem]
    total_costs_czk: int
    net_profit_czk_m12: int
    breakeven_customers: int
    legal_form: str
    tax_notes: str


class LocalCompetitor(BaseModel):
    name: str
    kind: str  # Local | International | Substitute
    url: str
    threat: str  # Low | Medium | High
    gap: str


class GTMStep(BaseModel):
    title: str
    days: str
    actions: list[str]
    kpi: str


class CzechAdjustmentItem(BaseModel):
    factor: str
    points: int  # <= 0
    detail: str


class CzechReport(BaseModel):
    feasibility_score: int
    czech_adjusted_score: int
    czech_adjustments: list[CzechAdjustmentItem]
    confidence: Literal["low", "medium", "high"]
    confidence_reason: str
    verdict: str
    one_liner: str
    score_breakdown: list[ScoreFactor]
    target_audiences: list[TargetAudience]
    unit_economics: UnitEconomics
    competitors: list[LocalCompetitor]
    gtm_plan: list[GTMStep]
    risks: list[str]
    localization_checklist: list[str]
    assumptions: list[str]


@dataclass
class AnalysisResult:
    report: CzechReport
    engine: str  # "mock" or the Claude model id
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Heuristic engine
# --------------------------------------------------------------------------- #

WEIGHTS = {
    "Local demand": 0.28,
    "Competitive whitespace": 0.20,
    "Build & ops simplicity": 0.14,
    "Regulatory ease": 0.10,
    "Localisation moat": 0.14,
    "Proven international traction": 0.14,
}


def _factor_scores(m: BusinessModel) -> dict[str, int]:
    traction = min(1.0, math.log10(m.mrr_usd) / math.log10(500_000)) if m.mrr_usd else 0.55
    return {
        "Local demand": round(100 * (m.demand - 1) / 4),
        "Competitive whitespace": round(100 * (5 - m.competition) / 4),
        "Build & ops simplicity": round(100 * (5 - m.complexity) / 4),
        "Regulatory ease": round(100 * (5 - m.regulatory) / 4),
        "Localisation moat": round(100 * (m.moat - 1) / 4),
        "Proven international traction": round(100 * traction),
    }


def _nice_price(p: float) -> int:
    """Psychological CZK price points: 49, 149, 249, 990, 1 490 ..."""
    if p < 30:
        return max(19, int(math.ceil(p / 10) * 10 - 1))
    if p < 1000:
        return int(round(p / 50) * 50 - 1) if p >= 50 else 49
    return int(round(p / 100) * 100 - 10)


def price_czk(m: BusinessModel, a: CzechAssumptions) -> int:
    if m.price_czk_override:
        return m.price_czk_override
    ppp = a.ppp_b2b if m.audience == "B2B" else a.ppp_b2c
    return _nice_price(m.price_usd * a.usd_czk * ppp)


def _customers_m12(m: BusinessModel) -> int:
    adoption = 0.002 + 0.0025 * (m.demand - 1) - 0.0015 * (m.competition - 1)
    adoption = max(0.0015, adoption)
    return max(3, round(m.cz_sam * adoption))


def quick_metrics(m: BusinessModel, a: CzechAssumptions) -> dict:
    """Cheap per-card metrics used for dashboard filters and sorting."""
    factors = _factor_scores(m)
    score = round(sum(factors[k] * w for k, w in WEIGHTS.items()))
    price = price_czk(m, a)
    customers = _customers_m12(m)
    return {"score": score, "price_czk": price, "customers_m12": customers, "mrr_czk_m12": price * customers}


def verdict_for(score: int, lang: str = "en") -> str:
    tx = _RT[lang]
    if score >= 70:
        return tx["verdict_strong"]
    if score >= 55:
        return tx["verdict_promising"]
    if score >= 40:
        return tx["verdict_risky"]
    return tx["verdict_weak"]


# Offline-report texts. Factor keys (WEIGHTS) stay English; FACTOR_LABELS translates them for display.
_RT: dict[str, dict[str, str]] = {
    "en": {
        "verdict_strong": "Strong candidate - build the MVP", "verdict_promising": "Promising with a sharp niche",
        "verdict_risky": "Risky - validate demand before building", "verdict_weak": "Weak fit for the Czech market",
        "no_incumbents": "no obvious incumbents", "czech_smes": "Czech SMEs",
        "r_demand": "Demand rated {d}/5 across {segs}.",
        "r_competition": "Competition intensity {c}/5 (e.g. {comps}).",
        "r_complexity": "Complexity {x}/5 - {fit} for a 14-day MVP.", "feasible": "feasible", "tight": "tight",
        "r_regulatory": "Regulatory burden {r}/5 in Czechia.",
        "r_moat": "Czech-specific advantage {mo}/5. {notes}",
        "r_traction": "~${mrr:,} MRR internationally ({note}).",
        "r_traction_unknown": "Category proven abroad, exact revenue unknown. {note}",
        "lf1": "OSVČ in paušální režim (band 1)", "lf1_item": "Paušální daň (band 1)",
        "lf1_note": "Covers income tax + social + health insurance",
        "lf1_tax": "Annual revenue under 1M CZK fits band 1 of the flat-tax regime. Stay under the {vat:,} CZK VAT "
                   "threshold to remain a non-VAT payer. Figures are rounded - verify yearly.",
        "lf2": "OSVČ in paušální režim (band {band}) - evaluate s.r.o. at year 2",
        "lf2_item": "Paušální daň (band {band})", "lf2_note": "Band depends on income type and expense flat-rate",
        "lf2_tax": "Revenue between 1M and 2M CZK: flat-tax band 2/3 applies depending on the type of income. "
                   "Approaching the VAT threshold - plan for DPH registration and consider an s.r.o.",
        "lf3": "s.r.o. (limited company), VAT registered",
        "lf3_acc": "Accountant (účetní)", "lf3_acc_note": "Double-entry bookkeeping + VAT returns",
        "lf3_fixed": "s.r.o. fixed overhead", "lf3_fixed_note": "Registered office, bank, misc.",
        "lf3_tax": "Above {vat:,} CZK turnover VAT registration is mandatory ({rate:.0%} DPH; B2C prices must include "
                   "VAT). Corporate income tax is {cit:.0%} of profit, then 15% withholding tax on dividends.",
        "target_customers": "target customers", "existing_alternatives": "existing alternatives",
        "g1_title": "Validate & build a Czech-first MVP", "g1_days": "Days 1-4",
        "g1_a1": "Interview 10 {seg} (call, LinkedIn, walk-in) - ask how they solve it today (e.g. {comp}) and what "
                 "it costs them.",
        "g1_a2": "Build a Czech landing page (Carrd/Webnode) with CZK pricing and a pre-order / waitlist form.",
        "g1_a3": "Ship the smallest working version of '{niche}' using no-code or a Streamlit/Next.js template.",
        "g1_kpi": "10 interviews done, 30+ waitlist sign-ups",
        "g2_title": "Distribution through local channels", "g2_days": "Days 5-9",
        "g2_a1": "Launch in {channel}.",
        "g2_a2": "Offer 3 free pilots to {seg} in exchange for a testimonial and a Czech case study.",
        "g2_a3": "Pitch a revenue-share to {partner} (typically 20-30%).",
        "g2_kpi": "3 active pilots, 1 partner conversation",
        "g3_title": "Convert to paying customers", "g3_days": "Days 10-14",
        "g3_a1": "Switch pilots to paid at {price:,} CZK with a founding-customer discount (e.g. 30% for life).",
        "g3_a2": "Enable Czech invoicing (Fakturoid/iDoklad API) and card + QR payments (Comgate/GoPay/Stripe).",
        "g3_a3": "Publish the case study, request reviews on Firmy.cz/Google, and set up a weekly metric review.",
        "g3_kpi": "First 3-5 paying customers ({mrr:,}+ CZK MRR)",
        "wtp_b2b": "Medium", "wtp_b2c": "Price-sensitive",
        "aud_size": "~{n:,} potential customers (rough estimate)",
        "t_standard": "Standard", "t_annual": "Annual", "b_monthly": "monthly",
        "b_yearly": "per month, billed yearly", "i_full": "Full service", "i_annual": "Same as Standard, ~20% discount",
        "t_starter": "Starter", "t_pro": "Pro", "t_business": "Business", "b_excl_vat": "monthly, excl. VAT",
        "i_starter": "Core features, 1 user/site", "i_pro": "Everything + integrations, priority support in Czech",
        "i_business": "Multiple sites/users, onboarding call",
        "c_tools": "Hosting, SaaS tools & APIs", "c_tools_note": "Scales with build complexity",
        "c_marketing": "Marketing (ads, events, content)", "c_marketing_note": "~12% of month-12 MRR, min 3k CZK",
        "c_fees": "Payment fees", "c_fees_note": "{fee:.1%} blended",
        "c_cogs": "Variable costs (COGS)", "c_cogs_note": "{cogs:.0%} of revenue (food, compute, SMS...)",
        "low": "Low", "medium": "Medium", "high": "High", "local": "Local", "international": "International",
        "gap_local": "compete on a narrower niche, faster onboarding and founder-led Czech support.",
        "gap_intl": "win on Czech language, CZK invoicing, local payment methods and integrations.",
        "risk_crowded": "Crowded local market - differentiation must be explicit from day one.",
        "risk_regulatory": "Regulatory exposure - get a one-off legal review (≈5-15k CZK) before scaling.",
        "risk_scope": "Build scope is large for 14 days - fake the back-office manually at first (concierge MVP).",
        "risk_tam": "Small Czech TAM - plan Slovakia (same language market) and DACH/Poland expansion early.",
        "risk_b2c": "B2C willingness to pay is ~40% lower than in the US; watch CAC closely.",
        "risk_heuristic": "All numbers are heuristic estimates - validate with real customer interviews.",
        "chk1": "Czech UI, onboarding e-mails and support (tykání vs. vykání tone chosen deliberately)",
        "chk2": "CZK pricing; B2C prices shown including 21% DPH",
        "chk3": "Czech-compliant invoices with IČO/DIČ (Fakturoid or iDoklad API)",
        "chk4": "Local payments: cards + QR platba via Comgate/GoPay/Stripe",
        "chk5": "GDPR + opt-in cookie consent; Czech-language terms (VOP) and privacy policy",
        "one_liner": "{name}-style '{niche}' for {segs}, priced at ~{price:,} CZK/month.",
        "as1": "USD/CZK {fx}; Czech price = US price x {ppp} (purchasing power).",
        "as2": "Serviceable market ~{sam:,} customers; month-12 adoption derived from demand {d}/5 and "
               "competition {c}/5.",
        "as3": "Tax figures are rounded 2026 approximations - verify with an accountant / financnisprava.cz.",
        "conf_reason": "Rule-based heuristic from 1-5 ratings and category defaults; no model-specific research.",
    },
    "ru": {
        "verdict_strong": "Сильный кандидат — стройте MVP", "verdict_promising": "Перспективно при узкой нише",
        "verdict_risky": "Рискованно — сначала проверьте спрос", "verdict_weak": "Слабо подходит для чешского рынка",
        "no_incumbents": "явных конкурентов нет", "czech_smes": "чешский малый и средний бизнес",
        "r_demand": "Спрос оценён на {d}/5 в сегментах: {segs}.",
        "r_competition": "Интенсивность конкуренции {c}/5 (например, {comps}).",
        "r_complexity": "Сложность {x}/5 — MVP за 14 дней {fit}.", "feasible": "реалистичен", "tight": "впритык",
        "r_regulatory": "Регуляторная нагрузка в Чехии: {r}/5.",
        "r_moat": "Преимущество от чешской специфики: {mo}/5. {notes}",
        "r_traction": "~${mrr:,} MRR в мире ({note}).",
        "r_traction_unknown": "Категория доказана за рубежом, точная выручка неизвестна. {note}",
        "lf1": "OSVČ в режиме paušální daň (уровень 1)", "lf1_item": "Paušální daň (уровень 1)",
        "lf1_note": "Покрывает подоходный налог, социальное и медицинское страхование",
        "lf1_tax": "Годовая выручка до 1 млн CZK подходит под 1-й уровень paušální daň. Держитесь ниже порога "
                   "НДС в {vat:,} CZK, чтобы не становиться плательщиком DPH. Цифры округлены — проверяйте каждый год.",
        "lf2": "OSVČ в режиме paušální daň (уровень {band}) — на 2-й год оцените переход в s.r.o.",
        "lf2_item": "Paušální daň (уровень {band})", "lf2_note": "Уровень зависит от типа дохода и нормы расходов",
        "lf2_tax": "Выручка от 1 до 2 млн CZK: применяется 2-й или 3-й уровень paušální daň в зависимости от типа "
                   "дохода. Порог НДС близко — заложите регистрацию плательщиком DPH и подумайте об s.r.o.",
        "lf3": "s.r.o. (ООО), плательщик НДС",
        "lf3_acc": "Бухгалтер (účetní)", "lf3_acc_note": "Двойная бухгалтерия и декларации по НДС",
        "lf3_fixed": "Постоянные расходы s.r.o.", "lf3_fixed_note": "Юридический адрес, банк, прочее",
        "lf3_tax": "При обороте выше {vat:,} CZK регистрация плательщиком НДС обязательна ({rate:.0%} DPH; цены "
                   "для B2C указываются с НДС). Налог на прибыль — {cit:.0%}, затем 15% с дивидендов.",
        "target_customers": "целевых клиентов", "existing_alternatives": "существующие альтернативы",
        "g1_title": "Проверить спрос и собрать MVP для Чехии", "g1_days": "Дни 1–4",
        "g1_a1": "Проведите 10 интервью: {seg} (звонок, LinkedIn, личный визит) — спросите, как они решают задачу "
                 "сейчас (например, {comp}) и сколько это стоит.",
        "g1_a2": "Сделайте лендинг на чешском (Carrd/Webnode) с ценами в CZK и формой предзаказа / листа ожидания.",
        "g1_a3": "Выпустите минимальную рабочую версию «{niche}» на no-code или шаблоне Streamlit/Next.js.",
        "g1_kpi": "10 интервью, 30+ записей в лист ожидания",
        "g2_title": "Дистрибуция через местные каналы", "g2_days": "Дни 5–9",
        "g2_a1": "Запуститесь здесь: {channel}.",
        "g2_a2": "Предложите 3 бесплатных пилота ({seg}) в обмен на отзыв и чешский кейс.",
        "g2_a3": "Предложите партнёрство с долей выручки ({partner}), обычно 20–30%.",
        "g2_kpi": "3 активных пилота, 1 разговор с партнёром",
        "g3_title": "Перевести в платящих клиентов", "g3_days": "Дни 10–14",
        "g3_a1": "Переведите пилоты на оплату {price:,} CZK со скидкой для первых клиентов (например, 30% навсегда).",
        "g3_a2": "Подключите чешские счета (API Fakturoid/iDoklad) и оплату картой и QR (Comgate/GoPay/Stripe).",
        "g3_a3": "Опубликуйте кейс, попросите отзывы на Firmy.cz/Google и заведите еженедельный разбор метрик.",
        "g3_kpi": "Первые 3–5 платящих клиентов ({mrr:,}+ CZK MRR)",
        "wtp_b2b": "Средняя", "wtp_b2c": "Чувствительны к цене",
        "aud_size": "~{n:,} потенциальных клиентов (грубая оценка)",
        "t_standard": "Стандарт", "t_annual": "Годовой", "b_monthly": "ежемесячно",
        "b_yearly": "в месяц при оплате за год", "i_full": "Полный сервис", "i_annual": "Как «Стандарт», скидка ~20%",
        "t_starter": "Старт", "t_pro": "Про", "t_business": "Бизнес", "b_excl_vat": "ежемесячно, без НДС",
        "i_starter": "Основные функции, 1 пользователь/сайт", "i_pro": "Всё + интеграции, приоритетная поддержка на чешском",
        "i_business": "Несколько сайтов/пользователей, онбординг-звонок",
        "c_tools": "Хостинг, SaaS-сервисы и API", "c_tools_note": "Растёт со сложностью продукта",
        "c_marketing": "Маркетинг (реклама, мероприятия, контент)", "c_marketing_note": "~12% MRR 12-го месяца, мин. 3 тыс. CZK",
        "c_fees": "Платёжные комиссии", "c_fees_note": "в среднем {fee:.1%}",
        "c_cogs": "Переменные расходы (себестоимость)", "c_cogs_note": "{cogs:.0%} выручки (еда, вычисления, SMS…)",
        "low": "Низкая", "medium": "Средняя", "high": "Высокая", "local": "Местный", "international": "Международный",
        "gap_local": "конкурируйте узкой нишей, быстрым онбордингом и поддержкой на чешском от основателя.",
        "gap_intl": "выигрывайте чешским языком, счетами в CZK, местными способами оплаты и интеграциями.",
        "risk_crowded": "Рынок переполнен — отличие должно быть явным с первого дня.",
        "risk_regulatory": "Регуляторные риски — перед масштабированием закажите разовую юр. проверку (≈5–15 тыс. CZK).",
        "risk_scope": "Объём разработки велик для 14 дней — поначалу делайте бэк-офис вручную (concierge MVP).",
        "risk_tam": "Маленький чешский рынок — заранее планируйте Словакию (тот же язык), DACH и Польшу.",
        "risk_b2c": "Готовность B2C-клиентов платить на ~40% ниже, чем в США; следите за стоимостью привлечения.",
        "risk_heuristic": "Все цифры — эвристические оценки; проверьте их интервью с реальными клиентами.",
        "chk1": "Интерфейс, письма онбординга и поддержка на чешском (осознанно выберите «ты» или «вы» — tykání/vykání)",
        "chk2": "Цены в CZK; для B2C — с учётом 21% DPH",
        "chk3": "Счета по чешским правилам с IČO/DIČ (API Fakturoid или iDoklad)",
        "chk4": "Местная оплата: карты и QR platba через Comgate/GoPay/Stripe",
        "chk5": "GDPR и согласие на cookie (opt-in); условия (VOP) и политика конфиденциальности на чешском",
        "one_liner": "«{niche}» для сегментов: {segs}; цена ~{price:,} CZK/мес.",
        "as1": "Курс USD/CZK {fx}; чешская цена = цена в США × {ppp} (с учётом покупательной способности).",
        "as2": "Доступный рынок ~{sam:,} клиентов; доля к 12-му месяцу выведена из спроса {d}/5 и конкуренции {c}/5.",
        "as3": "Налоговые цифры — округлённые оценки на 2026 год; проверяйте у бухгалтера / на financnisprava.cz.",
        "conf_reason": "Эвристика по правилам на основе оценок 1–5 и значений по умолчанию для категории; "
                       "исследования конкретной модели не было.",
    },
}

class RuText(str):
    """Russian template: after formatting, thousands separators become non-breaking spaces (1 490, not 1,490)."""

    def format(self, *args, **kwargs) -> str:
        return re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "\u00a0", str.format(self, *args, **kwargs))


_RT["ru"] = {k: RuText(v) for k, v in _RT["ru"].items()}

FACTOR_LABELS_RU = {
    "Local demand": "Местный спрос", "Competitive whitespace": "Свободная ниша",
    "Build & ops simplicity": "Простота запуска и работы", "Regulatory ease": "Регуляторная простота",
    "Localisation moat": "Преимущество локализации", "Proven international traction": "Доказанный спрос в мире",
}


def factor_label(key: str, lang: str = "en") -> str:
    return FACTOR_LABELS_RU.get(key, key) if lang == "ru" else key


def _rationale(name: str, m: BusinessModel, lang: str = "en") -> str:
    tx = _RT[lang]
    comps = ", ".join(tr(c.name, lang) for c in m.cz_competitors[:2]) or tx["no_incumbents"]
    segs = ", ".join(tr_list(m.cz_segments[:2], lang)) or tx["czech_smes"]
    note = tr(m.revenue_note, lang)
    return {
        "Local demand": tx["r_demand"].format(d=m.demand, segs=segs),
        "Competitive whitespace": tx["r_competition"].format(c=m.competition, comps=comps),
        "Build & ops simplicity": tx["r_complexity"].format(
            x=m.complexity, fit=tx["feasible"] if m.complexity <= 3 else tx["tight"]),
        "Regulatory ease": tx["r_regulatory"].format(r=m.regulatory),
        "Localisation moat": tx["r_moat"].format(mo=m.moat, notes=tr(m.cz_notes, lang)[:160]).strip(),
        "Proven international traction": (tx["r_traction"].format(mrr=m.mrr_usd, note=note) if m.mrr_usd
                                          else tx["r_traction_unknown"].format(note=note)),
    }[name]


def _legal_form(annual: int, a: CzechAssumptions, lang: str = "en") -> tuple[str, list[CostItem], str]:
    tx = _RT[lang]
    if annual < 1_000_000:
        return (tx["lf1"], [CostItem(item=tx["lf1_item"], czk_per_month=a.pausal_band1, note=tx["lf1_note"])],
                tx["lf1_tax"].format(vat=a.vat_threshold))
    if annual < a.vat_threshold:
        band, amt = (2, a.pausal_band2) if annual < 1_500_000 else (3, a.pausal_band3)
        return (tx["lf2"].format(band=band),
                [CostItem(item=tx["lf2_item"].format(band=band), czk_per_month=amt, note=tx["lf2_note"])],
                tx["lf2_tax"])
    return (tx["lf3"],
            [CostItem(item=tx["lf3_acc"], czk_per_month=a.sro_accounting, note=tx["lf3_acc_note"]),
             CostItem(item=tx["lf3_fixed"], czk_per_month=a.sro_fixed_other, note=tx["lf3_fixed_note"])],
            tx["lf3_tax"].format(vat=a.vat_threshold, rate=a.vat_rate, cit=a.corporate_tax))


_TOOL_COST = [600, 1_200, 2_500, 4_500, 8_000]

# (launch channel, partner) per category and language
_GTM = {
    "E-commerce Add-ons": {"en": ("Shoptet Addons marketplace + Czech e-commerce Facebook groups",
                                  "E-commerce agencies & Shoptet partners"),
                           "ru": ("маркетплейс дополнений Shoptet и чешские Facebook-группы по e-commerce",
                                  "e-commerce-агентствам и партнёрам Shoptet")},
    "Hospitality & Gastro": {"en": ("in-person walk-ins in Prague 1-2 venues + AHR ČR (hotel & restaurant association)",
                                    "POS resellers & gastro suppliers"),
                             "ru": ("личные визиты в заведения Праги 1–2 и AHR ČR (ассоциация отелей и ресторанов)",
                                    "реселлерам POS-систем и поставщикам для общепита")},
    "Local Services": {"en": ("Firmy.cz + Google Business Profile + neighbourhood Facebook groups",
                              "local suppliers & industry associations"),
                       "ru": ("Firmy.cz, профиль компании в Google и районные Facebook-группы",
                              "местным поставщикам и отраслевым ассоциациям")},
    "Finance & Admin": {"en": ("Czech accountant & OSVČ communities, Podnikatel.cz and LinkedIn CZ",
                               "accounting firms as resellers"),
                        "ru": ("сообщества чешских бухгалтеров и OSVČ, Podnikatel.cz и LinkedIn CZ",
                               "бухгалтерским фирмам как реселлерам")},
    "Marketing & Growth": {"en": ("LinkedIn CZ + Czech digital-agency network (WebExpo, meetups)",
                                  "digital agencies (white-label)"),
                           "ru": ("LinkedIn CZ и сеть чешских digital-агентств (WebExpo, митапы)",
                                  "digital-агентствам (white-label)")},
    "Dev & Productivity Tools": {"en": ("Czech dev communities, WebExpo, Product Hunt launch",
                                        "web agencies & hosting providers"),
                                 "ru": ("чешские сообщества разработчиков, WebExpo и запуск на Product Hunt",
                                        "веб-агентствам и хостинг-провайдерам")},
    "AI Tools": {"en": ("LinkedIn CZ + Seznam Sklik ads + Czech AI meetups", "digital agencies & consultants"),
                 "ru": ("LinkedIn CZ, реклама в Seznam Sklik и чешские AI-митапы", "digital-агентствам и консультантам")},
    "Creator Economy": {"en": ("Czech creators on Instagram/YouTube + coach communities",
                               "course platforms & event organisers"),
                        "ru": ("чешские авторы в Instagram/YouTube и сообщества коучей",
                               "платформам курсов и организаторам мероприятий")},
    "Communities & Marketplaces": {"en": ("Expats.cz, Prague Facebook groups and Meetup.com",
                                          "relocation agencies & coworkings"),
                                   "ru": ("Expats.cz, пражские Facebook-группы и Meetup.com",
                                          "релокационным агентствам и коворкингам")},
    "D2C & Subscriptions": {"en": ("Instagram/TikTok micro-influencers + a Shoptet store + Czech farmers' markets & "
                                   "pop-ups", "concept stores and Czech micro-influencers"),
                            "ru": ("микроинфлюенсеры в Instagram/TikTok, магазин на Shoptet, фермерские рынки и "
                                   "pop-up", "концепт-сторам и чешским микроинфлюенсерам")},
    "Health & Wellness": {"en": ("physiotherapists, clinics and pharmacies as referrers + LinkedIn/Facebook health "
                                 "groups", "clinics and employers' wellness programmes"),
                          "ru": ("физиотерапевты, клиники и аптеки как источники рекомендаций, группы о здоровье в "
                                 "LinkedIn/Facebook", "клиникам и корпоративным велнес-программам")},
    "Education & EdTech": {"en": ("parent Facebook groups, schools and Seznam/Google ads timed to exam season",
                                  "schools and tutoring centres"),
                           "ru": ("родительские Facebook-группы, школы и реклама в Seznam/Google к сезону экзаменов",
                                  "школам и центрам репетиторства")},
}


def _gtm_plan(m: BusinessModel, price: int, lang: str = "en") -> list[GTMStep]:
    tx = _RT[lang]
    channel, partner = _GTM.get(m.category, _GTM["Dev & Productivity Tools"])[lang]
    segs = tr_list(m.cz_segments, lang)
    seg0 = segs[0] if segs else tx["target_customers"]
    seg1 = segs[1] if len(segs) > 1 else seg0
    top_comp = tr(m.cz_competitors[0].name, lang) if m.cz_competitors else tx["existing_alternatives"]
    return [
        GTMStep(title=tx["g1_title"], days=tx["g1_days"],
                actions=[tx["g1_a1"].format(seg=seg0, comp=top_comp), tx["g1_a2"],
                         tx["g1_a3"].format(niche=tr(m.niche, lang))],
                kpi=tx["g1_kpi"]),
        GTMStep(title=tx["g2_title"], days=tx["g2_days"],
                actions=[tx["g2_a1"].format(channel=channel), tx["g2_a2"].format(seg=seg1),
                         tx["g2_a3"].format(partner=partner)],
                kpi=tx["g2_kpi"]),
        GTMStep(title=tx["g3_title"], days=tx["g3_days"],
                actions=[tx["g3_a1"].format(price=price), tx["g3_a2"], tx["g3_a3"]],
                kpi=tx["g3_kpi"].format(mrr=3 * price)),
    ]


_CATEGORY_CHECKLIST = {
    "E-commerce Add-ons": {"en": ["Shoptet API / add-on marketplace listing", "Heureka & Zboží.cz XML feed compatibility"],
                           "ru": ["API Shoptet / размещение в маркетплейсе дополнений",
                                  "Совместимость с XML-фидами Heureka и Zboží.cz"]},
    "Hospitality & Gastro": {"en": ["EU allergen labelling (Reg. 1169/2011, 14 allergens)",
                                    "Accommodation/tourist fee & guest-registration compliance where relevant"],
                             "ru": ["Маркировка аллергенов по правилам ЕС (регламент 1169/2011, 14 аллергенов)",
                                    "Туристический сбор и регистрация гостей, где это применимо"]},
    "Finance & Admin": {"en": ["ISDOC e-invoice format and Pohoda/Money S3 XML import",
                               "Czech tax calendar (DPH, kontrolní hlášení deadlines)"],
                        "ru": ["Формат электронных счетов ISDOC и XML-импорт в Pohoda/Money S3",
                               "Чешский налоговый календарь (сроки DPH и kontrolní hlášení)"]},
    "AI Tools": {"en": ["EU AI Act transparency: label AI-generated content", "Native-quality Czech prompts & outputs"],
                 "ru": ["Прозрачность по EU AI Act: маркируйте контент, созданный ИИ",
                        "Промпты и ответы на чешском уровня носителя"]},
    "Local Services": {"en": ["Trade licence (živnostenský list) for the service type",
                              "Firmy.cz & Google Business Profile listings"],
                       "ru": ["Лицензия на вид деятельности (živnostenský list)",
                              "Карточки на Firmy.cz и в профиле компании Google"]},
    "D2C & Subscriptions": {"en": ["Czech-language product labelling and 14-day withdrawal terms",
                                   "Packaging take-back obligations (EKO-KOM) and food/cosmetics rules where relevant"],
                            "ru": ["Маркировка товаров на чешском и 14 дней на возврат",
                                   "Обязательства по упаковке (EKO-KOM) и правила для еды/косметики, где применимо"]},
    "Health & Wellness": {"en": ["GDPR special-category (health) data handling",
                                 "Check medical-device and health-claim rules before marketing"],
                          "ru": ["Обработка медицинских данных как особой категории по GDPR",
                                 "Проверьте правила для медизделий и заявлений о пользе для здоровья до рекламы"]},
    "Education & EdTech": {"en": ["Align content with the Czech RVP curriculum / CERMAT exam formats",
                                  "Parental consent for pupils' data (GDPR)"],
                           "ru": ["Согласуйте контент с чешской программой RVP / форматами экзаменов CERMAT",
                                  "Согласие родителей на обработку данных учеников (GDPR)"]},
}


def mock_report(m: BusinessModel, a: CzechAssumptions, czech_context: dict | None = None,
                lang: str = "en") -> CzechReport:
    tx = _RT[lang]
    factors = _factor_scores(m)
    breakdown = [ScoreFactor(factor=factor_label(k, lang), score=factors[k], weight=w, rationale=_rationale(k, m, lang))
                 for k, w in WEIGHTS.items()]
    score = round(sum(f.score * f.weight for f in breakdown))
    segments = tr_list(m.cz_segments, lang)

    # Audiences
    sam = m.cz_sam
    shares = [0.5, 0.3, 0.2]
    wtp = tx["wtp_b2b"] if m.audience == "B2B" else tx["wtp_b2c"]
    audiences = [
        TargetAudience(segment=s, size_estimate=tx["aud_size"].format(n=round(sam * shares[i])),
                       pain_point=tr(m.problem, lang), willingness_to_pay=wtp)
        for i, s in enumerate(segments[:3] or [tx["czech_smes"]])
    ]

    # Pricing & projections
    price = price_czk(m, a)
    if m.price_czk_override or m.audience == "B2C":
        tiers = [PriceTier(name=tx["t_standard"], price_czk=price, billing=tx["b_monthly"], includes=tx["i_full"]),
                 PriceTier(name=tx["t_annual"], price_czk=_nice_price(price * 0.8), billing=tx["b_yearly"],
                           includes=tx["i_annual"])]
    else:
        tiers = [PriceTier(name=tx["t_starter"], price_czk=_nice_price(price * 0.6), billing=tx["b_excl_vat"],
                           includes=tx["i_starter"]),
                 PriceTier(name=tx["t_pro"], price_czk=price, billing=tx["b_excl_vat"], includes=tx["i_pro"]),
                 PriceTier(name=tx["t_business"], price_czk=_nice_price(price * 2.5), billing=tx["b_excl_vat"],
                           includes=tx["i_business"])]
    c12 = _customers_m12(m)
    c3, c6 = max(1, round(c12 * 0.2)), max(2, round(c12 * 0.45))
    mrr = price * c12

    legal, legal_costs, tax_notes = _legal_form(mrr * 12, a, lang)
    costs = [
        CostItem(item=tx["c_tools"], czk_per_month=_TOOL_COST[m.complexity - 1], note=tx["c_tools_note"]),
        CostItem(item=tx["c_marketing"], czk_per_month=max(3_000, round(mrr * 0.12, -2)), note=tx["c_marketing_note"]),
        CostItem(item=tx["c_fees"], czk_per_month=round(mrr * a.payment_fee), note=tx["c_fees_note"].format(fee=a.payment_fee)),
    ]
    if m.cogs_pct:
        costs.append(CostItem(item=tx["c_cogs"], czk_per_month=round(mrr * m.cogs_pct),
                              note=tx["c_cogs_note"].format(cogs=m.cogs_pct)))
    costs += legal_costs
    total = sum(c.czk_per_month for c in costs)
    fixed = total - round(mrr * (a.payment_fee + m.cogs_pct))
    margin = price * (1 - a.payment_fee - m.cogs_pct)
    breakeven = math.ceil(fixed / margin) if margin > 0 else 0

    econ = UnitEconomics(
        price_tiers=tiers, arpu_czk=price, customers_m3=c3, customers_m6=c6, customers_m12=c12, mrr_czk_m12=mrr,
        monthly_costs=costs, total_costs_czk=total, net_profit_czk_m12=mrr - total,
        breakeven_customers=breakeven, legal_form=legal, tax_notes=tax_notes,
    )

    # Competition
    level = {1: tx["low"], 2: tx["low"], 3: tx["medium"], 4: tx["high"], 5: tx["high"]}[m.competition]
    competitors = [
        LocalCompetitor(
            name=tr(c.name, lang), kind=tx["local"] if c.local else tx["international"], url=c.url,
            threat=level if c.local else (tx["medium"] if m.moat >= 3 else tx["high"]),
            gap=(tr(c.note, lang) + " — " if c.note else "") + (tx["gap_local"] if c.local else tx["gap_intl"]),
        )
        for c in m.cz_competitors
    ]

    risks = []
    if m.competition >= 4:
        risks.append(tx["risk_crowded"])
    if m.regulatory >= 3:
        risks.append(tx["risk_regulatory"])
    if m.complexity >= 4:
        risks.append(tx["risk_scope"])
    if m.cz_sam < 5_000:
        risks.append(tx["risk_tam"])
    if m.audience == "B2C":
        risks.append(tx["risk_b2c"])
    risks.append(tx["risk_heuristic"])

    checklist = [tx[f"chk{i}"] for i in range(1, 6)] + _CATEGORY_CHECKLIST.get(m.category, {}).get(lang, [])

    one_liner = tx["one_liner"].format(name=tr(m.name, lang), niche=tr(m.niche, lang),
                                       segs=", ".join(segments[:2]) or tx["czech_smes"], price=price)
    assumptions = [
        tx["as1"].format(fx=a.usd_czk, ppp=a.ppp_b2b if m.audience == "B2B" else a.ppp_b2c),
        tx["as2"].format(sam=m.cz_sam, d=m.demand, c=m.competition),
        tx["as3"],
    ]
    if m.cz_notes:
        assumptions.append(tr(m.cz_notes, lang))

    ctx = czech_context or {}
    adjustments = [CzechAdjustmentItem(factor=x["factor"], points=round(x["points"]), detail=x["detail"])
                   for x in ctx.get("adjustments", [])]
    risks += [r for r in ctx.get("recommendations", []) if r not in risks]
    return CzechReport(
        feasibility_score=score, czech_adjusted_score=ctx.get("czech_adjusted_score", score),
        czech_adjustments=adjustments, confidence="low", confidence_reason=tx["conf_reason"],
        verdict=verdict_for(score, lang), one_liner=one_liner, score_breakdown=breakdown,
        target_audiences=audiences, unit_economics=econ, competitors=competitors, gtm_plan=_gtm_plan(m, price, lang),
        risks=risks, localization_checklist=checklist, assumptions=assumptions,
    )


# --------------------------------------------------------------------------- #
# LLM engines (Claude & Gemini share the prompt)
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """You are a pragmatic Czech market-entry analyst based in Prague. You help solo founders \
decide whether a proven international small-business or micro-SaaS model can be adapted for the Czech Republic.

You know the local landscape well: Seznam (Firmy.cz, Zboží.cz, Sklik), Heureka, Shoptet and Upgates, \
Fakturoid and iDoklad, Pohoda and Money S3, Comgate and GoPay, Reservio, Qerko, Smartsupp, Ecomail, \
SmartEmailing, Jobs.cz, Expats.cz, and the way Czech OSVČ and s.r.o. businesses are taxed (paušální daň, \
21% DPH, 2M CZK VAT threshold, 21% corporate tax, 15% dividend tax).

Be concrete and honest. Prefer realistic, conservative numbers. Name real Czech incumbents only when you \
are confident they exist; otherwise describe the type of competitor. When a fact may be outdated, say \
"verify" in the text. All money is in CZK. Write in English, keeping Czech terms where they are the \
natural name (OSVČ, s.r.o., DPH, paušální daň)."""


_LANGUAGE_RULE = {
    "en": "Write all text fields in English, keeping Czech terms where they are the natural name "
          "(OSVČ, s.r.o., DPH, paušální daň).",
    "ru": "Write ALL text fields in Russian. Keep Czech proper names and legal terms as they are "
          "(OSVČ, s.r.o., DPH, paušální daň, živnost, IČO) and keep company and product names unchanged.",
}


def _user_prompt(m: BusinessModel, baseline: CzechReport, a: CzechAssumptions, lang: str = "en") -> str:
    model_json = m.model_dump(exclude={"id", "inferred_fields"})
    model_json["fields_inferred_by_rules_not_verified"] = m.inferred_fields
    return f"""Produce a Czech feasibility report for this business model.

<business_model>
{json.dumps(model_json, ensure_ascii=False, indent=2)}
</business_model>

<market_assumptions>
{a.model_dump_json(indent=2)}
</market_assumptions>

<heuristic_baseline>
This is the output of a simple rule-based scorer. Use it as a starting point: keep its arithmetic \
conventions, but correct anything unrealistic, sharpen the audiences, competitors and go-to-market steps \
with specific Czech knowledge, and explain your reasoning in the rationale fields.
{baseline.model_dump_json(indent=2)}
</heuristic_baseline>

Requirements:
- feasibility_score is 0-100 and equals the weighted sum of score_breakdown (weights sum to 1).
- target_audiences: 3 Czech segments with size estimates and willingness to pay.
- unit_economics: CZK pricing, customers at months 3/6/12, month-12 MRR, itemised monthly costs including \
the right legal form (OSVČ paušální daň vs. s.r.o.), total costs, net profit and break-even customers.
- competitors: the most relevant local incumbents plus international substitutes, each with threat level \
(Low/Medium/High) and the gap a newcomer could exploit.
- gtm_plan: exactly 3 steps covering days 1-14 to launch the MVP in Prague/Czechia, each with concrete actions and a KPI.
- czech_adjusted_score: start from feasibility_score and subtract Czech-specific frictions, one \
czech_adjustments item each (negative points, one-line detail):
  * local incumbents - weigh their real strength in Czechia, not just their number;
  * share of the Czech SAM the plan needs within 12 months (sam_estimate and sam_source; a heuristic SAM is weak evidence);
  * legal complexity - GDPR, zákon 480/2004 Sb. on commercial communications, consumer protection \
(ochrana spotřebitele), trade licence type (živnost volná / vázaná / koncese), health-care rules, ČNB licensing;
  * complex integrations the Czech market expects (Pohoda, Money S3, ABRA, Fakturoid, iDoklad, Shoptet, Upgates, \
Heureka, Zboží.cz, Sklik, Firmy.cz, QR platba, GoPay, Comgate, Bank iD, ISDOC);
  * the cost of Czech-language support for a solo founder.
  Seasonality is not a penalty: put the latest sensible launch month into risks or gtm_plan.
  The rule-based values in the baseline (czech_adjusted_score, czech_adjustments) are a starting point - \
correct them where you know better. Fields listed in fields_inferred_by_rules_not_verified are guesses.
- confidence: "low", "medium" or "high" - how much the assessment rests on specific, current knowledge of \
the Czech market rather than assumptions. Explain in confidence_reason (1-2 sentences).
- risks, localization_checklist and assumptions as short bullet strings.
- Language: {_LANGUAGE_RULE[lang]}"""


def claude_report(m: BusinessModel, a: CzechAssumptions, api_key: str, model: str,
                  czech_context: dict | None = None, lang: str = "en") -> CzechReport:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=300)
    baseline = mock_report(m, a, czech_context, lang)
    response = client.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(m, baseline, a, lang)}],
        output_format=CzechReport,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's response was incomplete.")
    return _clamp(response.parsed_output)


def gemini_report(m: BusinessModel, a: CzechAssumptions, api_key: str, model: str,
                  czech_context: dict | None = None, lang: str = "en") -> CzechReport:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=300_000))
    baseline = mock_report(m, a, czech_context, lang)
    response = client.models.generate_content(
        model=model,
        contents=_user_prompt(m, baseline, a, lang),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=CzechReport,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if response.prompt_feedback and response.prompt_feedback.block_reason:
        raise RuntimeError(f"Gemini blocked the request ({response.prompt_feedback.block_reason}).")
    finish = response.candidates[0].finish_reason if response.candidates else None
    if finish is not None and getattr(finish, "name", str(finish)) not in ("STOP", "FINISH_REASON_UNSPECIFIED"):
        raise RuntimeError(f"Gemini stopped early ({getattr(finish, 'name', finish)}).")
    report = response.parsed
    if not isinstance(report, CzechReport):
        report = CzechReport.model_validate_json(response.text)
    return _clamp(report)


def _clamp(report: CzechReport) -> CzechReport:
    report.feasibility_score = max(0, min(100, report.feasibility_score))
    report.czech_adjusted_score = max(0, min(100, report.czech_adjusted_score))
    return report


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def resolve_keys(anthropic_key: str | None = None, gemini_key: str | None = None) -> tuple[str | None, str | None]:
    return (
        anthropic_key or os.environ.get("ANTHROPIC_API_KEY") or None,
        gemini_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None,
    )


def pick_engine(engine: str, anthropic_key: str | None, gemini_key: str | None) -> str:
    """Resolve 'auto' to a concrete engine: Claude first, then Gemini, then offline."""
    if engine != "auto":
        return engine
    if anthropic_key:
        return "claude"
    if gemini_key:
        return "gemini"
    return "mock"


_FALLBACK_MSG = {"en": "{msg} - showing the offline heuristic report instead.",
                 "ru": "{msg} — показан офлайн-отчёт (эвристика)."}


# Russian versions of the engine error messages below (regex on the English text -> template).
_MSG_RU = [
    (r"`(\S+)` package not installed", r"не установлен пакет `\1`"),
    (r"Invalid (Anthropic|Gemini) API key", r"неверный API-ключ \1"),
    (r"Anthropic rate limit hit - try again in a minute", "превышен лимит запросов Anthropic — повторите через минуту"),
    (r"Anthropic API error (.*)", r"ошибка API Anthropic \1"),
    (r"Could not reach the Anthropic API", "не удалось связаться с API Anthropic"),
    (r"Claude analysis failed \((.*)\)", r"анализ Claude не удался (\1)"),
    (r"Gemini rate limit / free-tier quota hit - try again later",
     "превышен лимит или бесплатная квота Gemini — повторите позже"),
    (r"Gemini model '(.*)' not found", r"модель Gemini «\1» не найдена"),
    (r"Gemini API error (.*)", r"ошибка API Gemini \1"),
    (r"Gemini server error (\S+) - try again", r"ошибка сервера Gemini \1 — повторите попытку"),
    (r"Gemini analysis failed \((.*)\)", r"анализ Gemini не удался (\1)"),
    (r"No (ANTHROPIC_API_KEY|GEMINI_API_KEY) found", r"не найден \1"),
]


def _localize_msg(msg: str, lang: str) -> str:
    if lang != "ru":
        return msg
    for pattern, ru in _MSG_RU:
        if re.fullmatch(pattern, msg, flags=re.S):
            return re.sub(pattern, ru, msg, flags=re.S)
    return msg


def _fallback(m: BusinessModel, a: CzechAssumptions, msg: str, ctx: dict | None = None,
              lang: str = "en") -> AnalysisResult:
    text = _FALLBACK_MSG[lang].format(msg=_localize_msg(msg, lang))
    return AnalysisResult(mock_report(m, a, ctx, lang), "mock", [text[0].upper() + text[1:]])


def _run_claude(m: BusinessModel, a: CzechAssumptions, key: str, model: str, ctx: dict | None,
                lang: str = "en") -> AnalysisResult:
    try:
        import anthropic
    except ImportError:
        return _fallback(m, a, "`anthropic` package not installed", ctx, lang)
    try:
        return AnalysisResult(claude_report(m, a, key, model, ctx, lang), model)
    except anthropic.AuthenticationError:
        msg = "Invalid Anthropic API key"
    except anthropic.RateLimitError:
        msg = "Anthropic rate limit hit - try again in a minute"
    except anthropic.APIStatusError as e:
        msg = f"Anthropic API error {e.status_code}: {getattr(e, 'message', e)}"
    except anthropic.APIConnectionError:
        msg = "Could not reach the Anthropic API"
    except Exception as e:  # validation / refusal / unexpected output
        msg = f"Claude analysis failed ({e})"
    return _fallback(m, a, msg, ctx, lang)


def _run_gemini(m: BusinessModel, a: CzechAssumptions, key: str, model: str, ctx: dict | None,
                lang: str = "en") -> AnalysisResult:
    try:
        from google.genai import errors
    except ImportError:
        return _fallback(m, a, "`google-genai` package not installed", ctx, lang)
    try:
        return AnalysisResult(gemini_report(m, a, key, model, ctx, lang), model)
    except errors.ClientError as e:
        if e.code in (401, 403) or "API_KEY_INVALID" in str(e) or "API key not valid" in str(e):
            msg = "Invalid Gemini API key"
        elif e.code == 429:
            msg = "Gemini rate limit / free-tier quota hit - try again later"
        elif e.code == 404:
            msg = f"Gemini model '{model}' not found"
        else:
            msg = f"Gemini API error {e.code}: {e.message}"
    except errors.ServerError as e:
        msg = f"Gemini server error {e.code} - try again"
    except Exception as e:  # network / validation / blocked output
        msg = f"Gemini analysis failed ({e})"
    return _fallback(m, a, msg, ctx, lang)


def analyze(m: BusinessModel, a: CzechAssumptions | None = None, engine: str = "auto",
            anthropic_key: str | None = None, gemini_key: str | None = None,
            claude_model: str = DEFAULT_CLAUDE_MODEL, gemini_model: str = DEFAULT_GEMINI_MODEL,
            czech_context: dict | None = None, lang: str = "en") -> AnalysisResult:
    """Run the deep-dive. engine: 'auto', 'claude', 'gemini' or 'mock'.
    czech_context: the rule-based Czech score (scoring.czech.to_context) given to the LLM as a baseline."""
    ctx = czech_context
    a = a or CzechAssumptions()
    anthropic_key, gemini_key = resolve_keys(anthropic_key, gemini_key)
    engine = pick_engine(engine, anthropic_key, gemini_key)
    if engine == "claude":
        if not anthropic_key:
            return _fallback(m, a, "No ANTHROPIC_API_KEY found", ctx, lang)
        return _run_claude(m, a, anthropic_key, claude_model, ctx, lang)
    if engine == "gemini":
        if not gemini_key:
            return _fallback(m, a, "No GEMINI_API_KEY found", ctx, lang)
        return _run_gemini(m, a, gemini_key, gemini_model, ctx, lang)
    return AnalysisResult(mock_report(m, a, ctx, lang), "mock")
