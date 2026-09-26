"""Data-quality audit (step 6). Read-only: writes a report and a proposed patch, never edits data.

    python scripts/audit_data.py            # -> reports/audit.md + patches/data_fixes.json
    python scripts/apply_data_patch.py      # review first; applies the patch to data/cz_enrichment.json

Checks:
  1. identical (templated) Czech segment lists shared by several models;
  2. suspicious metadata - URL that doesn't match the model name, country vs. URL domain mismatch,
     unknown / remote origin;
  3. models tied to a post-Soviet fiscal / e-document / platform ecosystem -> needs_rethink_for_cz;
  4. enrichment gaps - model_type, VAT treatment and SAM only inferred, MRR not comparable with the type.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer import CzechAssumptions  # noqa: E402
from data_loader import BusinessModel, load_curated  # noqa: E402
from scoring.metrics import MRR_STATUS_LABELS, derived_metrics  # noqa: E402

REPORT = ROOT / "reports" / "audit.md"
PATCH = ROOT / "patches" / "data_fixes.json"

TLD_COUNTRY = {".ru": "Russia", ".ua": "Ukraine", ".by": "Belarus", ".kz": "Kazakhstan", ".pl": "Poland",
               ".sk": "Slovakia", ".de": "Germany", ".fr": "France", ".nl": "Netherlands", ".at": "Austria",
               ".co.uk": "UK", ".jp": "Japan", ".co.il": "Israel", ".co.in": "India", ".com.br": "Brazil",
               ".mx": "Mexico", ".cl": "Chile", ".co.nz": "New Zealand", ".com.au": "Australia", ".sa": "Saudi Arabia"}

POST_SOVIET = {"Russia", "Ukraine", "Belarus", "Kazakhstan"}
# Local systems a model depends on that have no Czech equivalent to plug into.
ECOSYSTEM_MARKERS = {
    "fiscal": "fiscal / cash-register law", "cash register": "fiscal / cash-register law",
    "fiscalisation": "fiscal / cash-register law", "electronic invoices": "national e-document (EDO) rules",
    "document exchange": "national e-document (EDO) rules", "sole proprietors": "Russian ИП tax regimes",
    "outsourced accounting": "Russian accounting standards (RSBU)", "inventory & retail": "Russian marking & fiscal integrations",
    "freelance contractors": "Russian self-employed (НПД) regime", "vk communities": "VK platform (not used in CZ)",
    "telegram channel": "Telegram ad market (niche in CZ)", "wildberries": "Wildberries/Ozon marketplaces (absent in CZ)",
    "ozon": "Wildberries/Ozon marketplaces (absent in CZ)", "restaurant management & pos": "Russian EGAIS / fiscal integrations",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{4,}", text.lower())}


def _url_matches_name(name: str, host: str) -> bool:
    """'nomadlist.com' ~ 'Nomad List', 'getjobber.com' ~ 'Jobber', 'kit.com' ~ 'Kit (formerly ConvertKit)'."""
    compact = re.sub(r"[^a-z0-9]", "", name.lower())
    labels = host.split(".")
    core = labels[-3] if len(labels) >= 3 and labels[-2] in ("co", "com") else labels[-2] if len(labels) >= 2 else host
    return core in compact or any(t in host for t in _tokens(name)) or any(
        compact.startswith(core[:k]) for k in (4,) if len(core) >= 4)


def templated_segments(models: list[BusinessModel], min_group: int = 3) -> list[tuple[tuple[str, ...], list[str]]]:
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for m in models:
        if m.cz_segments:
            groups[tuple(m.cz_segments)].append(m.name)
    return sorted(((k, v) for k, v in groups.items() if len(v) >= min_group), key=lambda kv: -len(kv[1]))


def suspicious_metadata(m: BusinessModel) -> list[str]:
    issues = []
    if m.country in ("Unknown", "Global / remote", "North America"):
        issues.append(f"origin country is vague ('{m.country}')")
    host = urlparse(m.url).netloc.lower().removeprefix("www.")
    if host:
        if "archetype" not in m.name.lower() and not _url_matches_name(m.name, host):
            issues.append(f"URL host '{host}' doesn't match the model name")
        for tld, country in TLD_COUNTRY.items():
            if host.endswith(tld) and m.country != country:
                issues.append(f"URL domain {tld} suggests {country}, but country is {m.country}")
                break
    elif m.source == "Curated":
        issues.append("no URL")
    if (re.search(r"\bczech|přijímačky|svj|sklik|seznam\b", m.name.lower()) and "archetype" not in m.name.lower()
            and m.country != "Global / remote"):
        issues.append(f"Czech-specific idea attributed to origin '{m.country}' - origin should describe the "
                      "reference model, not the Czech idea")
    return issues


def ecosystem_dependency(m: BusinessModel) -> list[str]:
    if m.country not in POST_SOVIET:
        return []
    text = f"{m.name} {m.niche} {m.problem} {m.cz_notes}".lower()
    return sorted({reason for marker, reason in ECOSYSTEM_MARKERS.items() if marker in text})


def main() -> None:
    a = CzechAssumptions()
    models = load_curated()
    fixes: list[dict] = []
    out = [f"# Data audit - {date.today().isoformat()}", "",
           f"{len(models)} curated models. This report changes nothing; proposed fixes are in "
           "`patches/data_fixes.json` and are applied only by `scripts/apply_data_patch.py`.", ""]

    # 1 --------------------------------------------------------------- templated segments
    groups = templated_segments(models)
    out += ["## 1. Templated Czech segments", "",
            f"{len(groups)} identical segment lists are shared by 3+ models "
            f"({sum(len(v) for _, v in groups)} models). Most come from category defaults filled in when a model "
            "had no hand-written segments - they describe the category, not the model.", ""]
    for segs, names in groups:
        out.append(f"- **{'; '.join(segs)}** ({len(names)}): {', '.join(sorted(names))}")
    out.append("")

    # 2 --------------------------------------------------------------- suspicious metadata
    flagged = [(m, suspicious_metadata(m)) for m in models]
    flagged = [(m, i) for m, i in flagged if i]
    out += ["## 2. Suspicious metadata", "", f"{len(flagged)} models.", "",
            "| Model | Country | URL | Issues |", "|---|---|---|---|"]
    out += [f"| {m.name} | {m.country} | {m.url or '-'} | {'; '.join(i)} |" for m, i in flagged]
    out.append("")

    # 3 --------------------------------------------------------------- ecosystem dependency
    deps = [(m, ecosystem_dependency(m)) for m in models]
    deps = [(m, r) for m, r in deps if r]
    out += ["## 3. Tied to a post-Soviet fiscal / e-document / platform ecosystem", "",
            "Proposed `needs_rethink_for_cz: true` - the model only works on top of systems that do not exist "
            "in Czechia. The idea may still transfer, but the product must be rebuilt around Czech equivalents.", "",
            "| Model | Country | Dependency |", "|---|---|---|"]
    for m, reasons in deps:
        out.append(f"| {m.name} | {m.country} | {'; '.join(reasons)} |")
        if not m.needs_rethink_for_cz:
            fixes.append({"model": m.name, "field": "needs_rethink_for_cz", "old": False, "new": True,
                          "reason": "; ".join(reasons)})
    out.append("")

    # 4 --------------------------------------------------------------- enrichment gaps
    only_inferred = lambda f: [m for m in models if f in m.inferred_fields]  # noqa: E731
    not_comparable = []
    for m in models:
        d = derived_metrics(m, a)
        if not d.comparable:
            not_comparable.append((m, d.mrr_status))
    out += ["## 4. Enrichment gaps", "",
            f"- `model_type` only inferred by rules: **{len(only_inferred('model_type'))}** models "
            "(verify in `data/cz_enrichment.json`).",
            f"- VAT treatment (`price_includes_vat`) only inferred from B2B/B2C: "
            f"**{len(only_inferred('price_includes_vat'))}** models.",
            f"- SAM is still the unverified heuristic: **{len(only_inferred('sam_estimate'))}** models.",
            f"- MRR not comparable with the model type: **{len(not_comparable)}** models:", ""]
    by_status: dict[str, list[str]] = defaultdict(list)
    for m, status in not_comparable:
        by_status[status].append(m.name)
    for status, names in by_status.items():
        out.append(f"  - *{MRR_STATUS_LABELS[status]}* ({len(names)}): {', '.join(sorted(names))}")
    out.append("")

    # proposed metadata fixes (reviewed by hand, see _MANUAL)
    by_name = {m.name: m for m in models}
    for name, field, new, reason in _MANUAL:
        if name not in by_name:
            raise SystemExit(f"_MANUAL refers to unknown model: {name}")
        old = getattr(by_name[name], field)
        if old != new:
            fixes.append({"model": name, "field": field, "old": old, "new": new, "reason": reason})
    out += ["## Proposed patch", "", f"{len(fixes)} changes in `patches/data_fixes.json`:", "",
            "| Model | Field | New value | Reason |", "|---|---|---|---|"]
    out += [f"| {f['model']} | {f['field']} | {json.dumps(f['new'], ensure_ascii=False)} | {f['reason']} |" for f in fixes]

    REPORT.parent.mkdir(exist_ok=True)
    PATCH.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    PATCH.write_text(json.dumps({"generated": date.today().isoformat(), "fixes": fixes}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"Report: {REPORT.relative_to(ROOT)} | patch: {len(fixes)} changes -> {PATCH.relative_to(ROOT)}")
    print(f"  templated segment groups: {len(groups)} | suspicious metadata: {len(flagged)} | "
          f"ecosystem-dependent: {len(deps)} | MRR not comparable: {len(not_comparable)}")


# Hand-reviewed corrections to base metadata: (model, field, new value, reason). The current value is
# filled in as "old" when the patch is generated. Nothing is applied until apply_data_patch.py runs.
_GASTRO_TEMPLATE = "templated gastro/STR segments don't describe this model"
_FIN_TEMPLATE = "templated 'OSVČ / accounting firms' segments don't fit a consumer product"
_MANUAL: list[tuple[str, str, object, str]] = [
    ("Czech for Foreigners: Exam-prep Marketplace", "country", "Global / remote",
     "Czech-specific idea; italki (Hong Kong) is only the inspiration, not the origin of this model"),
    ("Czech for Foreigners: Exam-prep Marketplace", "url", "",
     "italki.com is a general tutoring marketplace, not a reference for this exam-prep niche"),
    ("AirDNA", "cz_segments", ["Short-term rental investors", "Prague Airbnb hosts", "Property-management companies"],
     _GASTRO_TEMPLATE),
    ("PriceLabs", "cz_segments", ["Prague Airbnb hosts & co-hosts", "Apartment-management companies",
                                  "Small hotels & pensions"], _GASTRO_TEMPLATE),
    ("Guesty", "cz_segments", ["Short-term rental management companies", "Prague co-hosting agencies"],
     _GASTRO_TEMPLATE),
    ("Lodgify", "cz_segments", ["Holiday-home owners (chaty, chalupy)", "Pensions (penziony)", "Apartment managers"],
     _GASTRO_TEMPLATE),
    ("Travelline", "cz_segments", ["Small hotels", "Pensions (penziony)", "Spa hotels"], _GASTRO_TEMPLATE),
    ("Aviasales", "cz_segments", ["Czech leisure travellers", "Budget travellers & students"], _GASTRO_TEMPLATE),
    ("La Belle Assiette", "cz_segments", ["Private chefs", "Households hosting dinners", "Corporate event organisers"],
     _GASTRO_TEMPLATE),
    ("Withlocals", "cz_segments", ["Prague tour guides", "Tourists wanting private tours"], _GASTRO_TEMPLATE),
    ("Kitopi", "cz_segments", ["Restaurant brands wanting delivery reach", "Dark-kitchen operators"], _GASTRO_TEMPLATE),
    ("Luckin Coffee", "cz_segments", ["Urban commuters", "Office workers", "Students"], _GASTRO_TEMPLATE),
    ("Kopi Kenangan", "cz_segments", ["Urban commuters", "Office workers", "Students"], _GASTRO_TEMPLATE),
    ("Cofix", "cz_segments", ["Price-sensitive coffee drinkers", "Students", "Office workers"], _GASTRO_TEMPLATE),
    ("Chai Point", "cz_segments", ["Offices wanting hot-drink service", "Commuters"], _GASTRO_TEMPLATE),
    ("Dodo Pizza", "cz_segments", ["Families ordering delivery", "Office lunch orders", "Franchisees"], _GASTRO_TEMPLATE),
    ("Cleo", "cz_segments", ["Young adults 18-30", "Students managing money"], _FIN_TEMPLATE),
    ("Farewill", "cz_segments", ["Adults 40+ planning inheritance", "Families going through probate (dědické řízení)"],
     _FIN_TEMPLATE),
    ("Banki.ru", "cz_segments", ["Consumers comparing loans & deposits", "Banks & lenders buying leads"], _FIN_TEMPLATE),
    ("PolicyBazaar", "cz_segments", ["Consumers comparing insurance", "Insurers & brokers buying leads"], _FIN_TEMPLATE),
    ("Money Fellows", "cz_segments", ["Young savers", "Communities saving together"], _FIN_TEMPLATE),
]


if __name__ == "__main__":
    main()
