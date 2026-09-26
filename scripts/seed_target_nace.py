"""Seed/refresh: write target_nace (and a few manual B2C SAMs) into data/cz_enrichment.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "data" / "cz_enrichment.json"
d = json.loads(p.read_text(encoding="utf-8"))
models = d["models"]

REST = ["561", "563"]
ESHOP = ["4791"]
HEALTH = ["862"]
# Most gyms register as 93.11 (sports facilities), not 93.13 (fitness, only ~270 subjects).
FITNESS = ["9311", "9313", "8551"]
TRADES = ["432", "433"]

MAP = {
    # gastro
    "QR Table Ordering & Pay (Sunday/Mr Yum archetype)": REST,
    "AI Multilingual Menu & Allergen Labels": REST,
    "Restaurant Inventory & Food-cost Control (MarketMan archetype)": REST,
    "Online Table Reservations (OpenTable archetype)": REST,
    "Toast": REST, "Slice": ["5610"], "Flipdish": REST, "Deliverect": REST, "iiko": REST, "Poster POS": REST,
    "iCHEF": REST, "Foodics": REST, "Wongnai": REST,
    # Cafés mostly register as 56.10 restaurants; 56.30 has only ~400 subjects.
    "Digital Loyalty Cards for Cafés (Stamp Me archetype)": REST + ["4724"],
    # accommodation & tourism
    "Guesthouse Booking Engine & Channel Manager (Little Hotelier archetype)": ["551", "552"],
    "Travelline": ["551", "552"], "Lodgify": ["552"],
    "FareHarbor": ["7912", "7990"],
    # services
    "Salon Booking with No-show Deposits (Fresha archetype)": ["9602", "9604"],
    "Fitness & Yoga Studio Software (Mindbody archetype)": FITNESS, "Glofox": FITNESS,
    "Housecall Pro": ["432", "812", "8130"], "Jobber": ["432", "812", "8130"],
    "Tradesperson Quote Marketplace (Checkatrade archetype)": TRADES,
    "Driving School Management & Theory App": ["8553"],
    "Kids' Clubs & Camps Booking (ActivityHero archetype)": ["9312", "8551", "8552"],
    "Spond": ["9312"],
    "Client Galleries for Photographers (Pixieset archetype)": ["7420"],
    "AI Phone Receptionist in Czech (Smith.ai archetype)": ["4520", "862", "432"],
    "Review Request Automation (NiceJob archetype)": ["4520", "862", "9602", "432"],
    # professional services
    "Accountant-Client Document Portal (TaxDome archetype)": ["6920"],
    "Clio": ["6910"],
    "AI Legal Research Assistant for Czech Law (Harvey archetype)": ["6910"],
    "Spellbook": ["6910"],
    "Follow Up Boss": ["6831"],
    "Fixflo": ["6832"], "SVJ Building Management Portal (Buildium archetype)": ["6832"],
    "Local SEO for Google & Seznam (BrightLocal archetype)": ["7311"],
    "Sklik + Google Ads Client Reporting (AgencyAnalytics archetype)": ["7311"],
    "Agency Time Tracking & Profitability (Toggl archetype)": ["7311", "7410", "6201"],
    "Supplier Risk & VAT-Reliability Monitoring (Creditsafe archetype)": ["6920", "46"],
    # health
    "Freed": HEALTH, "Doctolib": HEALTH, "Zocdoc": HEALTH,
    "SimplePractice": ["8690"], "Jane App": ["8690"], "Cliniko": ["8690"],
    "Birdie": ["881"], "Lottie": ["873"],
    # construction, manufacturing, agriculture
    "Public Tender Alerts for SMEs (GovSpend archetype)": ["41", "42", "43"],
    "PlanRadar": ["41", "43"], "Buildxact": ["41", "43"],
    "Katana": ["10", "11", "31", "2042"],
    "Agrivi": ["01"],
    # e-commerce add-ons: NOT mapped - e-shops register under product categories (47.xx), so
    # primary NACE 47.91 finds only ~700 of them. Their SAM stays heuristic until set manually.
    # staffing-heavy tools: count only employers
    "Shift Scheduling for Hourly Staff (Deputy archetype)": REST + ["47"],
    "7shifts": REST, "Planday": REST,
}
GASTRO_TOOLS = ["QR Table Ordering & Pay (Sunday/Mr Yum archetype)", "AI Multilingual Menu & Allergen Labels",
                "Restaurant Inventory & Food-cost Control (MarketMan archetype)",
                "Online Table Reservations (OpenTable archetype)", "Toast", "Slice", "Flipdish", "Deliverect", "iiko",
                "Poster POS", "iCHEF", "Foodics", "Wongnai"]
SEGMENT = {
    # RES counts dormant sole traders as active (115k 'restaurants'); venues with staff are the real market.
    **{n: "with_employees" for n in GASTRO_TOOLS + ["Digital Loyalty Cards for Cafés (Stamp Me archetype)"]},
    "Shift Scheduling for Hourly Staff (Deputy archetype)": "with_employees",
    "7shifts": "with_employees", "Planday": "with_employees",
    "Public Tender Alerts for SMEs (GovSpend archetype)": "legal_entities",
    "Supplier Risk & VAT-Reliability Monitoring (Creditsafe archetype)": "legal_entities",
}
for name, codes in MAP.items():
    entry = models.setdefault(name, {})
    entry["target_nace"] = codes
    if name in SEGMENT:
        entry["sam_segment"] = SEGMENT[name]

# Manual B2C SAM (spec example): pupils sitting the unified entrance exam.
models.setdefault("AI Tutor for Přijímačky & Maturita (Khanmigo archetype)", {}).update({
    "sam_estimate": 96_482,
    "sam_source": ("CERMAT: ~96,482 applicants taking the JPZ for 4-year programmes in 2026 "
                   "(quoted from CERMAT news; source page not reachable - to verify)"),
})
d["_meta"]["fields"] = sorted(set(d["_meta"]["fields"]) | {"sam_segment"})
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"target_nace set for {len(MAP)} models")
