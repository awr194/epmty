"""Czech Business Model Radar & Adaptation Engine - Streamlit dashboard.

Run:  streamlit run app.py
"""

from __future__ import annotations

import os

import altair as alt
import pandas as pd
import streamlit as st

from analyzer import (CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL, DEFAULT_GEMINI_MODEL, GEMINI_MODELS, AnalysisResult,
                      CzechAssumptions, analyze, pick_engine, quick_metrics)
from data_loader import CATEGORIES, LIVE_SOURCES, BusinessModel, _id, load_curated, with_cz_defaults
from exporter import to_markdown, to_pdf
from scoring.config import DEFAULT_WEIGHTS, CzechScoreWeights
from scoring.czech import czech_adjusted_score
from scoring.metrics import derived_metrics

st.set_page_config(page_title="Czech Business Model Radar", page_icon="🇨🇿", layout="wide")

VIEWS = ["📡 Radar", "🔬 Deep-Dive", "📊 Data table", "ℹ️ Methodology"]

ss = st.session_state
ss.setdefault("live_models", [])
ss.setdefault("custom_models", [])
ss.setdefault("reports", {})
ss.setdefault("view", VIEWS[0])
ss.setdefault("selected_id", None)
ss.setdefault("run_for", None)


def secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)  # Streamlit Cloud secrets / .streamlit/secrets.toml
    except Exception:  # no secrets file configured
        return None


def open_deep_dive(model_id: str) -> None:
    ss.selected_id = model_id
    ss.run_for = model_id
    ss.view = VIEWS[1]


def czk(v: float) -> str:
    return f"{v:,.0f} CZK".replace(",", " ")


# --------------------------------------------------------------------------- #
# Sidebar - engine, assumptions, sources
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.header("⚙️ Analysis engine")
    with st.expander("🔑 API keys", expanded=False):
        typed_anthropic = st.text_input("Anthropic API key", type="password",
                                        help="Kept only in this browser session. Or set ANTHROPIC_API_KEY "
                                             "as a secret / env var.")
        typed_gemini = st.text_input("Gemini API key", type="password",
                                     help="Free key at aistudio.google.com/apikey. Kept only in this browser "
                                          "session. Or set GEMINI_API_KEY as a secret / env var.")
    anthropic_key = typed_anthropic or secret("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = (typed_gemini or secret("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
                  or os.environ.get("GOOGLE_API_KEY"))

    engine_label = st.radio("Engine", ["Auto", "Claude", "Gemini", "Offline"], horizontal=True,
                            help="Auto: Claude if its key is set, otherwise Gemini, otherwise the instant offline engine.")
    engine = {"Auto": "auto", "Claude": "claude", "Gemini": "gemini", "Offline": "mock"}[engine_label]
    active = pick_engine(engine, anthropic_key, gemini_key)
    claude_model = st.selectbox("Claude model", CLAUDE_MODELS, index=CLAUDE_MODELS.index(DEFAULT_CLAUDE_MODEL),
                                disabled=active != "claude")
    gemini_model = st.selectbox("Gemini model", GEMINI_MODELS, index=GEMINI_MODELS.index(DEFAULT_GEMINI_MODEL),
                                accept_new_options=True, disabled=active != "gemini",
                                help="Pick one or type any other Gemini model id.")
    active_key = {"claude": anthropic_key, "gemini": gemini_key}.get(active)
    active_model = {"claude": claude_model, "gemini": gemini_model}.get(active, "")
    st.caption(f"Keys detected: Anthropic {'✅' if anthropic_key else '—'} · Gemini {'✅' if gemini_key else '—'}")
    if active == "mock":
        st.info("Offline demo mode - instant heuristic reports.", icon="⚡")
    elif active_key:
        st.success(f"{active.title()} enabled ({active_model})", icon="🤖")
    else:
        st.warning(f"No {active.title()} API key found - reports will fall back to offline mode.", icon="🔑")

    with st.expander("🇨🇿 Market assumptions"):
        a = CzechAssumptions(
            usd_czk=st.number_input("USD / CZK", 15.0, 35.0, 23.0, 0.1),
            ppp_b2b=st.slider("B2B price vs. US", 0.3, 1.2, 0.75, 0.05),
            ppp_b2c=st.slider("B2C price vs. US", 0.3, 1.2, 0.60, 0.05),
            pausal_band1=st.number_input("Paušální daň band 1 (CZK/month)", 5_000, 20_000, 10_000, 100,
                                         help="Rounded 2026 figure - verify on financnisprava.cz"),
            pausal_band2=st.number_input("Paušální daň band 2 (CZK/month)", 10_000, 30_000, 17_000, 100),
            pausal_band3=st.number_input("Paušální daň band 3 (CZK/month)", 15_000, 45_000, 27_000, 100),
            sro_accounting=st.number_input("s.r.o. accountant (CZK/month)", 0, 20_000, 4_000, 500),
        )
        st.markdown("**Czech score weights**")
        d = DEFAULT_WEIGHTS
        weights = CzechScoreWeights(
            incumbent_points_per_strength=st.slider("Points per incumbent strength", 0.0, 10.0,
                                                    d.incumbent_points_per_strength, 0.5),
            incumbent_cap=st.slider("Max incumbent penalty", 0.0, 50.0, d.incumbent_cap, 1.0),
            sam_soft=st.slider("SAM share: penalty starts at", 0.0, 0.10, d.sam_soft, 0.005, format="%.3f"),
            sam_hard=st.slider("SAM share: steep penalty from", 0.02, 0.30, d.sam_hard, 0.01, format="%.2f"),
            sam_soft_penalty=st.slider("SAM penalty up to the steep threshold", 0.0, 30.0, d.sam_soft_penalty, 1.0),
            sam_hard_penalty=st.slider("Extra SAM penalty beyond it", 0.0, 40.0, d.sam_hard_penalty, 1.0),
            legal_points_per_level=st.slider("Points per legal-complexity level", 0.0, 8.0,
                                             d.legal_points_per_level, 0.5),
            integration_points_each=st.slider("Points per complex integration", 0.0, 8.0,
                                              d.integration_points_each, 0.5),
            solo_founder=st.toggle("Solo founder (Czech support is costly)", d.solo_founder),
            czech_support_penalty=st.slider("Czech-support penalty", 0.0, 10.0, d.czech_support_penalty, 0.5),
        )

    st.header("🌐 Live sources")
    sources = st.multiselect("Fetch fresh launches from", list(LIVE_SOURCES), default=list(LIVE_SOURCES))
    live_limit = st.slider("Items per source", 5, 30, 15)
    c1, c2 = st.columns(2)
    if c1.button("Fetch live", width="stretch", disabled=not sources):
        fetched: list[BusinessModel] = []
        for name in sources:
            with st.spinner(f"Fetching {name}..."):
                try:
                    fetched += LIVE_SOURCES[name](limit=live_limit)
                except Exception as e:
                    st.warning(f"{name}: {e}")
        ss.live_models = fetched
        st.toast(f"Fetched {len(fetched)} live launches")
    if c2.button("Clear live", width="stretch", disabled=not ss.live_models):
        ss.live_models = []
    st.caption("Indie Hackers has no public API - its revenue-transparent products are in the curated set.")

    with st.expander("➕ Add your own model"):
        with st.form("custom", clear_on_submit=True):
            name = st.text_input("Name *")
            url = st.text_input("URL")
            cat = st.selectbox("Category", CATEGORIES)
            niche = st.text_input("Niche")
            problem = st.text_area("Problem solved")
            rev_model = st.text_input("Revenue model", "Subscription SaaS")
            mrr = st.number_input("Known MRR (USD, 0 = unknown)", 0, 10_000_000, 0, 1000)
            price = st.number_input("Typical price (USD/month)", 1.0, 5000.0, 29.0)
            audience = st.radio("Audience", ["B2B", "B2C"], horizontal=True)
            sam = st.number_input("Serviceable customers in CZ", 100, 1_000_000, 5_000, 500)
            segs = st.text_input("Czech segments (comma separated)")
            demand = st.slider("Local demand", 1, 5, 3)
            comp = st.slider("Local competition", 1, 5, 3)
            cplx = st.slider("Build complexity", 1, 5, 3)
            if st.form_submit_button("Add") and name:
                ss.custom_models.append(with_cz_defaults(BusinessModel(
                    id=_id(name, "Custom"), name=name, url=url or "", category=cat, niche=niche or cat,
                    revenue_model=rev_model, mrr_usd=mrr or None, revenue_note="User-supplied",
                    problem=problem or niche, source="Custom", audience=audience, price_usd=price, cz_sam=sam,
                    demand=demand, competition=comp, complexity=cplx,
                    cz_segments=[s.strip() for s in segs.split(",") if s.strip()],
                )))
                st.toast(f"Added {name}")


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

@st.cache_data
def curated() -> list[BusinessModel]:
    return load_curated()


models: dict[str, BusinessModel] = {m.id: m for m in curated() + ss.live_models + ss.custom_models}

rows = []
czech_scores = {}
for m in models.values():
    q = quick_metrics(m, a)
    dm = derived_metrics(m, a, q)
    czech_scores[m.id] = czech_adjusted_score(q["score"], m, dm, weights)
    rows.append({"id": m.id, "Name": m.name, "Category": m.category, "Source": m.source, "Country": m.country, "Niche": m.niche,
                 "Score": q["score"], "Czech score": czech_scores[m.id].score, "Price (CZK)": q["price_czk"], "Customers M12": q["customers_m12"],
                 "CZK potential (M12 MRR)": q["mrr_czk_m12"], "Intl. MRR (USD)": m.mrr_usd,
                 "Revenue model": m.revenue_model, "Problem": m.problem, "Tech stack": ", ".join(m.tech_stack),
                 "URL": m.url})
df = pd.DataFrame(rows)

st.title("🇨🇿 Czech Business Model Radar")
st.caption("Discover proven small-business & micro-SaaS models worldwide and adapt them for Prague and the Czech market.")

# Filters
with st.container(border=True):
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1.4])
    query = f1.text_input("🔎 Search", placeholder="e.g. Shoptet, restaurant, AI")
    cats = f2.multiselect("Category", sorted(df["Category"].unique()))
    min_score = f3.slider("Min. feasibility score", 0, 100, 0, 5)
    sort_by = f4.selectbox("Sort by", ["Score", "CZK potential (M12 MRR)", "Intl. MRR (USD)", "Name"])
    g1, g2, g3 = st.columns([3, 2, 2])
    max_pot = int(df["CZK potential (M12 MRR)"].max()) + 1
    pot = g1.slider("Estimated CZK potential (month-12 MRR)", 0, max_pot, (0, max_pot), step=5_000,
                    format="%d CZK")
    countries = g2.multiselect("Country of origin", sorted(df["Country"].unique()))
    srcs = g3.multiselect("Source", sorted(df["Source"].unique()))

view_df = df[(df["Score"] >= min_score) & df["CZK potential (M12 MRR)"].between(*pot)]
if cats:
    view_df = view_df[view_df["Category"].isin(cats)]
if countries:
    view_df = view_df[view_df["Country"].isin(countries)]
if srcs:
    view_df = view_df[view_df["Source"].isin(srcs)]
if query:
    hay = (view_df["Name"] + " " + view_df["Niche"] + " " + view_df["Problem"] + " " + view_df["Category"] + " " + view_df["Country"]).str.lower()
    view_df = view_df[hay.str.contains(query.lower(), regex=False)]
view_df = view_df.sort_values(sort_by, ascending=sort_by == "Name", na_position="last")

k1, k5, k2, k3, k4 = st.columns([1, 0.8, 1, 1.2, 1.4])
k1.metric("Models shown", f"{len(view_df)} / {len(df)}")
k5.metric("Countries", view_df["Country"].nunique())
k2.metric("Avg. feasibility", f"{view_df['Score'].mean():.0f}" if len(view_df) else "-")
k3.metric("Median CZK potential", czk(view_df["CZK potential (M12 MRR)"].median()) if len(view_df) else "-")
k4.metric("Top pick", view_df.sort_values("Score", ascending=False).iloc[0]["Name"][:28] if len(view_df) else "-")

view = st.radio("View", VIEWS, key="view", horizontal=True, label_visibility="collapsed")


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #

def radar_view() -> None:
    if view_df.empty:
        st.info("No models match the filters.")
        return
    chart = (
        alt.Chart(view_df)
        .mark_circle(size=140, opacity=0.8)
        .encode(
            x=alt.X("Score:Q", title="Czech feasibility score", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("CZK potential (M12 MRR):Q", title="Month-12 MRR potential (CZK)", scale=alt.Scale(type="symlog")),
            color=alt.Color("Category:N", legend=alt.Legend(orient="bottom", columns=3)),
            tooltip=["Name", "Category", "Country", "Score", alt.Tooltip("CZK potential (M12 MRR):Q", format=",.0f"),
                     alt.Tooltip("Price (CZK):Q", format=",.0f")],
        )
        .properties(height=340, title="Opportunity map - top-right is best")
    )
    st.altair_chart(chart, width="stretch")

    page_size = 24
    n_pages = max(1, -(-len(view_df) // page_size))
    if ss.get("radar_page", 1) > n_pages:  # filters shrank the list
        ss.radar_page = n_pages
    p1, p2 = st.columns([1, 4])
    page =p1.number_input("Page", 1, n_pages, 1, key="radar_page") if n_pages > 1 else 1
    start = (page - 1) * page_size
    p2.caption(f"Showing {start + 1}-{min(start + page_size, len(view_df))} of {len(view_df)} models")

    cols = st.columns(3)
    for i, (_, r) in enumerate(view_df.iloc[start:start + page_size].iterrows()):
        m = models[r["id"]]
        score = int(r["Score"])
        with cols[i % 3].container(border=True):
            st.markdown(f"**[{m.name}]({m.url})**" if m.url else f"**{m.name}**")
            st.markdown(f":blue-badge[{m.category}] :green-badge[{m.country}] :gray-badge[{m.source}]")
            st.caption(m.niche)
            st.progress(score / 100, text=f"Feasibility **{score}**/100")
            c1, c2 = st.columns(2)
            c1.metric("Intl. MRR", f"${m.mrr_usd / 1000:,.0f}k" if m.mrr_usd else "n/a")
            c2.metric("CZK / month (M12)", f"{r['CZK potential (M12 MRR)'] / 1000:,.0f}k")
            with st.expander("Details"):
                st.write(f"**Problem:** {m.problem}")
                st.write(f"**Revenue model:** {m.revenue_model}")
                if m.tech_stack:
                    st.write(f"**Tech stack:** {', '.join(m.tech_stack)}")
                if m.cz_segments:
                    st.write(f"**Czech segments:** {', '.join(m.cz_segments)}")
                st.caption(m.revenue_note)
            st.button("🔬 Deep-Dive Czech Report", key=f"dd_{m.id}", width="stretch",
                      on_click=open_deep_dive, args=(m.id,), type="primary" if score >= 60 else "secondary")


def get_report(m: BusinessModel, force: bool = False) -> AnalysisResult | None:
    cache_key = (m.id, active, active_model, a.model_dump_json())
    if force or cache_key not in ss.reports:
        if not force and ss.run_for != m.id:
            return None
        with st.spinner(f"Asking {active_model} for a Czech deep-dive (can take a minute)..." if active_key
                        else "Running the Czech adaptation engine..."):
            ss.reports[cache_key] = analyze(m, a, engine=active, anthropic_key=anthropic_key, gemini_key=gemini_key,
                                            claude_model=claude_model, gemini_model=gemini_model)
        ss.run_for = None
    return ss.reports[cache_key]


def deep_dive_view() -> None:
    ids = list(models)
    if ss.selected_id not in models:
        ss.selected_id = view_df["id"].iloc[0] if len(view_df) else ids[0]
    # The widget key is separate from `selected_id` because Streamlit discards widget
    # state while the widget is not rendered (i.e. when another view is active).
    ss.dd_choice = ss.selected_id
    c1, c2 = st.columns([4, 1])
    c1.selectbox("Business model", ids, key="dd_choice",
                 format_func=lambda i: f"{models[i].name}  ·  {models[i].category}",
                 on_change=lambda: ss.update(selected_id=ss.dd_choice))
    m = models[ss.selected_id]
    has_report = get_report(m) is not None
    force = c2.button("🔄 Regenerate" if has_report else "🔬 Generate report", width="stretch", type="primary")
    res = get_report(m, force=force)
    if res is None:
        st.info("Click **Generate report** to run the Czech localisation analysis.")
        return
    for w in res.warnings:
        st.warning(w)

    r, e = res.report, res.report.unit_economics
    st.subheader(m.name)
    st.markdown(f"> {r.one_liner}")
    st.caption(("🤖 Generated by " + res.engine) if res.engine != "mock" else "⚡ Offline heuristic engine")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Czech Feasibility Score", f"{r.feasibility_score}/100", r.verdict,
              delta_color="normal" if r.feasibility_score >= 55 else "inverse")
    k2.metric("Month-12 MRR", czk(e.mrr_czk_m12), f"{e.customers_m12} customers", delta_color="off")
    k3.metric("Net profit / month (M12)", czk(e.net_profit_czk_m12))
    k4.metric("Break-even", f"{e.breakeven_customers} customers", e.legal_form, delta_color="off")

    t1, t2, t3, t4, t5, t6 = st.tabs(["🎯 Score", "👥 Audience", "💰 Unit economics", "🏁 Competition",
                                      "🗺️ 14-day roadmap", "⚠️ Risks & checklist"])
    with t1:
        sdf = pd.DataFrame([f.model_dump() for f in r.score_breakdown])
        st.altair_chart(
            alt.Chart(sdf).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("score:Q", scale=alt.Scale(domain=[0, 100]), title="Score"),
                y=alt.Y("factor:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                color=alt.Color("score:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[0, 100]), legend=None),
                tooltip=["factor", "score", alt.Tooltip("weight:Q", format=".0%"), "rationale"],
            ).properties(height=230),
            width="stretch",
        )
        st.dataframe(sdf, hide_index=True, width="stretch",
                     column_config={"weight": st.column_config.NumberColumn(format="percent"),
                                    "score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
    with t2:
        for aud in r.target_audiences:
            with st.container(border=True):
                st.markdown(f"**{aud.segment}** — {aud.size_estimate}")
                st.write(f"Pain: {aud.pain_point}")
                st.caption(f"Willingness to pay: {aud.willingness_to_pay}")
    with t3:
        st.markdown("**Pricing (CZK)**")
        st.dataframe(pd.DataFrame([t.model_dump() for t in e.price_tiers]), hide_index=True, width="stretch",
                     column_config={"price_czk": st.column_config.NumberColumn("Price (CZK)", format="%d")})
        proj = pd.DataFrame({"Month": [0, 3, 6, 12], "Customers": [0, e.customers_m3, e.customers_m6, e.customers_m12]})
        proj["MRR (CZK)"] = proj["Customers"] * e.arpu_czk
        proj["Monthly costs (CZK)"] = e.total_costs_czk
        long = proj.melt("Month", ["MRR (CZK)", "Monthly costs (CZK)"], var_name="Series", value_name="CZK")
        st.altair_chart(
            alt.Chart(long).mark_line(point=True).encode(
                x="Month:Q", y=alt.Y("CZK:Q", title="CZK / month"), color="Series:N",
                tooltip=["Month", "Series", alt.Tooltip("CZK:Q", format=",.0f")],
            ).properties(height=260, title="Revenue ramp vs. month-12 cost base"),
            width="stretch",
        )
        st.markdown("**Monthly operating costs in Czechia (at month 12)**")
        st.dataframe(pd.DataFrame([c.model_dump() for c in e.monthly_costs]), hide_index=True, width="stretch",
                     column_config={"czk_per_month": st.column_config.NumberColumn("CZK / month", format="%d")})
        st.info(f"**Legal form:** {e.legal_form}\n\n{e.tax_notes}", icon="🏛️")
    with t4:
        st.dataframe(pd.DataFrame([c.model_dump() for c in r.competitors]), hide_index=True, width="stretch",
                     column_config={"url": st.column_config.LinkColumn("URL")})
    with t5:
        cols = st.columns(len(r.gtm_plan) or 1)
        for i, step in enumerate(r.gtm_plan):
            with cols[i].container(border=True):
                st.markdown(f"#### {i + 1}. {step.title}")
                st.caption(step.days)
                for act in step.actions:
                    st.markdown(f"- {act}")
                st.success(f"KPI: {step.kpi}")
    with t6:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Risks**")
            for x in r.risks:
                st.markdown(f"- {x}")
            st.markdown("**Assumptions**")
            for x in r.assumptions:
                st.caption(f"• {x}")
        with c2:
            st.markdown("**Localisation checklist**")
            for i, x in enumerate(r.localization_checklist):
                st.checkbox(x, key=f"chk_{m.id}_{i}")

    st.divider()
    slug = "".join(ch if ch.isalnum() else "-" for ch in m.name.lower()).strip("-")[:40]
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button("⬇️ Export Markdown", to_markdown(m, res), f"czech-report-{slug}.md", "text/markdown",
                       width="stretch")
    try:
        d2.download_button("⬇️ Export PDF", to_pdf(m, res), f"czech-report-{slug}.pdf", "application/pdf",
                           width="stretch")
    except Exception as ex:  # font / rendering problems should never break the page
        d2.warning(f"PDF export unavailable: {ex}")


def table_view() -> None:
    st.dataframe(
        view_df.drop(columns=["id"]), hide_index=True, width="stretch", height=560,
        column_config={
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "CZK potential (M12 MRR)": st.column_config.NumberColumn(format="%d CZK"),
            "Price (CZK)": st.column_config.NumberColumn(format="%d"),
            "Intl. MRR (USD)": st.column_config.NumberColumn(format="$%d"),
            "URL": st.column_config.LinkColumn(),
        },
    )
    st.download_button("⬇️ Download CSV", view_df.drop(columns=["id"]).to_csv(index=False), "czech-radar.csv",
                       "text/csv")


def methodology_view() -> None:
    st.markdown("""
### How the radar works

**1. Sources.** A curated database of 500 proven models from 60+ countries (revenue figures are approximate,
self-reported numbers - an order-of-magnitude traction signal, not audited data), plus optional live feeds
from Hacker News *Show HN* (Algolia API) and Product Hunt (public RSS). You can also add your own ideas.

**2. Quick score (dashboard).** Every model carries Czech hints rated 1-5. The feasibility score is a weighted mix:

| Factor | Weight |
|---|---|
| Local demand | 28% |
| Competitive whitespace (inverse of local competition) | 20% |
| Build & ops simplicity | 14% |
| Regulatory ease | 10% |
| Localisation moat (advantage of being Czech-native) | 14% |
| Proven international traction (log of MRR) | 14% |

**3. CZK potential.** International price × USD/CZK × purchasing-power factor (B2B 0.75, B2C 0.60), rounded to
Czech price points, × customers at month 12 (serviceable market × adoption driven by demand & competition).

**4. Deep-Dive.** With an Anthropic or Gemini API key, the LLM refines the heuristic baseline into a full report
(audiences, CZK unit economics with OSVČ/paušální daň vs. s.r.o. overhead, local incumbents, 14-day GTM).
Without a key, the offline engine produces the same structure instantly.

**Caveats.** Tax figures (paušální daň bands, VAT threshold) are rounded 2026 approximations - always verify with
an accountant or *financnisprava.cz*. Competitor lists are starting points for your own research.
""")


{VIEWS[0]: radar_view, VIEWS[1]: deep_dive_view, VIEWS[2]: table_view, VIEWS[3]: methodology_view}[view]()
