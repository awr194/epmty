"""Czech-market enrichment layer on top of the base business-model records.

Base records (data_loader.py, curated_more.py, catalog/) stay untouched. Czech-specific
fields come from two places, in this order of precedence:

  1. data/cz_enrichment.json - hand-maintained overlay keyed by model name;
  2. inference rules below   - conservative defaults derived from existing fields.

Every field filled by inference is listed in `inferred_fields`, so the UI and the audit
script can tell verified data from guesses.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from market.nace_sam import cache_info, sam_for_nace
from market.original_cz import load_results as load_original_cz

ENRICHMENT_PATH = Path(__file__).parent / "data" / "cz_enrichment.json"

# Base-record fields the overlay may correct (only via reviewed patches).
BASE_OVERRIDES = ("country", "url", "cz_segments")

ModelType = Literal["saas", "marketplace", "d2c_physical", "offline_retail", "service", "media_ads"]
MODEL_TYPES: tuple[str, ...] = ("saas", "marketplace", "d2c_physical", "offline_retail", "service", "media_ads")

# Integrations recognised in free text; the scoring config decides which ones count as "complex".
KNOWN_INTEGRATIONS = [
    "Pohoda", "Money S3", "ABRA", "Fakturoid", "iDoklad", "Shoptet", "Upgates", "Heureka", "Zboží.cz",
    "Sklik", "Firmy.cz", "QR platba", "GoPay", "Comgate", "Bank iD", "ISDOC", "ARES", "Sreality",
]
_INTEGRATION_ALIASES = {"Zboží.cz": ["Zboží", "Zbozi"], "Bank iD": ["Bankovní identita", "Bank iD"]}

# Categories whose customers expect Czech-language support.
LOCAL_CATEGORIES = {"Local Services", "Hospitality & Gastro", "Finance & Admin", "Health & Wellness",
                     "Education & EdTech"}


class Incumbent(BaseModel):
    name: str
    strength: int = 2  # 1 = minor, 2 = established, 3 = dominant
    note: str = ""
    url: str = ""


class Seasonality(BaseModel):
    peak_months: list[int] = Field(default_factory=list)  # 1-12
    launch_by_month: Optional[int] = None  # latest month to launch before the peak


# --------------------------------------------------------------------------- #
# Inference rules
# --------------------------------------------------------------------------- #

def infer_model_type(row: dict) -> str:
    rev = row.get("revenue_model", "").lower()
    cat = row.get("category", "")
    cogs = row.get("cogs_pct", 0.0) or 0.0
    if rev in ("retail", "food sales") or "franchise" in rev:
        return "offline_retail"
    if "advertising" in rev:  # audience media paid by advertisers (6AM City, Nextdoor)
        return "media_ads"
    if "margin on resale" in rev:  # buys and resells goods (e.g. used cars)
        return "d2c_physical"
    if "per-service" in rev or "revenue share" in rev:
        return "service"
    # Payment processors charge per transaction too, but they are software, not marketplaces.
    if any(k in rev for k in ("commission", "per booking", "per-booking", "pay-per-lead", "lead fees", "per-lead",
                              "service fee", "buyer protection", "margin on orders", "listing fee", "per-ticket",
                              "tip-based", "affiliate")):
        return "marketplace"
    if cat == "D2C & Subscriptions" or "product sales" in rev or "subscription box" in rev or (
            cogs >= 0.5 and cat in ("Local Services", "Hospitality & Gastro")):
        return "d2c_physical"
    if cogs >= 0.45 or any(k in rev for k in ("margin on hours", "margin on placements", "tuition", "lesson",
                                              "per-service", "per-test", "outsourced", "package fees",
                                              "markup on hourly")):
        return "service"
    return "saas"


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_SEASON_WORDS = {"spring": [3, 4, 5], "summer": [6, 7, 8], "christmas": [11, 12], "autumn": [9, 10, 11],
                 "winter": [12, 1, 2]}


def _month_range(a: int, b: int) -> list[int]:
    return list(range(a, b + 1)) if a <= b else list(range(a, 13)) + list(range(1, b + 1))


def infer_seasonality(text: str) -> Seasonality | None:
    """Parse phrases like 'May-September', 'Jan-April', 'seasonal (spring)', 'Christmas'."""
    t = text.lower()
    if not any(k in t for k in ("season", "peak", "christmas")):
        return None
    months: list[int] = []
    for a, b in re.findall(r"\b([a-z]{3})[a-z]*\s*[-–]\s*([a-z]{3})[a-z]*\b", t):
        if a in _MONTHS and b in _MONTHS:
            months += _month_range(_MONTHS[a], _MONTHS[b])
    for word, ms in _SEASON_WORDS.items():
        if word in t:
            months += ms
    months = sorted(set(months))
    if not months:
        return None
    first = months[0] if not (1 in months and 12 in months) else min(m for m in months if m >= 9)
    return Seasonality(peak_months=months, launch_by_month=(first - 3) % 12 + 1)  # two months of lead time


def infer_integrations(row: dict) -> list[str]:
    """Integrations mentioned in the model's own text (not in competitor lists)."""
    text = " ".join([row.get("niche", ""), row.get("problem", ""), row.get("cz_notes", ""),
                     " ".join(row.get("cz_segments", [])), " ".join(row.get("tech_stack", []))])
    found = []
    for name in KNOWN_INTEGRATIONS:
        if any(alias.lower() in text.lower() for alias in [name] + _INTEGRATION_ALIASES.get(name, [])):
            found.append(name)
    return found


def infer_czech_support(row: dict) -> bool:
    return row.get("audience") == "B2C" or row.get("category") in LOCAL_CATEGORIES or row.get("moat", 0) >= 4


def incumbents_from_competitors(row: dict) -> list[Incumbent]:
    """Hand-named local competitors become incumbents (strength 2, to verify).
    Category-landscape placeholders and international players are skipped."""
    out = []
    for c in row.get("cz_competitors", []):
        c = c if isinstance(c, dict) else c.model_dump()
        if not c.get("local", True) or "Category landscape" in c.get("note", ""):
            continue
        out.append(Incumbent(name=c["name"], strength=2, url=c.get("url", ""),
                             note=f"{c.get('note') + ' - ' if c.get('note') else ''}strength to verify"))
    return out


# --------------------------------------------------------------------------- #
# Overlay + defaults
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def load_overlay(path: str = str(ENRICHMENT_PATH)) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("models", {})


def apply_cz_defaults(row: dict, overlay: dict[str, dict] | None = None) -> dict:
    """Return a copy of `row` with every Czech field set (overlay first, inference second)."""
    row = dict(row)
    over = (load_overlay() if overlay is None else overlay).get(row["name"], {})
    inferred: list[str] = []
    for field in BASE_OVERRIDES:  # reviewed corrections to base metadata (see patches/)
        if field in over:
            row[field] = over[field]

    def put(field: str, infer):
        if field in over:
            row[field] = over[field]
        elif row.get(field) is None:  # base records never carry these fields
            value = infer()
            row[field] = value
            if value not in (None, [], {}, "") and value != Seasonality().model_dump():
                inferred.append(field)

    put("model_type", lambda: infer_model_type(row))
    put("local_incumbents", lambda: [i.model_dump() for i in incumbents_from_competitors(row)])
    put("legal_complexity", lambda: row.get("regulatory", 1))
    put("required_integrations", lambda: infer_integrations(row))
    put("seasonality", lambda: (infer_seasonality(row.get("cz_notes", "")) or Seasonality()).model_dump())
    put("czech_support_required", lambda: infer_czech_support(row))
    put("price_includes_vat", lambda: row.get("audience") == "B2C")
    put("target_nace", list)
    row["sam_segment"] = over.get("sam_segment", "total")
    if "sam_estimate" not in over and row["target_nace"]:
        # Firms per CZ-NACE from the ČSÚ register beat the heuristic when codes are known.
        nace_sam = sam_for_nace(row["target_nace"], row["sam_segment"])
        if nace_sam:
            row["sam_estimate"] = nace_sam
            row["sam_source"] = (f"{cache_info()}, CZ-NACE {', '.join(row['target_nace'])}, "
                                 f"segment '{row['sam_segment']}'")
    put("sam_estimate", lambda: row.get("cz_sam"))
    put("sam_source", lambda: "heuristic estimate (unverified)")
    for field in ("take_rate", "gmv_estimate", "needs_rethink_for_cz"):
        if field in over:
            row[field] = over[field]

    # Is the original already offered in Czechia? Hand-checked overlay beats the website check.
    if "original_available_in_cz" in over:
        row["original_available_in_cz"] = over["original_available_in_cz"]
        row["original_cz_evidence"] = over.get("original_cz_evidence", [])
        row["original_cz_source"] = over.get("original_cz_source", "manual (cz_enrichment.json)")
    elif (check := load_original_cz().get(row["name"])) is not None:
        row["original_available_in_cz"] = check["status"]
        row["original_cz_evidence"] = check.get("evidence", [])
        row["original_cz_source"] = f"site check {check.get('checked_at', '')}".strip()

    row["inferred_fields"] = inferred
    return row
