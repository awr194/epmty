"""Compact row builder for the global catalogue.

Each catalogue row carries real, global facts about a proven business (name,
country of origin, URL, niche, revenue model, typical price, problem solved)
plus rough Czech-market ratings. Czech segments and competitors are optional:
when omitted, data_loader fills in a category-level Czech landscape that is
clearly labelled as not verified for the specific model.
"""

DEV = "Dev & Productivity Tools"
MKT = "Marketing & Growth"
ECOM = "E-commerce Add-ons"
CRE = "Creator Economy"
LOC = "Local Services"
AI = "AI Tools"
FIN = "Finance & Admin"
HOS = "Hospitality & Gastro"
COM = "Communities & Marketplaces"
D2C = "D2C & Subscriptions"
HEA = "Health & Wellness"
EDU = "Education & EdTech"

# Rough serviceable market in CZ by (category, audience) when a row gives none.
_DEFAULT_SAM = {
    DEV: (5_000, 20_000), MKT: (15_000, 30_000), ECOM: (20_000, 20_000), CRE: (8_000, 50_000),
    LOC: (20_000, 40_000), AI: (15_000, 60_000), FIN: (40_000, 80_000), HOS: (12_000, 40_000),
    COM: (10_000, 60_000), D2C: (10_000, 40_000), HEA: (8_000, 60_000), EDU: (5_000, 80_000),
}


def m(name: str, country: str, url: str, cat: str, niche: str, model: str, price: float, problem: str, *,
      mrr: int | None = None, note: str = "", aud: str = "B2B", czk: int | None = None, sam: int | None = None,
      d: int = 3, c: int = 3, x: int = 3, r: int = 1, mo: int = 2, cogs: float = 0.0,
      segs: list[str] | None = None, comps: list[tuple] | None = None, cz: str = "",
      stack: list[str] | None = None) -> dict:
    """d/c/x/r/mo = Czech demand, competition, complexity, regulation, localisation moat (1-5)."""
    b2b_sam, b2c_sam = _DEFAULT_SAM[cat]
    return dict(
        name=name, country=country, url=url, category=cat, niche=niche, revenue_model=model,
        mrr_usd=mrr, revenue_note=note or "Proven in its home market; revenue not public",
        problem=problem, tech_stack=stack or [], audience=aud, price_usd=price, price_czk_override=czk,
        cz_sam=sam or (b2b_sam if aud == "B2B" else b2c_sam),
        demand=d, competition=c, complexity=x, regulatory=r, moat=mo, cogs_pct=cogs,
        cz_segments=segs or [], cz_competitors=comps or [], cz_notes=cz,
    )
