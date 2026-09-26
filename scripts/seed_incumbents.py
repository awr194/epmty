"""Seed draft local_incumbents (step 5) into data/cz_enrichment.json.

Only the groups agreed in the task are seeded; every entry is marked "to verify" and gets the
default strength 2. Hand-named Czech competitors already on a record are kept (merged, not replaced).
Writes reports/models_without_incumbents.md listing models that still have no competitor data.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cz_enrichment import incumbents_from_competitors  # noqa: E402

OVERLAY = ROOT / "data" / "cz_enrichment.json"
REPORT = ROOT / "reports" / "models_without_incumbents.md"
TV = "draft - to verify"


def inc(name, url="", note=""):
    return {"name": name, "strength": 2, "url": url, "note": f"{note + '; ' if note else ''}{TV}"}


TENDERS = [inc("Hlídač státu", "https://www.hlidacstatu.cz", "free public-contract data"),
           inc("Tender Arena", "https://www.tenderarena.cz", "e-tendering platform"),
           inc("Věstník veřejných zakázek", "https://www.vestnikverejnychzakazek.cz", "official procurement bulletin")]
SHOPTET_WATCHDOG = [inc("Shoptet built-in 'Hlídací pes'", "https://www.shoptet.cz", "native back-in-stock watchdog")]
BOOKING = {"Reservio": inc("Reservio", "https://www.reservio.cz"),
           "Booksy": inc("Booksy", "https://booksy.com", "presence in CZ to verify"),
           "Bookio": inc("Bookio", "https://www.bookio.com")}
EXAMS = [inc("Scio", "https://www.scio.cz", "mock tests & prep courses"),
         inc("Umíme to", "https://www.umimeto.org", "adaptive practice"),
         inc("CERMAT materials", "https://prijimacky.cermat.cz", "free official past papers")]
GRANTS = [inc("Grant consultancies (dotační poradenské agentury)", "", "many small agencies, success fees"),
          inc("Subsidy portals (e.g. dotaceeu.cz)", "https://www.dotaceeu.cz", "official EU-funds information")]
INVOICING = [inc("Fakturoid", "https://www.fakturoid.cz"), inc("iDoklad", "https://www.idoklad.cz")]

GROUPS: dict[str, list[dict]] = {
    "Public Tender Alerts for SMEs (GovSpend archetype)": TENDERS,
    "Back-in-Stock Alerts (Shopify app archetype)": SHOPTET_WATCHDOG,
    **{n: list(BOOKING.values()) for n in [
        "Salon Booking with No-show Deposits (Fresha archetype)", "Treatwell", "YCLIENTS", "DIKIDI",
        "Acuity Scheduling"]},
    "Booksy": [BOOKING["Reservio"], BOOKING["Bookio"]],   # a model is not its own incumbent
    "Bookio": [BOOKING["Reservio"], BOOKING["Booksy"]],
    # the task names the AI tutor; the others are its direct peers in Czech exam prep
    **{n: EXAMS for n in ["AI Tutor for Přijímačky & Maturita (Khanmigo archetype)", "Seneca Learning",
                          "Descomplica", "Foxford (Фоксфорд)", "Physics Wallah"]},
    "AI Grant & Subsidy Finder (Instrumentl archetype)": GRANTS,
    **{n: INVOICING for n in [
        "Freelancer Invoicing (Invoice Ninja archetype)", "FreshBooks", "FreeAgent", "Wave", "sevDesk",
        "SuperFaktúra", "Kontur.Elba (Контур.Эльба)", "inFakt", "Xero", "freee", "Conta Azul"]},
}


def main() -> None:
    from data_loader import load_curated  # imported late: the overlay is rewritten below

    base = {m.name: m for m in load_curated()}
    data = json.loads(OVERLAY.read_text(encoding="utf-8"))
    for name, seeds in GROUPS.items():
        if name not in base:
            raise SystemExit(f"Unknown model name: {name}")
        existing = [i.model_dump() for i in incumbents_from_competitors(base[name].model_dump())]
        merged = {i["name"].lower(): i for i in existing}
        merged.update({i["name"].lower(): i for i in seeds})  # seeded entries win on name clash
        data["models"].setdefault(name, {})["local_incumbents"] = list(merged.values())
    OVERLAY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    import cz_enrichment
    cz_enrichment.load_overlay.cache_clear()
    missing = [m for m in load_curated() if not m.local_incumbents]
    REPORT.parent.mkdir(exist_ok=True)
    lines = ["# Models without local competitor data", "",
             f"{len(missing)} of {len(base)} models have no named Czech incumbents (their competitor list is empty "
             "or only a category landscape). The Czech score applies no incumbent penalty to them, which favours "
             "models with missing data - fill these in `data/cz_enrichment.json`.", "",
             "| Model | Category | Country |", "|---|---|---|"]
    lines += [f"| {m.name} | {m.category} | {m.country} |" for m in sorted(missing, key=lambda x: (x.category, x.name))]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Seeded {len(GROUPS)} models; {len(missing)} models without incumbents -> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
