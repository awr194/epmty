"""Czech Business Model Radar & Adaptation Engine - Streamlit dashboard (Russian / English).

Run:  streamlit run app.py
"""

from __future__ import annotations

import calendar
import os

import altair as alt
import pandas as pd
import streamlit as st

import report_store
from analyzer import (CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL, DEFAULT_GEMINI_MODEL, GEMINI_MODELS, AnalysisResult,
                      CzechAssumptions, analyze, pick_engine, quick_metrics)
from cz_enrichment import MODEL_TYPES
from data_loader import (CATEGORIES, LIVE_SOURCES, LOW_CZ_RELEVANCE_SOURCES, BusinessModel, _id, load_curated,
                         with_cz_defaults)
from exporter import to_markdown, to_pdf
from i18n import (DEFAULT_LANG, LANGS, cat_label, country_label, field_label, mrr_status_label, t, tr, tr_list,
                  tr_sam_source, type_label)
from i18n.ui import COLUMNS, MONTHS_RU
from scoring.config import DEFAULT_WEIGHTS, CzechScoreWeights
from scoring.czech import czech_adjusted_score, to_context
from scoring.metrics import derived_metrics

NON_RECURRING_TYPES = ("d2c_physical", "offline_retail")
VIEWS = ["radar", "deep", "table", "method"]
SOURCE_RU = {"Curated": "База", "Custom": "Своя идея"}

ss = st.session_state
ss.setdefault("lang", DEFAULT_LANG)
ss.setdefault("live_models", [])
ss.setdefault("custom_models", [])
ss.setdefault("reports", {})
ss.setdefault("view", VIEWS[0])
ss.setdefault("selected_id", None)
ss.setdefault("run_for", None)
# Language of this run. Helpers and format_func callbacks read this module-level value rather than
# session_state, because Streamlit may call format_func outside the script run.
lang = ss.lang

st.set_page_config(page_title=t("page_title"), page_icon="🇨🇿", layout="wide")


def secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)  # Streamlit Cloud secrets / .streamlit/secrets.toml
    except Exception:  # no secrets file configured
        return None


def open_deep_dive(model_id: str) -> None:
    ss.selected_id = model_id
    ss.run_for = model_id
    ss.view = "deep"


def czk(v: float) -> str:
    return f"{v:,.0f} CZK".replace(",", " ")


def col_label(key: str) -> str:
    return COLUMNS.get(key, {}).get(lang, key) if lang != "en" else key


def source_label(src: str) -> str:
    return SOURCE_RU.get(src, src) if lang == "ru" else src


def month_abbr(n: int) -> str:
    return (MONTHS_RU if lang == "ru" else calendar.month_abbr)[n]


def pct(x: float) -> str:
    """Percent with a decimal comma in Russian."""
    s = f"{x:.1%}"
    return s.replace(".", ",") if lang == "ru" else s


def mname(m: BusinessModel) -> str:
    """Display name: descriptive (archetype) names are translated, brand names stay as they are."""
    return tr(m.name, lang)


def conf_label(c: str) -> str:
    return t(f"conf_{c}", lang)


def lcat(c: str) -> str:
    return cat_label(c, lang)


def ltype(mt: str) -> str:
    return type_label(mt, lang)


def lcountry(c: str) -> str:
    return country_label(c, lang)


# --------------------------------------------------------------------------- #
# Sidebar - language, engine, assumptions, sources
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.selectbox(t("language"), list(LANGS), format_func=LANGS.get, key="lang")

    st.header(t("engine_header"))
    with st.expander(t("api_keys"), expanded=False):
        typed_anthropic = st.text_input(t("anthropic_key"), type="password", help=t("anthropic_key_help"))
        typed_gemini = st.text_input(t("gemini_key"), type="password", help=t("gemini_key_help"))
    anthropic_key = typed_anthropic or secret("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = (typed_gemini or secret("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
                  or os.environ.get("GOOGLE_API_KEY"))

    engine = st.radio(t("engine"), ["auto", "claude", "gemini", "mock"], horizontal=True, help=t("engine_help"),
                      format_func=lambda e: {"auto": t("engine_auto", lang), "claude": "Claude", "gemini": "Gemini",
                                             "mock": t("engine_offline", lang)}[e])
    active = pick_engine(engine, anthropic_key, gemini_key)
    claude_model = st.selectbox(t("claude_model"), CLAUDE_MODELS, index=CLAUDE_MODELS.index(DEFAULT_CLAUDE_MODEL),
                                disabled=active != "claude")
    gemini_model = st.selectbox(t("gemini_model"), GEMINI_MODELS, index=GEMINI_MODELS.index(DEFAULT_GEMINI_MODEL),
                                accept_new_options=True, disabled=active != "gemini", help=t("gemini_model_help"))
    active_key = {"claude": anthropic_key, "gemini": gemini_key}.get(active)
    active_model = {"claude": claude_model, "gemini": gemini_model}.get(active, "")
    st.caption(t("keys_detected", a="✅" if anthropic_key else "—", g="✅" if gemini_key else "—"))
    if active == "mock":
        st.info(t("offline_mode"), icon="⚡")
    elif active_key:
        st.success(t("engine_enabled", engine=active.title(), model=active_model), icon="🤖")
    else:
        st.warning(t("no_key", engine=active.title()), icon="🔑")

    with st.expander(t("assumptions")):
        a = CzechAssumptions(
            usd_czk=st.number_input(t("usd_czk"), 15.0, 35.0, 23.0, 0.1),
            ppp_b2b=st.slider(t("ppp_b2b"), 0.3, 1.2, 0.75, 0.05),
            ppp_b2c=st.slider(t("ppp_b2c"), 0.3, 1.2, 0.60, 0.05),
            pausal_band1=st.number_input(t("pausal1"), 5_000, 20_000, 10_000, 100, help=t("pausal1_help")),
            pausal_band2=st.number_input(t("pausal2"), 10_000, 30_000, 17_000, 100),
            pausal_band3=st.number_input(t("pausal3"), 15_000, 45_000, 27_000, 100),
            sro_accounting=st.number_input(t("sro_accounting"), 0, 20_000, 4_000, 500),
        )
        st.markdown(t("weights_header"))
        d = DEFAULT_WEIGHTS
        weights = CzechScoreWeights(
            incumbent_points_per_strength=st.slider(t("w_incumbent"), 0.0, 10.0, d.incumbent_points_per_strength, 0.5),
            incumbent_cap=st.slider(t("w_incumbent_cap"), 0.0, 50.0, d.incumbent_cap, 1.0),
            sam_soft=st.slider(t("w_sam_soft"), 0.0, 0.10, d.sam_soft, 0.005, format="%.3f"),
            sam_hard=st.slider(t("w_sam_hard"), 0.02, 0.30, d.sam_hard, 0.01, format="%.2f"),
            sam_step_penalty=st.slider(t("w_sam_step"), 0.0, 10.0, d.sam_step_penalty, 0.5),
            sam_soft_penalty=st.slider(t("w_sam_soft_pen"), 0.0, 30.0, d.sam_soft_penalty, 1.0),
            sam_hard_penalty=st.slider(t("w_sam_hard_pen"), 0.0, 40.0, d.sam_hard_penalty, 1.0),
            heuristic_sam_confidence=st.slider(t("w_sam_conf"), 0.0, 1.0, d.heuristic_sam_confidence, 0.05),
            legal_points_per_level=st.slider(t("w_legal"), 0.0, 8.0, d.legal_points_per_level, 0.5),
            integration_points_each=st.slider(t("w_integration"), 0.0, 8.0, d.integration_points_each, 0.5),
            solo_founder=st.toggle(t("w_solo"), d.solo_founder),
            czech_support_penalty=st.slider(t("w_support"), 0.0, 10.0, d.czech_support_penalty, 0.5),
            czech_support_penalty_other_b2b=st.slider(t("w_support_other"), 0.0, 10.0,
                                                      d.czech_support_penalty_other_b2b, 0.5),
            original_in_cz_penalty=st.slider(t("w_original"), 0.0, 20.0, d.original_in_cz_penalty, 1.0),
        )

    st.header(t("live_header"))
    sources = st.multiselect(t("live_from"), list(LIVE_SOURCES), default=list(LIVE_SOURCES),
                             placeholder=t("choose"))
    live_limit = st.slider(t("live_items"), 5, 30, 15)
    show_live = st.toggle(t("live_show"), False, help=t("live_show_help"))
    c1, c2 = st.columns(2)
    if c1.button(t("live_fetch"), width="stretch", disabled=not sources):
        fetched: list[BusinessModel] = []
        for name in sources:
            with st.spinner(t("live_fetching", name=name)):
                try:
                    fetched += LIVE_SOURCES[name](limit=live_limit)
                except Exception as e:
                    st.warning(f"{name}: {e}")
        ss.live_models = fetched
        st.toast(t("live_fetched", n=len(fetched)) + ("" if show_live else t("live_fetched_hidden")))
    if c2.button(t("live_clear"), width="stretch", disabled=not ss.live_models):
        ss.live_models = []
    st.caption(t("live_caption"))

    with st.expander(t("custom_header")):
        with st.form("custom", clear_on_submit=True):
            name = st.text_input(t("f_name"))
            url = st.text_input(t("f_url"))
            cat = st.selectbox(t("f_category"), CATEGORIES, format_func=lcat)
            niche = st.text_input(t("f_niche"))
            problem = st.text_area(t("f_problem"))
            rev_model = st.text_input(t("f_revenue_model"), t("f_revenue_model_default"))
            mrr = st.number_input(t("f_mrr"), 0, 10_000_000, 0, 1000)
            price = st.number_input(t("f_price"), 1.0, 5000.0, 29.0)
            audience = st.radio(t("f_audience"), ["B2B", "B2C"], horizontal=True)
            sam = st.number_input(t("f_sam"), 100, 1_000_000, 5_000, 500)
            segs = st.text_input(t("f_segments"))
            demand = st.slider(t("f_demand"), 1, 5, 3)
            comp = st.slider(t("f_competition"), 1, 5, 3)
            cplx = st.slider(t("f_complexity"), 1, 5, 3)
            if st.form_submit_button(t("f_add")) and name:
                ss.custom_models.append(with_cz_defaults(BusinessModel(
                    id=_id(name, "Custom"), name=name, url=url or "", category=cat, niche=niche or cat,
                    revenue_model=rev_model, mrr_usd=mrr or None, revenue_note=t("f_user_supplied"),
                    problem=problem or niche, source="Custom", country="Custom", audience=audience,
                    price_usd=price, cz_sam=sam, demand=demand, competition=comp, complexity=cplx,
                    cz_segments=[s.strip() for s in segs.split(",") if s.strip()],
                )))
                st.toast(t("f_added", name=name))


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

@st.cache_data
def curated() -> list[BusinessModel]:
    return load_curated()


models: dict[str, BusinessModel] = {m.id: m for m in curated() + ss.live_models + ss.custom_models}

rows = []
czech_scores = {}
metrics = {}
for m in models.values():
    q = quick_metrics(m, a)
    dm = metrics[m.id] = derived_metrics(m, a, q)
    cs = czech_scores[m.id] = czech_adjusted_score(q["score"], m, dm, weights, lang)
    launch = m.seasonality.launch_by_month
    niche_tr, problem_tr = tr(m.niche), tr(m.problem)
    rows.append({
        "id": m.id, "Name": mname(m), "Category": m.category, "Model type": m.model_type or "saas",
        "Source": m.source, "Country": m.country, "Niche": niche_tr,
        "Score": q["score"], "Czech score": cs.score, "Price (CZK)": q["price_czk"],
        "CZK potential (M12 MRR)": q["mrr_czk_m12"], "MRR comparable": dm.comparable,
        "MRR status": mrr_status_label(dm.mrr_status), "Customers needed": dm.customers_needed,
        "SAM": m.sam_estimate, "SAM share (12m)": dm.sam_share_12m, "SAM source": tr_sam_source(m.sam_source),
        "Local incumbents": len(m.local_incumbents), "Legal complexity": m.legal_complexity or m.regulatory,
        "Integrations": ", ".join(m.required_integrations),
        "Launch by": month_abbr(launch) if launch else "", "Needs rethink for CZ": m.needs_rethink_for_cz,
        "Intl. MRR (USD)": m.mrr_usd, "Revenue model": tr(m.revenue_model), "Problem": problem_tr,
        "Tech stack": ", ".join(m.tech_stack), "URL": m.url,
        # searchable in both languages
        "_search": " ".join([m.name, mname(m), m.niche, niche_tr, m.problem, problem_tr, m.category, cat_label(m.category),
                             m.country, country_label(m.country)]).lower(),
    })
df = pd.DataFrame(rows)

st.title(t("app_title"))
st.caption(t("app_caption"))

# Filters
with st.container(border=True):
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1.4])
    query = f1.text_input(t("search"), placeholder=t("search_ph"))
    cats = f2.multiselect(t("category"), sorted(df["Category"].unique(), key=lcat), format_func=lcat,
                          placeholder=t("choose"))
    score_mode = f3.radio(t("score"), ["czech", "orig"], horizontal=True, help=t("score_help"),
                          format_func=lambda s: t("score_czech", lang) if s == "czech" else t("score_orig", lang))
    score_col = "Czech score" if score_mode == "czech" else "Score"
    score_name = t("col_czech_score") if score_mode == "czech" else t("col_score")
    sort_by = f4.selectbox(t("sort_by"), [score_col, "CZK potential (M12 MRR)", "SAM", "Intl. MRR (USD)", "Name"],
                           format_func=col_label)
    h1, h2, h3, h4 = st.columns([2, 3, 1.4, 1.4])
    min_score = h1.slider(t("min_score", score=score_name.lower()), 0, 100, 0, 5)
    all_types = [x for x in MODEL_TYPES if x in set(df["Model type"])]
    types = h2.multiselect(t("model_type"), all_types, default=[x for x in all_types if x not in NON_RECURRING_TYPES],
                           format_func=ltype, help=t("model_type_help"), placeholder=t("choose"))
    hide_rethink = h3.checkbox(t("hide_rethink"), True, help=t("hide_rethink_help"))
    only_saas = h4.checkbox(t("only_saas"), False)
    g1, g2, g3 = st.columns([3, 2, 2])
    max_pot = int(df["CZK potential (M12 MRR)"].max()) + 1
    pot = g1.slider(t("potential"), 0, max_pot, (0, max_pot), step=5_000, format="%d CZK")
    countries = g2.multiselect(t("country"), sorted(df["Country"].unique(), key=lcountry),
                               format_func=lcountry, placeholder=t("choose"))
    srcs = g3.multiselect(t("source"), sorted(df["Source"].unique()), format_func=source_label,
                          placeholder=t("choose"))

view_df = df[(df[score_col] >= min_score) & df["CZK potential (M12 MRR)"].between(*pot)]
view_df = view_df[view_df["Model type"].isin(["saas"] if only_saas else types)]
if hide_rethink:
    view_df = view_df[~view_df["Needs rethink for CZ"]]
if cats:
    view_df = view_df[view_df["Category"].isin(cats)]
if countries:
    view_df = view_df[view_df["Country"].isin(countries)]
if srcs:
    view_df = view_df[view_df["Source"].isin(srcs)]
if not show_live:
    view_df = view_df[~view_df["Source"].isin(LOW_CZ_RELEVANCE_SOURCES)]
if query:
    view_df = view_df[view_df["_search"].str.contains(query.lower(), regex=False)]
view_df = view_df.sort_values(sort_by, ascending=sort_by == "Name", na_position="last")

k1, k5, k2, k3, k4 = st.columns([1, 0.8, 1, 1.2, 1.4])
k1.metric(t("kpi_shown"), f"{len(view_df)} / {len(df)}")
k5.metric(t("kpi_countries"), view_df["Country"].nunique())
k2.metric(t("kpi_avg", score=score_name.lower()), f"{view_df[score_col].mean():.0f}" if len(view_df) else "-")
k3.metric(t("kpi_median_pot"), czk(view_df["CZK potential (M12 MRR)"].median()) if len(view_df) else "-")
k4.metric(t("kpi_top"), view_df.sort_values(score_col, ascending=False).iloc[0]["Name"][:28] if len(view_df) else "-")

view = st.radio("View", VIEWS, key="view", horizontal=True, label_visibility="collapsed",
                format_func=lambda v: t(f"view_{v}", lang))


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #

def radar_view() -> None:
    if view_df.empty:
        st.info(t("no_match"))
        return
    color_by = st.radio(t("colour"), ["category", "incumbents"], horizontal=True, key="map_color",
                        format_func=lambda c: t("colour_category", lang) if c == "category" else t("colour_incumbents", lang))
    chart_df = view_df.assign(**{
        "SAM (size)": view_df["SAM"].fillna(0),
        "MRR": view_df["MRR comparable"].map({True: t("mrr_comparable"), False: t("mrr_not_comparable")}),
        "Category label": view_df["Category"].map(cat_label),
        "Type label": view_df["Model type"].map(type_label),
        "Country label": view_df["Country"].map(country_label),
    })
    # Legends sit on the right: Streamlit fits the whole chart (legends included) into `height`.
    color = (alt.Color("Category label:N", title=col_label("Category"), legend=alt.Legend(orient="right"))
             if color_by == "category" else
             alt.Color("Local incumbents:Q", scale=alt.Scale(scheme="orangered"),
                       legend=alt.Legend(title=col_label("Local incumbents"))))
    chart = (
        alt.Chart(chart_df)
        .mark_point(filled=True, opacity=0.75)
        .encode(
            x=alt.X(f"{score_col}:Q", title=score_name, scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("CZK potential (M12 MRR):Q", title=t("axis_mrr"), scale=alt.Scale(type="symlog")),
            size=alt.Size("SAM (size):Q", scale=alt.Scale(type="sqrt", range=[20, 600]),
                          legend=alt.Legend(title="SAM", orient="right", values=[1_000, 10_000, 50_000])),
            color=color,
            shape=alt.Shape("MRR:N", title="MRR", scale=alt.Scale(
                domain=[t("mrr_comparable"), t("mrr_not_comparable")], range=["circle", "diamond"])),
            tooltip=[alt.Tooltip("Name:N", title=col_label("Name")),
                     alt.Tooltip("Category label:N", title=col_label("Category")),
                     alt.Tooltip("Type label:N", title=col_label("Model type")),
                     alt.Tooltip("Country label:N", title=col_label("Country")),
                     alt.Tooltip("Czech score:Q", title=col_label("Czech score")),
                     alt.Tooltip("Score:Q", title=col_label("Score")),
                     alt.Tooltip("Local incumbents:Q", title=col_label("Local incumbents")),
                     alt.Tooltip("SAM:Q", format=",.0f"),
                     alt.Tooltip("SAM share (12m):Q", format=".1%", title=col_label("SAM share (12m)")),
                     alt.Tooltip("CZK potential (M12 MRR):Q", format=",.0f", title=col_label("CZK potential (M12 MRR)")),
                     alt.Tooltip("MRR status:N", title=col_label("MRR status"))],
        )
        .properties(height=460, title=t("map_title"))
    )
    st.altair_chart(chart, width="stretch")

    page_size = 24
    n_pages = max(1, -(-len(view_df) // page_size))
    if ss.get("radar_page", 1) > n_pages:  # filters shrank the list
        ss.radar_page = n_pages
    p1, p2 = st.columns([1, 4])
    page = p1.number_input(t("page"), 1, n_pages, 1, key="radar_page") if n_pages > 1 else 1
    start = (page - 1) * page_size
    p2.caption(t("showing", a=start + 1, b=min(start + page_size, len(view_df)), n=len(view_df)))

    cols = st.columns(3)
    for i, (_, r) in enumerate(view_df.iloc[start:start + page_size].iterrows()):
        m, cs, dm = models[r["id"]], czech_scores[r["id"]], metrics[r["id"]]
        score = int(r[score_col])
        with cols[i % 3].container(border=True):
            st.markdown(f"**[{mname(m)}]({m.url})**" if m.url else f"**{mname(m)}**")
            badges = (f":blue-badge[{cat_label(m.category)}] :green-badge[{country_label(m.country)}] "
                      f":gray-badge[{type_label(m.model_type)}]")
            if m.needs_rethink_for_cz:
                badges += f" :red-badge[{t('badge_rethink')}]"
            if m.original_available_in_cz in ("yes", "likely"):
                badges += (f" :{'red' if m.original_available_in_cz == 'yes' else 'orange'}-badge"
                           f"[{t('badge_orig_' + m.original_available_in_cz)}]")
            if m.source in LOW_CZ_RELEVANCE_SOURCES:
                badges += f" :orange-badge[{t('badge_feed')}]"
            st.markdown(badges)
            st.caption(tr(m.niche))
            st.progress(score / 100, text=f"{score_name} **{score}**/100")
            st.caption(t("czech_vs_orig", cz=cs.score, base=cs.base, delta=cs.delta))
            c1, c2 = st.columns(2)
            if dm.customers_needed is not None:
                c1.metric(t("customers_needed"), f"{dm.customers_needed:,}".replace(",", " "),
                          t("of_sam", share=pct(dm.sam_share_12m)) if dm.sam_share_12m is not None else t("no_sam"),
                          delta_color="off")
            else:
                c1.metric(t("intl_mrr"), f"${m.mrr_usd / 1000:,.0f}k" if m.mrr_usd else t("na"))
            c2.metric(t("czk_month"), f"{r['CZK potential (M12 MRR)'] / 1000:,.0f}k",
                      None if dm.comparable else t("mrr_not_comparable"), delta_color="off")
            with st.expander(t("breakdown")):
                if cs.breakdown:
                    for adj in cs.breakdown:
                        st.markdown(f"- **{adj.factor}** {adj.points:+.0f} — {adj.detail}")
                else:
                    st.caption(t("no_deductions"))
                st.markdown(f"**{t('legal_complexity')}:** {m.legal_complexity or m.regulatory}/5 · "
                            f"**{t('integrations')}:** {', '.join(m.required_integrations) or '—'}")
                st.caption(t("sam_line", sam=f"{m.sam_estimate:,}".replace(",", " "),
                             source=tr_sam_source(m.sam_source)) if m.sam_estimate else t("no_sam_estimate"))
                for rec in cs.recommendations:
                    st.caption(f"💡 {rec}")
                if m.inferred_fields:
                    st.caption(t("inferred", fields=", ".join(field_label(f) for f in m.inferred_fields)))
            with st.expander(t("details")):
                st.write(f"**{t('problem')}:** {tr(m.problem)}")
                st.write(f"**{t('revenue_model')}:** {tr(m.revenue_model)}")
                if m.tech_stack:
                    st.write(f"**{t('tech_stack')}:** {', '.join(m.tech_stack)}")
                if m.cz_segments:
                    st.write(f"**{t('czech_segments')}:** {', '.join(tr_list(m.cz_segments))}")
                st.caption(tr(m.revenue_note))
                stored = report_store.latest(m.id)
                if stored:
                    rep_ = stored["report"]
                    st.markdown(t("llm_assessment", engine=stored["engine"], date=stored["timestamp"][:10],
                                  f=rep_.feasibility_score, cz=rep_.czech_adjusted_score,
                                  conf=conf_label(rep_.confidence)))
                    st.caption(rep_.confidence_reason)
                else:
                    st.caption(t("no_llm"))
            st.button(t("dd_button"), key=f"dd_{m.id}", width="stretch",
                      on_click=open_deep_dive, args=(m.id,), type="primary" if score >= 60 else "secondary")


def get_report(m: BusinessModel, force: bool = False) -> AnalysisResult | None:
    cache_key = (m.id, active, active_model, a.model_dump_json(), weights, lang)
    if force or cache_key not in ss.reports:
        if not force and ss.run_for != m.id:
            return None
        with st.spinner(t("spinner_llm", model=active_model) if active_key else t("spinner_offline")):
            result = analyze(m, a, engine=active, anthropic_key=anthropic_key, gemini_key=gemini_key,
                             claude_model=claude_model, gemini_model=gemini_model,
                             czech_context=to_context(czech_scores[m.id], m, metrics[m.id]), lang=lang)
            report_store.save(m.id, m.name, result)  # LLM runs only; keeps rationale & confidence
            ss.reports[cache_key] = result
        ss.run_for = None
    return ss.reports[cache_key]


def _renamed(records: list[dict], mapping: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(records).rename(columns={k: t(v) for k, v in mapping.items()})


def deep_dive_view() -> None:
    ids = list(models)
    if ss.selected_id not in models:
        ss.selected_id = view_df["id"].iloc[0] if len(view_df) else ids[0]
    # The widget key is separate from `selected_id` because Streamlit discards widget
    # state while the widget is not rendered (i.e. when another view is active).
    ss.dd_choice = ss.selected_id
    c1, c2 = st.columns([4, 1])
    c1.selectbox(t("business_model"), ids, key="dd_choice",
                 format_func=lambda i: f"{mname(models[i])}  ·  {lcat(models[i].category)}",
                 on_change=lambda: ss.update(selected_id=ss.dd_choice))
    m = models[ss.selected_id]
    has_report = get_report(m) is not None
    force = c2.button(t("regenerate") if has_report else t("generate"), width="stretch", type="primary")
    res = get_report(m, force=force)
    if res is None:
        st.info(t("click_generate"))
        return
    for w in res.warnings:
        st.warning(w)

    r, e = res.report, res.report.unit_economics
    st.subheader(mname(m))
    st.markdown(f"> {r.one_liner}")
    st.caption(t("generated_by", engine=res.engine) if res.engine != "mock" else t("offline_engine"))
    conf_icon = {"low": "🟠", "medium": "🟡", "high": "🟢"}[r.confidence]
    st.markdown(f"{conf_icon} **{t('confidence')}: {conf_label(r.confidence)}** — {r.confidence_reason}")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(t("k_feasibility"), f"{r.feasibility_score}/100", r.verdict,
              delta_color="normal" if r.feasibility_score >= 55 else "inverse")
    k2.metric(t("k_mrr"), czk(e.mrr_czk_m12), t("k_customers", n=e.customers_m12), delta_color="off")
    k3.metric(t("k_profit"), czk(e.net_profit_czk_m12))
    k4.metric(t("k_breakeven"), t("k_customers", n=e.breakeven_customers), e.legal_form, delta_color="off")

    t1, t2, t3, t4, t5, t6 = st.tabs([t("tab_score"), t("tab_audience"), t("tab_economics"), t("tab_competition"),
                                      t("tab_roadmap"), t("tab_risks")])
    with t1:
        st.markdown(t("czech_adjusted", cz=r.czech_adjusted_score, f=r.feasibility_score))
        for x in r.czech_adjustments:
            st.markdown(f"- {x.factor}: **{x.points:+d}** — {x.detail}")
        sdf = pd.DataFrame([f.model_dump() for f in r.score_breakdown])
        st.altair_chart(
            alt.Chart(sdf).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("score:Q", scale=alt.Scale(domain=[0, 100]), title=t("score")),
                y=alt.Y("factor:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                color=alt.Color("score:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[0, 100]), legend=None),
                tooltip=[alt.Tooltip("factor:N", title=t("col_factor")), alt.Tooltip("score:Q", title=t("score")),
                         alt.Tooltip("weight:Q", format=".0%", title=t("col_weight")),
                         alt.Tooltip("rationale:N", title=t("col_rationale"))],
            ).properties(height=230),
            width="stretch",
        )
        st.dataframe(sdf.rename(columns={"factor": t("col_factor"), "score": t("score"), "weight": t("col_weight"),
                                         "rationale": t("col_rationale")}), hide_index=True, width="stretch",
                     column_config={t("col_weight"): st.column_config.NumberColumn(format="percent"),
                                    t("score"): st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
    with t2:
        for aud in r.target_audiences:
            with st.container(border=True):
                st.markdown(f"**{aud.segment}** — {aud.size_estimate}")
                st.write(t("pain", x=aud.pain_point))
                st.caption(t("wtp", x=aud.willingness_to_pay))
    with t3:
        st.markdown(t("pricing"))
        st.dataframe(_renamed([x.model_dump() for x in e.price_tiers],
                              {"name": "col_tier", "price_czk": "col_price", "billing": "col_billing",
                               "includes": "col_includes"}),
                     hide_index=True, width="stretch",
                     column_config={t("col_price"): st.column_config.NumberColumn(format="%d")})
        proj = pd.DataFrame({"m": [0, 3, 6, 12], "c": [0, e.customers_m3, e.customers_m6, e.customers_m12]})
        proj[t("series_mrr")] = proj["c"] * e.arpu_czk
        proj[t("series_costs")] = e.total_costs_czk
        long = proj.melt("m", [t("series_mrr"), t("series_costs")], var_name="s", value_name="v")
        st.altair_chart(
            alt.Chart(long).mark_line(point=True).encode(
                x=alt.X("m:Q", title=t("month")), y=alt.Y("v:Q", title=t("czk_per_month")),
                color=alt.Color("s:N", title=t("series")),
                tooltip=[alt.Tooltip("m:Q", title=t("month")), alt.Tooltip("s:N", title=t("series")),
                         alt.Tooltip("v:Q", format=",.0f", title="CZK")],
            ).properties(height=260, title=t("ramp_title")),
            width="stretch",
        )
        st.markdown(t("op_costs"))
        st.dataframe(_renamed([c.model_dump() for c in e.monthly_costs],
                              {"item": "col_item", "czk_per_month": "czk_per_month", "note": "col_note"}),
                     hide_index=True, width="stretch",
                     column_config={t("czk_per_month"): st.column_config.NumberColumn(format="%d")})
        st.info(f"{t('legal_form', x=e.legal_form)}\n\n{e.tax_notes}", icon="🏛️")
    with t4:
        st.dataframe(_renamed([c.model_dump() for c in r.competitors],
                              {"name": "col_name", "kind": "col_kind", "url": "f_url", "threat": "col_threat",
                               "gap": "col_gap"}),
                     hide_index=True, width="stretch", column_config={t("f_url"): st.column_config.LinkColumn()})
    with t5:
        cols = st.columns(len(r.gtm_plan) or 1)
        for i, step in enumerate(r.gtm_plan):
            with cols[i].container(border=True):
                st.markdown(f"#### {i + 1}. {step.title}")
                st.caption(step.days)
                for act in step.actions:
                    st.markdown(f"- {act}")
                st.success(t("kpi_label", x=step.kpi))
    with t6:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(t("risks"))
            for x in r.risks:
                st.markdown(f"- {x}")
            st.markdown(t("assumptions_h"))
            for x in r.assumptions:
                st.caption(f"• {x}")
        with c2:
            st.markdown(t("checklist"))
            for i, x in enumerate(r.localization_checklist):
                st.checkbox(x, key=f"chk_{m.id}_{i}")

    st.divider()
    slug = "".join(ch if ch.isalnum() else "-" for ch in m.name.lower()).strip("-")[:40]
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button(t("export_md"), to_markdown(m, res, lang), f"czech-report-{slug}.md", "text/markdown",
                       width="stretch")
    try:
        d2.download_button(t("export_pdf"), to_pdf(m, res, lang), f"czech-report-{slug}.pdf", "application/pdf",
                           width="stretch")
    except Exception as ex:  # font / rendering problems should never break the page
        d2.warning(t("pdf_unavailable", e=ex))


def table_view() -> None:
    out = view_df.drop(columns=["id", "_search"]).assign(
        **{"Category": view_df["Category"].map(cat_label), "Model type": view_df["Model type"].map(type_label),
           "Country": view_df["Country"].map(country_label), "Source": view_df["Source"].map(source_label)})
    out = out.rename(columns={c: col_label(c) for c in out.columns})
    st.dataframe(
        out, hide_index=True, width="stretch", height=560,
        column_config={
            col_label("Score"): st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            col_label("Czech score"): st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            col_label("SAM share (12m)"): st.column_config.NumberColumn(format="percent"),
            col_label("SAM"): st.column_config.NumberColumn(format="%d"),
            col_label("CZK potential (M12 MRR)"): st.column_config.NumberColumn(format="%d CZK"),
            col_label("Price (CZK)"): st.column_config.NumberColumn(format="%d"),
            col_label("Intl. MRR (USD)"): st.column_config.NumberColumn(format="$%d"),
            col_label("URL"): st.column_config.LinkColumn(),
        },
    )
    st.download_button(t("download_csv"), out.to_csv(index=False), "czech-radar.csv", "text/csv")


def methodology_view() -> None:
    st.markdown(t("methodology_md"))


{"radar": radar_view, "deep": deep_dive_view, "table": table_view, "method": methodology_view}[view]()
