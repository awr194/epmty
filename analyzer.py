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
import os
from dataclasses import dataclass, field

from pydantic import BaseModel

from data_loader import BusinessModel

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


class CzechReport(BaseModel):
    feasibility_score: int
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


def verdict_for(score: int) -> str:
    if score >= 70:
        return "Strong candidate - build the MVP"
    if score >= 55:
        return "Promising with a sharp niche"
    if score >= 40:
        return "Risky - validate demand before building"
    return "Weak fit for the Czech market"


def _rationale(name: str, m: BusinessModel) -> str:
    comps = ", ".join(c.name for c in m.cz_competitors[:2]) or "no obvious incumbents"
    return {
        "Local demand": f"Demand rated {m.demand}/5 across {', '.join(m.cz_segments[:2]) or 'Czech SMEs'}.",
        "Competitive whitespace": f"Competition intensity {m.competition}/5 (e.g. {comps}).",
        "Build & ops simplicity": f"Complexity {m.complexity}/5 - {'feasible' if m.complexity <= 3 else 'tight'} for a 14-day MVP.",
        "Regulatory ease": f"Regulatory burden {m.regulatory}/5 in Czechia.",
        "Localisation moat": f"Czech-specific advantage {m.moat}/5. {m.cz_notes[:140]}".strip(),
        "Proven international traction": (
            f"~${m.mrr_usd:,} MRR internationally ({m.revenue_note})." if m.mrr_usd
            else f"Category proven abroad, exact revenue unknown. {m.revenue_note}"
        ),
    }[name]


def _legal_form(annual: int, a: CzechAssumptions) -> tuple[str, list[CostItem], str]:
    if annual < 1_000_000:
        return (
            "OSVČ in paušální režim (band 1)",
            [CostItem(item="Paušální daň (band 1)", czk_per_month=a.pausal_band1,
                      note="Covers income tax + social + health insurance")],
            "Annual revenue under 1M CZK fits band 1 of the flat-tax regime. Stay under the "
            f"{a.vat_threshold:,} CZK VAT threshold to remain a non-VAT payer. Figures are rounded - verify yearly.",
        )
    if annual < a.vat_threshold:
        band, amt = (2, a.pausal_band2) if annual < 1_500_000 else (3, a.pausal_band3)
        return (
            f"OSVČ in paušální režim (band {band}) - evaluate s.r.o. at year 2",
            [CostItem(item=f"Paušální daň (band {band})", czk_per_month=amt,
                      note="Band depends on income type and expense flat-rate")],
            "Revenue between 1M and 2M CZK: flat-tax band 2/3 applies depending on the type of income. "
            "Approaching the VAT threshold - plan for DPH registration and consider an s.r.o.",
        )
    return (
        "s.r.o. (limited company), VAT registered",
        [CostItem(item="Accountant (účetní)", czk_per_month=a.sro_accounting, note="Double-entry bookkeeping + VAT returns"),
         CostItem(item="s.r.o. fixed overhead", czk_per_month=a.sro_fixed_other, note="Registered office, bank, misc.")],
        f"Above {a.vat_threshold:,} CZK turnover VAT registration is mandatory ({a.vat_rate:.0%} DPH; B2C prices must "
        f"include VAT). Corporate income tax is {a.corporate_tax:.0%} of profit, then 15% withholding tax on dividends.",
    )


_TOOL_COST = [600, 1_200, 2_500, 4_500, 8_000]

_GTM = {
    "E-commerce Add-ons": ("Shoptet Addons marketplace + Czech e-commerce Facebook groups",
                           "E-commerce agencies & Shoptet partners"),
    "Hospitality & Gastro": ("in-person walk-ins in Prague 1-2 venues + AHR ČR (hotel & restaurant association)",
                             "POS resellers & gastro suppliers"),
    "Local Services": ("Firmy.cz + Google Business Profile + neighbourhood Facebook groups",
                       "local suppliers & industry associations"),
    "Finance & Admin": ("Czech accountant & OSVČ communities, Podnikatel.cz and LinkedIn CZ",
                        "accounting firms as resellers"),
    "Marketing & Growth": ("LinkedIn CZ + Czech digital-agency network (WebExpo, meetups)",
                           "digital agencies (white-label)"),
    "Dev & Productivity Tools": ("Czech dev communities, WebExpo, Product Hunt launch",
                                 "web agencies & hosting providers"),
    "AI Tools": ("LinkedIn CZ + Seznam Sklik ads + Czech AI meetups",
                 "digital agencies & consultants"),
    "Creator Economy": ("Czech creators on Instagram/YouTube + coach communities",
                        "course platforms & event organisers"),
    "Communities & Marketplaces": ("Expats.cz, Prague Facebook groups and Meetup.com",
                                   "relocation agencies & coworkings"),
    "D2C & Subscriptions": ("Instagram/TikTok micro-influencers + a Shoptet store + Czech farmers' markets & pop-ups",
                            "concept stores and Czech micro-influencers"),
    "Health & Wellness": ("physiotherapists, clinics and pharmacies as referrers + LinkedIn/Facebook health groups",
                          "clinics and employers' wellness programmes"),
    "Education & EdTech": ("parent Facebook groups, schools and Seznam/Google ads timed to exam season",
                           "schools and tutoring centres"),
}


def _gtm_plan(m: BusinessModel, price: int) -> list[GTMStep]:
    channel, partner = _GTM.get(m.category, _GTM["Dev & Productivity Tools"])
    seg0 = m.cz_segments[0] if m.cz_segments else "target customers"
    seg1 = m.cz_segments[1] if len(m.cz_segments) > 1 else seg0
    top_comp = m.cz_competitors[0].name if m.cz_competitors else "existing alternatives"
    return [
        GTMStep(
            title="Validate & build a Czech-first MVP", days="Days 1-4",
            actions=[
                f"Interview 10 {seg0} (call, LinkedIn, walk-in) - ask how they solve it today (e.g. {top_comp}) and what it costs them.",
                "Build a Czech landing page (Carrd/Webnode) with CZK pricing and a pre-order / waitlist form.",
                f"Ship the smallest working version of '{m.niche}' using no-code or a Streamlit/Next.js template.",
            ],
            kpi="10 interviews done, 30+ waitlist sign-ups",
        ),
        GTMStep(
            title="Distribution through local channels", days="Days 5-9",
            actions=[
                f"Launch in {channel}.",
                f"Offer 3 free pilots to {seg1} in exchange for a testimonial and a Czech case study.",
                f"Pitch a revenue-share to {partner} (typically 20-30%).",
            ],
            kpi="3 active pilots, 1 partner conversation",
        ),
        GTMStep(
            title="Convert to paying customers", days="Days 10-14",
            actions=[
                f"Switch pilots to paid at {price:,} CZK with a founding-customer discount (e.g. 30% for life).",
                "Enable Czech invoicing (Fakturoid/iDoklad API) and card + QR payments (Comgate/GoPay/Stripe).",
                "Publish the case study, request reviews on Firmy.cz/Google, and set up a weekly metric review.",
            ],
            kpi=f"First 3-5 paying customers ({3 * price:,}+ CZK MRR)",
        ),
    ]


_CATEGORY_CHECKLIST = {
    "E-commerce Add-ons": ["Shoptet API / add-on marketplace listing", "Heureka & Zboží.cz XML feed compatibility"],
    "Hospitality & Gastro": ["EU allergen labelling (Reg. 1169/2011, 14 allergens)",
                             "Accommodation/tourist fee & guest-registration compliance where relevant"],
    "Finance & Admin": ["ISDOC e-invoice format and Pohoda/Money S3 XML import",
                        "Czech tax calendar (DPH, kontrolní hlášení deadlines)"],
    "AI Tools": ["EU AI Act transparency: label AI-generated content", "Native-quality Czech prompts & outputs"],
    "Local Services": ["Trade licence (živnostenský list) for the service type", "Firmy.cz & Google Business Profile listings"],
    "D2C & Subscriptions": ["Czech-language product labelling and 14-day withdrawal terms",
                            "Packaging take-back obligations (EKO-KOM) and food/cosmetics rules where relevant"],
    "Health & Wellness": ["GDPR special-category (health) data handling",
                          "Check medical-device and health-claim rules before marketing"],
    "Education & EdTech": ["Align content with the Czech RVP curriculum / CERMAT exam formats",
                           "Parental consent for pupils' data (GDPR)"],
}


def mock_report(m: BusinessModel, a: CzechAssumptions) -> CzechReport:
    factors = _factor_scores(m)
    breakdown = [ScoreFactor(factor=k, score=factors[k], weight=w, rationale=_rationale(k, m)) for k, w in WEIGHTS.items()]
    score = round(sum(f.score * f.weight for f in breakdown))

    # Audiences
    sam = m.cz_sam
    shares = [0.5, 0.3, 0.2]
    wtp = "Medium" if m.audience == "B2B" else "Price-sensitive"
    audiences = [
        TargetAudience(segment=s, size_estimate=f"~{round(sam * shares[i]):,} potential customers (rough estimate)",
                       pain_point=m.problem, willingness_to_pay=wtp)
        for i, s in enumerate(m.cz_segments[:3] or ["Czech SMEs"])
    ]

    # Pricing & projections
    price = price_czk(m, a)
    if m.price_czk_override or m.audience == "B2C":
        tiers = [PriceTier(name="Standard", price_czk=price, billing="monthly", includes="Full service"),
                 PriceTier(name="Annual", price_czk=_nice_price(price * 0.8), billing="per month, billed yearly",
                           includes="Same as Standard, ~20% discount")]
    else:
        tiers = [PriceTier(name="Starter", price_czk=_nice_price(price * 0.6), billing="monthly, excl. VAT",
                           includes="Core features, 1 user/site"),
                 PriceTier(name="Pro", price_czk=price, billing="monthly, excl. VAT",
                           includes="Everything + integrations, priority support in Czech"),
                 PriceTier(name="Business", price_czk=_nice_price(price * 2.5), billing="monthly, excl. VAT",
                           includes="Multiple sites/users, onboarding call")]
    c12 = _customers_m12(m)
    c3, c6 = max(1, round(c12 * 0.2)), max(2, round(c12 * 0.45))
    mrr = price * c12

    legal, legal_costs, tax_notes = _legal_form(mrr * 12, a)
    costs = [
        CostItem(item="Hosting, SaaS tools & APIs", czk_per_month=_TOOL_COST[m.complexity - 1],
                 note="Scales with build complexity"),
        CostItem(item="Marketing (ads, events, content)", czk_per_month=max(3_000, round(mrr * 0.12, -2)),
                 note="~12% of month-12 MRR, min 3k CZK"),
        CostItem(item="Payment fees", czk_per_month=round(mrr * a.payment_fee), note=f"{a.payment_fee:.1%} blended"),
    ]
    if m.cogs_pct:
        costs.append(CostItem(item="Variable costs (COGS)", czk_per_month=round(mrr * m.cogs_pct),
                              note=f"{m.cogs_pct:.0%} of revenue (food, compute, SMS...)"))
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
    level = {1: "Low", 2: "Low", 3: "Medium", 4: "High", 5: "High"}[m.competition]
    competitors = [
        LocalCompetitor(
            name=c.name, kind="Local" if c.local else "International", url=c.url,
            threat=level if c.local else ("Medium" if m.moat >= 3 else "High"),
            gap=(c.note + " - " if c.note else "") + (
                "compete on a narrower niche, faster onboarding and founder-led Czech support." if c.local
                else "win on Czech language, CZK invoicing, local payment methods and integrations."),
        )
        for c in m.cz_competitors
    ]

    risks = []
    if m.competition >= 4:
        risks.append("Crowded local market - differentiation must be explicit from day one.")
    if m.regulatory >= 3:
        risks.append("Regulatory exposure - get a one-off legal review (≈5-15k CZK) before scaling.")
    if m.complexity >= 4:
        risks.append("Build scope is large for 14 days - fake the back-office manually at first (concierge MVP).")
    if m.cz_sam < 5_000:
        risks.append("Small Czech TAM - plan Slovakia (same language market) and DACH/Poland expansion early.")
    if m.audience == "B2C":
        risks.append("B2C willingness to pay is ~40% lower than in the US; watch CAC closely.")
    risks.append("All numbers are heuristic estimates - validate with real customer interviews.")

    checklist = [
        "Czech UI, onboarding e-mails and support (tykání vs. vykání tone chosen deliberately)",
        "CZK pricing; B2C prices shown including 21% DPH",
        "Czech-compliant invoices with IČO/DIČ (Fakturoid or iDoklad API)",
        "Local payments: cards + QR platba via Comgate/GoPay/Stripe",
        "GDPR + opt-in cookie consent; Czech-language terms (VOP) and privacy policy",
    ] + _CATEGORY_CHECKLIST.get(m.category, [])

    one_liner = (f"{m.name}-style '{m.niche}' for {', '.join(m.cz_segments[:2]) or 'Czech SMEs'}, "
                 f"priced at ~{price:,} CZK/month.")
    assumptions = [
        f"USD/CZK {a.usd_czk}; Czech price = US price x {a.ppp_b2b if m.audience == 'B2B' else a.ppp_b2c} (purchasing power).",
        f"Serviceable market ~{m.cz_sam:,} customers; month-12 adoption derived from demand {m.demand}/5 and competition {m.competition}/5.",
        "Tax figures are rounded 2026 approximations - verify with an accountant / financnisprava.cz.",
    ]
    if m.cz_notes:
        assumptions.append(m.cz_notes)

    return CzechReport(
        feasibility_score=score, verdict=verdict_for(score), one_liner=one_liner, score_breakdown=breakdown,
        target_audiences=audiences, unit_economics=econ, competitors=competitors, gtm_plan=_gtm_plan(m, price),
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


def _user_prompt(m: BusinessModel, baseline: CzechReport, a: CzechAssumptions) -> str:
    model_json = m.model_dump(exclude={"id"})
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
- risks, localization_checklist and assumptions as short bullet strings."""


def claude_report(m: BusinessModel, a: CzechAssumptions, api_key: str, model: str) -> CzechReport:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=300)
    baseline = mock_report(m, a)
    response = client.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(m, baseline, a)}],
        output_format=CzechReport,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's response was incomplete.")
    report = response.parsed_output
    report.feasibility_score = max(0, min(100, report.feasibility_score))
    return report


def gemini_report(m: BusinessModel, a: CzechAssumptions, api_key: str, model: str) -> CzechReport:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=300_000))
    baseline = mock_report(m, a)
    response = client.models.generate_content(
        model=model,
        contents=_user_prompt(m, baseline, a),
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
    report.feasibility_score = max(0, min(100, report.feasibility_score))
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


def _fallback(m: BusinessModel, a: CzechAssumptions, msg: str) -> AnalysisResult:
    return AnalysisResult(mock_report(m, a), "mock", [f"{msg} - showing the offline heuristic report instead."])


def _run_claude(m: BusinessModel, a: CzechAssumptions, key: str, model: str) -> AnalysisResult:
    try:
        import anthropic
    except ImportError:
        return _fallback(m, a, "`anthropic` package not installed")
    try:
        return AnalysisResult(claude_report(m, a, key, model), model)
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
    return _fallback(m, a, msg)


def _run_gemini(m: BusinessModel, a: CzechAssumptions, key: str, model: str) -> AnalysisResult:
    try:
        from google.genai import errors
    except ImportError:
        return _fallback(m, a, "`google-genai` package not installed")
    try:
        return AnalysisResult(gemini_report(m, a, key, model), model)
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
    return _fallback(m, a, msg)


def analyze(m: BusinessModel, a: CzechAssumptions | None = None, engine: str = "auto",
            anthropic_key: str | None = None, gemini_key: str | None = None,
            claude_model: str = DEFAULT_CLAUDE_MODEL, gemini_model: str = DEFAULT_GEMINI_MODEL) -> AnalysisResult:
    """Run the deep-dive. engine: 'auto', 'claude', 'gemini' or 'mock'."""
    a = a or CzechAssumptions()
    anthropic_key, gemini_key = resolve_keys(anthropic_key, gemini_key)
    engine = pick_engine(engine, anthropic_key, gemini_key)
    if engine == "claude":
        if not anthropic_key:
            return _fallback(m, a, "No ANTHROPIC_API_KEY found")
        return _run_claude(m, a, anthropic_key, claude_model)
    if engine == "gemini":
        if not gemini_key:
            return _fallback(m, a, "No GEMINI_API_KEY found")
        return _run_gemini(m, a, gemini_key, gemini_model)
    return AnalysisResult(mock_report(m, a), "mock")
