"""Markdown and PDF export of a Czech deep-dive report."""

from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path

from fpdf import FPDF, FontFace

from analyzer import AnalysisResult
from data_loader import BusinessModel


def _czk(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " CZK"


def engine_label(engine: str) -> str:
    if engine == "mock":
        return "offline heuristic engine"
    return f"{'Gemini' if engine.startswith('gemini') else 'Claude'} ({engine})"


def to_markdown(m: BusinessModel, res: AnalysisResult) -> str:
    r, e = res.report, res.report.unit_economics
    engine = engine_label(res.engine)
    out = [
        f"# Czech Deep-Dive: {m.name}",
        "",
        f"*Generated {date.today().isoformat()} by Czech Business Model Radar - {engine}*",
        "",
        f"**Original:** [{m.url}]({m.url})  ",
        f"**Category:** {m.category}  ",
        f"**Country of origin:** {m.country}  ",
        f"**Niche:** {m.niche}  ",
        f"**International revenue:** {f'~${m.mrr_usd:,} MRR' if m.mrr_usd else 'n/a'} ({m.revenue_note})",
        "",
        f"## Czech Feasibility Score: {r.feasibility_score}/100 - {r.verdict}",
        "",
        f"> {r.one_liner}",
        "",
        f"**Czech-adjusted score:** {r.czech_adjusted_score}/100  ",
        f"**Confidence:** {r.confidence} - {r.confidence_reason}",
        "",
        *[f"- {x.factor}: {x.points:+d} ({x.detail})" for x in r.czech_adjustments],
        "",
        "| Factor | Score | Weight | Rationale |",
        "|---|---|---|---|",
        *[f"| {f.factor} | {f.score} | {f.weight:.0%} | {f.rationale} |" for f in r.score_breakdown],
        "",
        "## Target audience in Czechia",
        "",
        *[f"- **{a.segment}** - {a.size_estimate}. Pain: {a.pain_point} Willingness to pay: {a.willingness_to_pay}."
          for a in r.target_audiences],
        "",
        "## Czech unit economics",
        "",
        "| Tier | Price | Billing | Includes |",
        "|---|---|---|---|",
        *[f"| {t.name} | {_czk(t.price_czk)} | {t.billing} | {t.includes} |" for t in e.price_tiers],
        "",
        f"- **Customers:** month 3: {e.customers_m3}, month 6: {e.customers_m6}, month 12: {e.customers_m12}",
        f"- **Month-12 MRR:** {_czk(e.mrr_czk_m12)} (ARPU {_czk(e.arpu_czk)})",
        f"- **Monthly costs:** {_czk(e.total_costs_czk)} -> **net {_czk(e.net_profit_czk_m12)}/month**",
        f"- **Break-even:** {e.breakeven_customers} customers",
        f"- **Legal form:** {e.legal_form}",
        f"- **Tax notes:** {e.tax_notes}",
        "",
        "| Cost item | CZK / month | Note |",
        "|---|---|---|",
        *[f"| {c.item} | {c.czk_per_month:,} | {c.note} |" for c in e.monthly_costs],
        "",
        "## Local competition",
        "",
        "| Competitor | Type | Threat | Gap to exploit |",
        "|---|---|---|---|",
        *[f"| {f'[{c.name}]({c.url})' if c.url else c.name} | {c.kind} | {c.threat} | {c.gap} |" for c in r.competitors],
        "",
        "## 14-day go-to-market plan",
        "",
    ]
    for i, s in enumerate(r.gtm_plan, 1):
        out += [f"### {i}. {s.title} ({s.days})", "", *[f"- {a}" for a in s.actions], f"- **KPI:** {s.kpi}", ""]
    out += ["## Risks", "", *[f"- {x}" for x in r.risks], "",
            "## Localisation checklist", "", *[f"- [ ] {x}" for x in r.localization_checklist], "",
            "## Assumptions", "", *[f"- {x}" for x in r.assumptions], ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #

# Unicode TTFs so Czech diacritics (č, ř, ž ...) render. First existing pair wins.
_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    (str(Path(__file__).parent / "fonts" / "DejaVuSans.ttf"), str(Path(__file__).parent / "fonts" / "DejaVuSans-Bold.ttf")),
]


class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        self._uni = False
        for regular, bold in _FONT_CANDIDATES:
            if Path(regular).exists():
                self.add_font("Body", "", regular)
                self.add_font("Body", "B", bold if Path(bold).exists() else regular)
                self._uni = True
                break
        self._fam = "Body" if self._uni else "Helvetica"
        self.set_auto_page_break(True, margin=15)

    def t(self, s: str) -> str:
        s = s.replace("–", "-").replace("—", "-").replace("≈", "~").replace("→", "->")
        if self._uni:
            return s
        # Core PDF fonts are Latin-1 only: strip diacritics as a fallback.
        return unicodedata.normalize("NFKD", s).encode("latin-1", "ignore").decode("latin-1")

    def footer(self):
        self.set_y(-12)
        self.set_font(self._fam, "", 8)
        self.set_text_color(130)
        self.cell(0, 8, self.t(f"Czech Business Model Radar - page {self.page_no()}"), align="C")

    def heading(self, text: str, size: int = 13):
        self.ln(3)
        self.set_font(self._fam, "B", size)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 7, self.t(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)

    def para(self, text: str, bold: bool = False, size: int = 10):
        self.set_font(self._fam, "B" if bold else "", size)
        self.multi_cell(0, 5.5, self.t(text), align="L", new_x="LMARGIN", new_y="NEXT")

    def bullet(self, text: str):
        self.set_font(self._fam, "", 10)
        self.set_x(self.l_margin + 3)
        self.multi_cell(0, 5.5, self.t(f"- {text}"), align="L", new_x="LMARGIN", new_y="NEXT")

    def grid(self, headers: list[str], rows: list[list[str]], widths: list[float]):
        self.set_font(self._fam, "B", 9)
        with self.table(col_widths=widths, text_align="LEFT", line_height=5,
                        headings_style=FontFace(emphasis="BOLD", fill_color=(225, 234, 245))) as t:
            hr = t.row()
            for h_ in headers:
                hr.cell(self.t(h_))
            self.set_font(self._fam, "", 9)
            for row in rows:
                tr = t.row()
                for v in row:
                    tr.cell(self.t(str(v)))
        self.ln(2)


def to_pdf(m: BusinessModel, res: AnalysisResult) -> bytes:
    r, e = res.report, res.report.unit_economics
    pdf = _PDF()
    pdf.add_page()
    pdf.heading(f"Czech Deep-Dive: {m.name}", 18)
    engine = engine_label(res.engine)
    pdf.para(f"Generated {date.today().isoformat()} - {engine}", size=8)
    pdf.para(f"{m.category} | {m.niche} | origin: {m.country}")
    pdf.para(f"Original: {m.url}", size=9)

    pdf.heading(f"Feasibility score: {r.feasibility_score}/100 - {r.verdict}", 14)
    pdf.para(r.one_liner)
    pdf.para(f"Czech-adjusted score: {r.czech_adjusted_score}/100 | confidence: {r.confidence} - {r.confidence_reason}",
             size=9)
    for x in r.czech_adjustments:
        pdf.bullet(f"{x.factor}: {x.points:+d} ({x.detail})")
    pdf.ln(1)
    pdf.grid(["Factor", "Score", "Weight", "Rationale"],
              [[f.factor, f.score, f"{f.weight:.0%}", f.rationale] for f in r.score_breakdown], [40, 14, 16, 120])

    pdf.heading("Target audience in Czechia")
    for a in r.target_audiences:
        pdf.bullet(f"{a.segment} - {a.size_estimate}. Willingness to pay: {a.willingness_to_pay}.")

    pdf.heading("Czech unit economics")
    pdf.grid(["Tier", "Price", "Billing", "Includes"],
              [[t.name, _czk(t.price_czk), t.billing, t.includes] for t in e.price_tiers], [28, 30, 45, 87])
    pdf.para(f"Customers: M3 {e.customers_m3} | M6 {e.customers_m6} | M12 {e.customers_m12}")
    pdf.para(f"Month-12 MRR {_czk(e.mrr_czk_m12)} - costs {_czk(e.total_costs_czk)} = net {_czk(e.net_profit_czk_m12)}/month",
          bold=True)
    pdf.para(f"Break-even: {e.breakeven_customers} customers. Legal form: {e.legal_form}.")
    pdf.para(e.tax_notes, size=9)
    pdf.ln(1)
    pdf.grid(["Cost item", "CZK / month", "Note"],
              [[c.item, f"{c.czk_per_month:,}".replace(",", " "), c.note] for c in e.monthly_costs], [60, 30, 100])

    pdf.heading("Local competition")
    pdf.grid(["Competitor", "Type", "Threat", "Gap to exploit"],
              [[c.name, c.kind, c.threat, c.gap] for c in r.competitors], [45, 25, 18, 102])

    pdf.heading("14-day go-to-market plan")
    for i, s in enumerate(r.gtm_plan, 1):
        pdf.para(f"{i}. {s.title} ({s.days})", bold=True)
        for act in s.actions:
            pdf.bullet(act)
        pdf.bullet(f"KPI: {s.kpi}")

    pdf.heading("Risks")
    for x in r.risks:
        pdf.bullet(x)
    pdf.heading("Localisation checklist")
    for x in r.localization_checklist:
        pdf.bullet(x)
    pdf.heading("Assumptions")
    for x in r.assumptions:
        pdf.bullet(x)
    return bytes(pdf.output())
