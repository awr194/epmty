"""Markdown and PDF export of a Czech deep-dive report (Russian or English labels)."""

from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path

from fpdf import FPDF, FontFace

from analyzer import AnalysisResult
from data_loader import BusinessModel
from i18n import cat_label, country_label, tr

_L = {
    "en": {
        "title": "Czech Deep-Dive: {name}", "generated": "Generated {d} by Czech Business Model Radar - {engine}",
        "generated_short": "Generated {d} - {engine}", "offline": "offline heuristic engine",
        "original": "Original", "category": "Category", "country": "Country of origin", "niche": "Niche",
        "intl_revenue": "International revenue", "na": "n/a", "origin": "origin",
        "feasibility": "Czech Feasibility Score", "feasibility_short": "Feasibility score",
        "czech_adjusted": "Czech-adjusted score", "confidence": "Confidence",
        "conf": {"low": "low", "medium": "medium", "high": "high"},
        "factor": "Factor", "score": "Score", "weight": "Weight", "rationale": "Rationale",
        "audience": "Target audience in Czechia", "pain": "Pain", "wtp": "Willingness to pay",
        "economics": "Czech unit economics", "tier": "Tier", "price": "Price", "billing": "Billing",
        "includes": "Includes", "customers": "Customers", "month_n": "month {n}", "mrr12": "Month-12 MRR",
        "monthly_costs": "Monthly costs", "net": "net", "per_month": "month", "breakeven": "Break-even",
        "customers_word": "customers", "legal_form": "Legal form", "tax_notes": "Tax notes",
        "cost_item": "Cost item", "czk_month": "CZK / month", "note": "Note",
        "competition": "Local competition", "competitor": "Competitor", "type": "Type", "threat": "Threat",
        "gap": "Gap to exploit", "gtm": "14-day go-to-market plan", "risks": "Risks",
        "checklist": "Localisation checklist", "assumptions": "Assumptions", "page": "page",
        "costs": "costs",
    },
    "ru": {
        "title": "Разбор для Чехии: {name}", "generated": "Создано {d} в «Радаре бизнес-моделей для Чехии» — {engine}",
        "generated_short": "Создано {d} — {engine}", "offline": "офлайн-движок (эвристика)",
        "original": "Оригинал", "category": "Категория", "country": "Страна происхождения", "niche": "Ниша",
        "intl_revenue": "Выручка в мире", "na": "нет данных", "origin": "страна",
        "feasibility": "Выполнимость в Чехии", "feasibility_short": "Выполнимость",
        "czech_adjusted": "Скор с поправками для Чехии", "confidence": "Уверенность",
        "conf": {"low": "низкая", "medium": "средняя", "high": "высокая"},
        "factor": "Фактор", "score": "Балл", "weight": "Вес", "rationale": "Обоснование",
        "audience": "Целевая аудитория в Чехии", "pain": "Боль", "wtp": "Готовность платить",
        "economics": "Юнит-экономика в Чехии", "tier": "Тариф", "price": "Цена", "billing": "Оплата",
        "includes": "Что входит", "customers": "Клиенты", "month_n": "{n}-й месяц", "mrr12": "MRR на 12-й месяц",
        "monthly_costs": "Расходы в месяц", "net": "чистыми", "per_month": "мес.", "breakeven": "Безубыточность",
        "customers_word": "клиентов", "legal_form": "Правовая форма", "tax_notes": "Налоги",
        "cost_item": "Статья расходов", "czk_month": "CZK / мес.", "note": "Примечание",
        "competition": "Местная конкуренция", "competitor": "Конкурент", "type": "Тип", "threat": "Угроза",
        "gap": "Незанятая ниша", "gtm": "План выхода на рынок за 14 дней", "risks": "Риски",
        "checklist": "Чек-лист локализации", "assumptions": "Допущения", "page": "стр.",
        "costs": "расходы",
    },
}


def _czk(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " CZK"


def engine_label(engine: str, lang: str = "en") -> str:
    if engine == "mock":
        return _L[lang]["offline"]
    return f"{'Gemini' if engine.startswith('gemini') else 'Claude'} ({engine})"


def to_markdown(m: BusinessModel, res: AnalysisResult, lang: str = "en") -> str:
    L = _L[lang]
    r, e = res.report, res.report.unit_economics
    engine = engine_label(res.engine, lang)
    revenue = f"~${m.mrr_usd:,} MRR" if m.mrr_usd else L["na"]
    out = [
        f"# {L['title'].format(name=m.name)}",
        "",
        f"*{L['generated'].format(d=date.today().isoformat(), engine=engine)}*",
        "",
        f"**{L['original']}:** [{m.url}]({m.url})  ",
        f"**{L['category']}:** {cat_label(m.category, lang)}  ",
        f"**{L['country']}:** {country_label(m.country, lang)}  ",
        f"**{L['niche']}:** {tr(m.niche, lang)}  ",
        f"**{L['intl_revenue']}:** {revenue} ({tr(m.revenue_note, lang)})",
        "",
        f"## {L['feasibility']}: {r.feasibility_score}/100 - {r.verdict}",
        "",
        f"> {r.one_liner}",
        "",
        f"**{L['czech_adjusted']}:** {r.czech_adjusted_score}/100  ",
        f"**{L['confidence']}:** {L['conf'][r.confidence]} - {r.confidence_reason}",
        "",
        *[f"- {x.factor}: {x.points:+d} ({x.detail})" for x in r.czech_adjustments],
        "",
        f"| {L['factor']} | {L['score']} | {L['weight']} | {L['rationale']} |",
        "|---|---|---|---|",
        *[f"| {f.factor} | {f.score} | {f.weight:.0%} | {f.rationale} |" for f in r.score_breakdown],
        "",
        f"## {L['audience']}",
        "",
        *[f"- **{a.segment}** - {a.size_estimate}. {L['pain']}: {a.pain_point} {L['wtp']}: {a.willingness_to_pay}."
          for a in r.target_audiences],
        "",
        f"## {L['economics']}",
        "",
        f"| {L['tier']} | {L['price']} | {L['billing']} | {L['includes']} |",
        "|---|---|---|---|",
        *[f"| {t.name} | {_czk(t.price_czk)} | {t.billing} | {t.includes} |" for t in e.price_tiers],
        "",
        f"- **{L['customers']}:** {L['month_n'].format(n=3)}: {e.customers_m3}, {L['month_n'].format(n=6)}: "
        f"{e.customers_m6}, {L['month_n'].format(n=12)}: {e.customers_m12}",
        f"- **{L['mrr12']}:** {_czk(e.mrr_czk_m12)} (ARPU {_czk(e.arpu_czk)})",
        f"- **{L['monthly_costs']}:** {_czk(e.total_costs_czk)} -> **{L['net']} {_czk(e.net_profit_czk_m12)}/"
        f"{L['per_month']}**",
        f"- **{L['breakeven']}:** {e.breakeven_customers} {L['customers_word']}",
        f"- **{L['legal_form']}:** {e.legal_form}",
        f"- **{L['tax_notes']}:** {e.tax_notes}",
        "",
        f"| {L['cost_item']} | {L['czk_month']} | {L['note']} |",
        "|---|---|---|",
        *[f"| {c.item} | {c.czk_per_month:,} | {c.note} |" for c in e.monthly_costs],
        "",
        f"## {L['competition']}",
        "",
        f"| {L['competitor']} | {L['type']} | {L['threat']} | {L['gap']} |",
        "|---|---|---|---|",
        *[f"| {f'[{c.name}]({c.url})' if c.url else c.name} | {c.kind} | {c.threat} | {c.gap} |" for c in r.competitors],
        "",
        f"## {L['gtm']}",
        "",
    ]
    for i, s in enumerate(r.gtm_plan, 1):
        out += [f"### {i}. {s.title} ({s.days})", "", *[f"- {a}" for a in s.actions], f"- **KPI:** {s.kpi}", ""]
    out += [f"## {L['risks']}", "", *[f"- {x}" for x in r.risks], "",
            f"## {L['checklist']}", "", *[f"- [ ] {x}" for x in r.localization_checklist], "",
            f"## {L['assumptions']}", "", *[f"- {x}" for x in r.assumptions], ""]
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
    def __init__(self, page_word: str = "page"):
        super().__init__()
        self._page_word = page_word
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
        self.cell(0, 8, self.t(f"Czech Business Model Radar - {self._page_word} {self.page_no()}"), align="C")

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


def to_pdf(m: BusinessModel, res: AnalysisResult, lang: str = "en") -> bytes:
    L = _L[lang]
    r, e = res.report, res.report.unit_economics
    pdf = _PDF(page_word=L["page"])
    pdf.add_page()
    pdf.heading(L["title"].format(name=m.name), 18)
    pdf.para(L["generated_short"].format(d=date.today().isoformat(), engine=engine_label(res.engine, lang)), size=8)
    pdf.para(f"{cat_label(m.category, lang)} | {tr(m.niche, lang)} | {L['origin']}: {country_label(m.country, lang)}")
    pdf.para(f"{L['original']}: {m.url}", size=9)

    pdf.heading(f"{L['feasibility_short']}: {r.feasibility_score}/100 - {r.verdict}", 14)
    pdf.para(r.one_liner)
    pdf.para(f"{L['czech_adjusted']}: {r.czech_adjusted_score}/100 | {L['confidence']}: {L['conf'][r.confidence]} - "
             f"{r.confidence_reason}", size=9)
    for x in r.czech_adjustments:
        pdf.bullet(f"{x.factor}: {x.points:+d} ({x.detail})")
    pdf.ln(1)
    pdf.grid([L["factor"], L["score"], L["weight"], L["rationale"]],
             [[f.factor, f.score, f"{f.weight:.0%}", f.rationale] for f in r.score_breakdown], [40, 14, 16, 120])

    pdf.heading(L["audience"])
    for a in r.target_audiences:
        pdf.bullet(f"{a.segment} - {a.size_estimate}. {L['wtp']}: {a.willingness_to_pay}.")

    pdf.heading(L["economics"])
    pdf.grid([L["tier"], L["price"], L["billing"], L["includes"]],
             [[t.name, _czk(t.price_czk), t.billing, t.includes] for t in e.price_tiers], [28, 30, 45, 87])
    pdf.para(f"{L['customers']}: M3 {e.customers_m3} | M6 {e.customers_m6} | M12 {e.customers_m12}")
    pdf.para(f"{L['mrr12']} {_czk(e.mrr_czk_m12)} - {L['costs']} {_czk(e.total_costs_czk)} = {L['net']} "
             f"{_czk(e.net_profit_czk_m12)}/{L['per_month']}", bold=True)
    pdf.para(f"{L['breakeven']}: {e.breakeven_customers} {L['customers_word']}. {L['legal_form']}: {e.legal_form}.")
    pdf.para(e.tax_notes, size=9)
    pdf.ln(1)
    pdf.grid([L["cost_item"], L["czk_month"], L["note"]],
             [[c.item, f"{c.czk_per_month:,}".replace(",", " "), c.note] for c in e.monthly_costs], [60, 30, 100])

    pdf.heading(L["competition"])
    pdf.grid([L["competitor"], L["type"], L["threat"], L["gap"]],
             [[c.name, c.kind, c.threat, c.gap] for c in r.competitors], [45, 25, 18, 102])

    pdf.heading(L["gtm"])
    for i, s in enumerate(r.gtm_plan, 1):
        pdf.para(f"{i}. {s.title} ({s.days})", bold=True)
        for act in s.actions:
            pdf.bullet(act)
        pdf.bullet(f"KPI: {s.kpi}")

    pdf.heading(L["risks"])
    for x in r.risks:
        pdf.bullet(x)
    pdf.heading(L["checklist"])
    for x in r.localization_checklist:
        pdf.bullet(x)
    pdf.heading(L["assumptions"])
    for x in r.assumptions:
        pdf.bullet(x)
    return bytes(pdf.output())
