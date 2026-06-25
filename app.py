"""
Lifecycle Planning Copilot
==========================
A cohort-based CLV and scenario planning tool for streaming households.
All data is synthetic. Transparent, driver-based model + Claude-powered
executive narratives.

Run:  streamlit run app.py
"""

import os

import pandas as pd
import streamlit as st

from src import claude_agent, narrative_agent
from src.charts import (
    clv_by_cohort, clv_by_dim, clv_vs_depth, engagement_vs_clv, health_vs_depth,
    impact_complexity_matrix, monetization_per_hour_by_dim, retention_by_segment,
    revenue_mix, scenario_impact,
)
from src.monetization_agent import (
    add_monetization_metrics, guardrail_segments, monetization_summary,
    portfolio_monetization_kpis,
)
from src.clv_agent import (
    FORMULA_EXPLAINERS, PLATFORM_AD_MONETIZATION_SHARE,
    SUBSCRIPTION_REVENUE_SHARE, payback_month, portfolio_kpis, run_clv_model,
)
from src.data_agent import ensure_synthetic_data, load_csv, validate_data
from src.insight_agent import compute_gap_insights
from src.prioritization_agent import (LIFT_FIELDS, QUAL_FIELDS,
                                      initiatives_table, score_initiatives)
from src.scenario_agent import ELASTICITY, apply_scenario, compare_scenario
from src.segmentation_agent import add_engagement_segments, segment_summary
from src.verifier_agent import verify_narrative
from src.utils import CLV_HORIZON_MONTHS, fmt_currency, fmt_num, fmt_pct, weighted_mean

st.set_page_config(page_title="Lifecycle Planning Copilot", page_icon="📺",
                   layout="wide")

# ---------------------------------------------------------------------------
# Styling: KPI cards, banner, takeaway cards (dark-blue theme)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
div[data-testid="stMetric"] {
    background: #14233A; border: 1px solid #2C4163; border-radius: 12px;
    padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.25);
}
div[data-testid="stMetricLabel"] { color: #9FB3D1; }
div[data-testid="stMetricValue"] { color: #E6EDF7; }
div[data-testid="stMetricValue"] > div {
    white-space: normal; overflow-wrap: break-word; line-height: 1.15;
}
.synthetic-banner {
    background: #152C4A; border: 1px solid #2E4F7A; border-radius: 8px;
    padding: 8px 14px; color: #9CC4F8; font-size: 0.85rem; margin-bottom: 8px;
}
.takeaway {
    background: #14233A; border-left: 4px solid #7C6CF0; border-radius: 8px;
    padding: 12px 16px; color: #E6EDF7; font-size: 0.92rem; height: 100%;
}
.takeaway b { color: #C4B5FD; }
.walkthrough {
    background: #14233A; border: 1px solid #2C4163; border-radius: 12px;
    padding: 16px 20px; color: #E6EDF7; font-size: 1.0rem; line-height: 2.0;
}
.walkthrough .num { color: #2BD9A9; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data pipeline (Data Agent -> Segmentation Agent -> CLV Agent)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_baseline(uploaded_bytes, discount_rate: float, eng_weights: tuple):
    """Run the full deterministic pipeline. Cached on inputs."""
    if uploaded_bytes is not None:
        import io
        raw = load_csv(io.BytesIO(uploaded_bytes))
    else:
        raw = ensure_synthetic_data()
    clean, errors, warnings = validate_data(raw)
    if errors:
        return None, errors, warnings
    clean = add_engagement_segments(clean, weights=eng_weights)
    clean = run_clv_model(clean, discount_rate)
    clean = add_monetization_metrics(clean)  # depth & guardrail scores
    return clean, errors, warnings


def page_header(title: str, subtitle: str, mode: str | None = None):
    """Consistent page title + one-line business framing.

    `mode` labels what kind of page this is, so the descriptive/forward split
    is always explicit: pages 1–3 & 6 describe where value sits today; pages
    4–5 model the impact of decisions not yet made.
    """
    st.title(title)
    if mode == "descriptive":
        st.caption("📊 **Descriptive** — where value sits today. " + subtitle)
    elif mode == "forward":
        st.caption("🔮 **Forward-looking** — modeled impact of initiatives, "
                   "computed through the CLV engine. " + subtitle)
    else:
        st.caption(subtitle)


def claude_section(title: str, generate_fn, key: str):
    """Render an AI Analyst commentary block with generate button + errors."""
    st.subheader(f"🪶 AI Analyst — {title}")
    st.caption("Drafted by Claude from the model outputs above. Every figure traces "
               "to the driver-based model — review before sharing, like any analyst "
               "draft.")
    if not claude_agent.is_configured():
        st.warning("**Claude is not configured.** Paste your API key in the sidebar, "
                   "or add `ANTHROPIC_API_KEY` to a `.env` file.", icon="🔑")
        return
    if st.button(f"Draft {title.lower()}", key=f"btn_{key}"):
        with st.spinner("Drafting..."):
            st.session_state[f"claude_{key}"] = generate_fn()
    result = st.session_state.get(f"claude_{key}")
    if result:
        if result["ok"]:
            st.markdown(result["text"])
            # Verifier: machine-check every figure against the model outputs
            # that were in the prompt — generated language never goes
            # unchecked (see src/verifier_agent.py).
            v = verify_narrative(result["text"], result.get("context") or {})
            if v["total"] and not v["unverified"]:
                st.caption(f"🛡️ **Verifier:** all {v['total']} figures cited above "
                           "trace to the model outputs provided to Claude.")
            elif v["unverified"]:
                st.warning(
                    f"🛡️ **Verifier:** {len(v['unverified'])} of {v['total']} figures "
                    "could not be traced directly to the model outputs: "
                    f"{', '.join(f'`{u}`' for u in v['unverified'][:6])}. "
                    "These may be legitimate derivations (e.g., a ratio of two "
                    "model figures) — confirm before sharing.", icon="🔎")
        else:
            st.error(result["error"], icon="⚠️")


def kpi_row(kpis: dict, top_initiative: str | None = None):
    cols = st.columns(6)
    cols[0].metric("Total households", fmt_num(kpis["total_households"]))
    cols[1].metric("Avg CLV (discounted)", fmt_currency(kpis["avg_clv"]))
    cols[2].metric("Total lifecycle value", fmt_currency(kpis["total_lifecycle_value"]))
    cols[3].metric("Avg month-6 retention", fmt_pct(kpis["avg_month_6_retention"]))
    cols[4].metric("Avg revenue / HH / mo", fmt_currency(kpis["avg_revenue_per_household"]))
    # Long names overflow the KPI card: truncate, full name in the tooltip.
    ti = top_initiative or "—"
    short = ti if len(ti) <= 22 else ti[:21].rstrip() + "…"
    cols[5].metric("Top initiative", short, help=ti if ti != short else None)


# ---------------------------------------------------------------------------
# Sidebar: navigation, data source, assumptions, Claude key
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📺 Lifecycle Planning Copilot")
    st.caption("Cohort CLV & scenario planning for streaming households. "
               "**All data is synthetic.**")

    page = st.radio("Navigate", [
        "1 · Executive Overview", "2 · Cohort Explorer", "3 · CLV Model",
        "4 · Scenario Planner", "5 · Initiative Prioritizer",
        "6 · Monetization Guardrails", "7 · Executive Memo",
    ], label_visibility="collapsed")

    st.divider()
    st.markdown("**Data source**")
    source = st.radio("Data source", ["Synthetic dataset", "Upload CSV"],
                      label_visibility="collapsed")
    uploaded_bytes = None
    if source == "Upload CSV":
        up = st.file_uploader("Upload cohort CSV", type="csv")
        if up is not None:
            uploaded_bytes = up.getvalue()
        with st.expander("Required columns"):
            from src.utils import REQUIRED_COLUMNS
            st.code("\n".join(REQUIRED_COLUMNS), language=None)

    st.divider()
    discount_rate = st.slider("Annual discount rate", 0.0, 0.25, 0.10, 0.01,
                              help="Used to discount monthly gross profit over the "
                                   "24-month CLV horizon.")
    acquisition_cost = st.number_input(
        "Acquisition cost / household ($)", min_value=0.0, max_value=200.0,
        value=8.0, step=1.0,
        help="Device subsidy + acquisition marketing per activated household — "
             "for a platform selling hardware near cost, a few dollars of "
             "subsidy plus marketing. Drives net CLV (gross CLV − CAC) and the "
             "payback month on the CLV Model page. Set to 0 for a "
             "gross-CLV-only view.")

    with st.expander("📐 Model assumptions"):
        st.markdown(f"""
- **CLV horizon:** {CLV_HORIZON_MONTHS} months; retention interpolated through
  observed months 1/3/6/12, extrapolated 13–24 at the months 6→12 decay rate.
- **Discount rate:** {discount_rate:.0%}/yr (adjustable above).
- **Acquisition cost:** ${acquisition_cost:.0f}/household (device subsidy +
  acquisition marketing — for a platform selling hardware near cost, the
  subsidy IS the CAC). Gross vs net CLV + payback on the CLV Model page.
- **Platform monetization** (calibrated to public platform disclosures —
  ~140 streaming hrs/HH/mo, blended revenue ≈ $4/HH/mo):
  - ad inventory capture: {PLATFORM_AD_MONETIZATION_SHARE:.0%} of the value a
    household generates (most viewing is in third-party apps)
  - subscription revenue share: {SUBSCRIPTION_REVENUE_SHARE:.0%} of ARPU
    (billing rev-share, not full subscription price)
- **Engagement → retention elasticities** (planning estimates — would be
  calibrated from experiments with real data):
  - first-week engagement: ×{ELASTICITY['first_week_to_retention']}
  - app installs: ×{ELASTICITY['app_install_to_retention']}
  - free-channel usage: ×{ELASTICITY['trc_to_retention']}
    (+×{ELASTICITY['trc_to_hours']} flow-through to streaming hours)
- **Experience risk penalty** (Scenario page): drags retention by
  penalty × (CPM + subscription lifts) AND streaming hours by
  ×{ELASTICITY['risk_to_hours']} × penalty × CPM lift — aggressive ad load
  partially cannibalizes its own hours-driven inventory.
- **Initiative scores:** financial columns are modeled through the CLV engine;
  1–5 qualitative scores are planning estimates (see Prioritizer page).
- **Monetization & experience scores:** transparent percentile blends —
  weights documented in `src/monetization_agent.py` (Guardrails page).
""")

    # Claude API key: read from .env if present, or paste directly in the app.
    if not claude_agent.is_configured():
        key_in = st.text_input(
            "Anthropic API key", type="password", placeholder="sk-ant-...",
            help="Held in memory for this session only — never written to disk. "
                 "Alternatively, set ANTHROPIC_API_KEY in a .env file.",
        )
        if key_in:
            os.environ["ANTHROPIC_API_KEY"] = key_in.strip()

    model_choice = st.selectbox(
        "Claude model", list(claude_agent.AVAILABLE_MODELS.keys()),
        format_func=lambda m: claude_agent.AVAILABLE_MODELS[m],
        help="Model used for all AI Analyst commentary and the executive memo. "
             "Sonnet is the sweet spot for this workload; Haiku for speed, "
             "Opus/Fable for the deepest drafting.")
    claude_agent.set_model(model_choice)

    st.caption("Claude API: " + ("✅ configured" if claude_agent.is_configured()
                                 else "❌ paste a key above or add it to `.env`"))

# Engagement-score weights (sliders live on the Cohort Explorer page;
# defaults set here so the pipeline has them on every page / first run)
for _k in ("ew_fw", "ew_ai", "ew_trc", "ew_hrs"):
    st.session_state.setdefault(_k, 1.0)
eng_weights = (st.session_state["ew_fw"], st.session_state["ew_ai"],
               st.session_state["ew_trc"], st.session_state["ew_hrs"])

# Run the deterministic pipeline
df, errors, warnings = load_baseline(uploaded_bytes, discount_rate, eng_weights)

st.markdown('<div class="synthetic-banner">🧪 All data in this tool is synthetic and '
            'illustrative. No real company data is used.</div>', unsafe_allow_html=True)

if errors:
    for e in errors:
        st.error(f"Data validation error: {e}")
    st.stop()
for wmsg in warnings:
    st.warning(f"Data quality: {wmsg}", icon="🔎")

# Initiative ranking is reused on several pages
@st.cache_data(show_spinner=False)
def ranked_initiatives(_df_hash, discount_rate):
    return score_initiatives(df, discount_rate)

_df_hash = int(pd.util.hash_pandas_object(df[["households", "discounted_clv"]]).sum())
ranked = ranked_initiatives(_df_hash, discount_rate)

# If the user customized initiatives on the Prioritizer page, use that
# ranking everywhere (overview KPI card, memo) for the rest of the session.
_custom = st.session_state.get("ranked_custom")
if _custom is not None and len(_custom):
    ranked = _custom
top_initiative = ranked.iloc[0]["initiative"]


# Gap insights (Insight Agent): the non-obvious story — gaps, vintage
# trends, marginal economics — reused on the Overview and in the Memo.
@st.cache_data(show_spinner=False)
def gap_insights_cached(_df_hash, discount_rate):
    return compute_gap_insights(df, discount_rate)

gaps = gap_insights_cached(_df_hash, discount_rate)


# ===========================================================================
# 1 · EXECUTIVE OVERVIEW
# ===========================================================================
if page.startswith("1"):
    page_header("Executive Overview",
                "How streaming household lifecycle behavior converts into lifetime "
                "value — and where to act first. Model is transparent and "
                "driver-based; AI accelerates the narrative.",
                mode="descriptive")

    kpis = portfolio_kpis(df)
    kpi_row(kpis, top_initiative)

    # --- Computed takeaways: the 'so what' strip (deterministic, not AI) ----
    seg = segment_summary(df, "engagement_segment").set_index("engagement_segment")
    mkt = segment_summary(df, "market")
    clv_premium = seg.loc["High", "avg_clv"] / seg.loc["Low", "avg_clv"] - 1
    m6_gap_pts = (seg.loc["High", "avg_month_6_retention"]
                  - seg.loc["Low", "avg_month_6_retention"]) * 100
    top_mkt = mkt.iloc[0]
    top_share = top_mkt["total_lifecycle_value"] / mkt["total_lifecycle_value"].sum()

    st.subheader("What the model says — beyond the obvious")
    um = gaps.get("under_monetized_opportunity")
    vt = gaps.get("vintage_trend")
    mr = gaps.get("marginal_retention_value")
    t1, t2, t3 = st.columns(3)
    if um:
        t1.markdown(
            f'<div class="takeaway"><b>Biggest under-monetized pocket.</b><br>'
            f'<b>{um["segment"]}</b> runs {um["experience_health"]:.0f}/100 '
            f'experience health yet yields <b>${um["segment_yield_per_hour"]:.3f}/hr</b> '
            f'vs ${um["portfolio_yield_per_hour"]:.3f} portfolio-wide — closing '
            f'half the gap is worth ≈ '
            f'<b>{fmt_currency(um["annual_value_of_closing_half_gap"])}/yr</b>.</div>',
            unsafe_allow_html=True)
    if vt:
        t2.markdown(
            f'<div class="takeaway"><b>Cohort vintage watch.</b><br>'
            f'The newest 3 cohorts arrive at <b>{vt["clv_delta_pct"]:+.0%} CLV</b> vs '
            f'the oldest 3 — <b>{vt["primary_driver"]}</b> explains it (month-6 '
            f'retention {vt["month_6_retention_delta_pts"]:+.1f} pts, revenue/HH '
            f'{vt["revenue_per_hh_delta_pct"]:+.1%}).</div>',
            unsafe_allow_html=True)
    if mr:
        t3.markdown(
            f'<div class="takeaway"><b>Where a retention point pays most.</b><br>'
            f'+1% retention is worth <b>${mr["best_value_per_hh_per_pct_lift"]:.2f}/HH</b> '
            f'in {mr["best_market"]} vs ${mr["worst_value_per_hh_per_pct_lift"]:.2f} in '
            f'{mr["worst_market"]} ({mr["spread_x"]}× spread) — at scale, '
            f'<b>{mr["largest_total_market"]}</b> adds the most total per point '
            f'({fmt_currency(mr["largest_total_per_pct_lift"])}).</div>',
            unsafe_allow_html=True)
    st.caption("Gap analysis, not levels: each card quantifies something the room "
               "does **not** already know — under-monetized pockets, vintage "
               "trends, marginal economics — recomputed live from the current "
               "dataset. Upload real data and these become real findings.")

    with st.expander("The familiar frame (orientation — what leadership already knows)"):
        st.markdown(
            f"- High-engagement households carry a **{clv_premium:.0%} CLV premium** "
            f"over low ({fmt_currency(seg.loc['High','avg_clv'])} vs "
            f"{fmt_currency(seg.loc['Low','avg_clv'])}).\n"
            f"- Month-6 retention runs **{m6_gap_pts:.0f} pts higher** in the "
            f"high-engagement segment — early behavior predicts lifetime value.\n"
            f"- **{top_mkt['market']}** holds **{top_share:.0%}** of total modeled "
            f"lifecycle value ({fmt_currency(top_mkt['total_lifecycle_value'])}).")

    with st.expander("Dataset coverage"):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.dataframe(
                df.groupby(["market", "region"]).agg(
                    cohorts=("cohort_month", "nunique"),
                    households=("households", "sum"),
                    avg_m6_retention=("month_6_retention", "mean"),
                    avg_clv=("discounted_clv", "mean"),
                ).round(2).reset_index(),
                width="stretch", hide_index=True,
            )
        with c2:
            st.metric("Cohort rows", fmt_num(len(df)))
            st.metric("Markets", fmt_num(df["market"].nunique()))
            st.metric("Cohort months", fmt_num(df["cohort_month"].nunique()))
            st.metric("Device types", fmt_num(df["device_type"].nunique()))

    claude_section("Portfolio overview",
                   lambda: narrative_agent.overview_insight(df, gaps), "overview")


# ===========================================================================
# 2 · COHORT EXPLORER
# ===========================================================================
elif page.startswith("2"):
    page_header("Cohort Explorer",
                "Slice the portfolio by market, region, device, cohort, and "
                "engagement segment to find where value concentrates — and why.",
                mode="descriptive")

    with st.expander("🎚️ What counts as “engaged”? — engagement score weights"):
        st.caption("The engagement score is a **weighted percentile blend** of four "
                   "behaviors. The weights are a planning choice, not a fact — move "
                   "them to stress-test how sensitive the segments (and every page "
                   "that uses them) are to the definition of engagement itself. "
                   "Re-segments the whole app live.")
        wc = st.columns(4)
        wc[0].slider("First-week hours", 0.0, 2.0, step=0.1, key="ew_fw",
                     help="Early habit formation.")
        wc[1].slider("First-week app installs", 0.0, 2.0, step=0.1, key="ew_ai",
                     help="Content breadth / onboarding success.")
        wc[2].slider("Free-channel (TRC) usage", 0.0, 2.0, step=0.1, key="ew_trc",
                     help="Owned-content engagement — the high-margin inventory.")
        wc[3].slider("Monthly streaming hours", 0.0, 2.0, step=0.1, key="ew_hrs",
                     help="Steady-state depth.")
        if sum(eng_weights) <= 0:
            st.warning("All weights are 0 — falling back to equal weights.",
                       icon="⚖️")

    f1, f2, f3, f4, f5 = st.columns(5)
    sel_market = f1.multiselect("Market", sorted(df["market"].unique()))
    sel_region = f2.multiselect("Region", sorted(df["region"].unique()))
    sel_device = f3.multiselect("Device type", sorted(df["device_type"].unique()))
    sel_cohort = f4.multiselect("Cohort month", sorted(df["cohort_month"].unique()))
    sel_segment = f5.multiselect("Engagement segment", ["High", "Medium", "Low"])

    view = df.copy()
    if sel_market:  view = view[view["market"].isin(sel_market)]
    if sel_region:  view = view[view["region"].isin(sel_region)]
    if sel_device:  view = view[view["device_type"].isin(sel_device)]
    if sel_cohort:  view = view[view["cohort_month"].isin(sel_cohort)]
    if sel_segment: view = view[view["engagement_segment"].isin(sel_segment)]

    if view.empty:
        st.info("No rows match the current filters.")
        st.stop()

    kpi_row(portfolio_kpis(view), top_initiative)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(clv_by_dim(segment_summary(view, "market"), "market",
                                   "Average CLV by market"), width="stretch")
        st.caption("**Read:** monetization (CPM, ARPU) and retention differences "
                   "compound — the CLV spread across markets is the international "
                   "opportunity sizing.")
    with c2:
        st.plotly_chart(clv_by_cohort(segment_summary(view, "cohort_month")),
                        width="stretch")
        st.caption("**Read:** cohort-over-cohort CLV trend. Holiday-quarter cohorts "
                   "run larger but slightly lower-intent — watch the Jan/Dec dips.")
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(retention_by_segment(view), width="stretch")
        st.caption("**Read:** the high-engagement curve is flatter, not just higher — "
                   "early engagement changes the *slope* of decay, which is what "
                   "compounds into CLV.")
    with c4:
        st.plotly_chart(engagement_vs_clv(view), width="stretch")
        st.caption("**Read:** each bubble is a cohort × market × device cell. The "
                   "upward sweep is the engagement→CLV relationship the initiatives "
                   "are designed to exploit.")

    filters = {"market": sel_market or "all", "region": sel_region or "all",
               "device_type": sel_device or "all", "cohort_month": sel_cohort or "all",
               "engagement_segment": sel_segment or "all"}
    claude_section("Cohort insights",
                   lambda: narrative_agent.cohort_insights(view, filters), "cohort")


# ===========================================================================
# 3 · CLV MODEL
# ===========================================================================
elif page.startswith("3"):
    page_header("CLV Model",
                "Every number is auditable — a finance partner could rebuild this "
                "page in Excel. No black boxes.",
                mode="descriptive")

    # --- Scope: walk the model for any market/device slice ------------------
    s1, s2, _sp = st.columns([1, 1, 2])
    view_mkt = s1.selectbox("Market", ["All markets"] + sorted(df["market"].unique()))
    view_dev = s2.selectbox("Device type",
                            ["All devices"] + sorted(df["device_type"].unique()))
    mdf = df
    if view_mkt != "All markets":
        mdf = mdf[mdf["market"] == view_mkt]
    if view_dev != "All devices":
        mdf = mdf[mdf["device_type"] == view_dev]
    if mdf.empty:
        st.info("No cohort rows for this market × device combination.")
        st.stop()
    scope_lbl = ", ".join(x for x in (view_mkt, view_dev)
                          if not x.startswith("All")) or "portfolio"

    kpis = portfolio_kpis(mdf)
    w = mdf["households"]

    # --- Follow one average household through the model ---------------------
    avg_ad = weighted_mean(mdf["ad_revenue_per_household"], w)
    avg_sub = weighted_mean(mdf["subscription_revenue_per_household"], w)
    avg_rev = weighted_mean(mdf["total_monthly_revenue_per_household"], w)
    avg_margin = weighted_mean(mdf["gross_margin"], w)
    avg_support = weighted_mean(mdf["support_cost_per_household"], w)
    avg_gp = kpis["avg_gross_profit_per_household"]
    avg_months = kpis["avg_expected_retained_months"]
    avg_clv_undisc = weighted_mean(mdf["baseline_clv"], w)

    st.subheader(f"Follow one average household through the model — {scope_lbl}")
    st.markdown(
        f'<div class="walkthrough">'
        f'<span class="num">{fmt_currency(avg_ad)}</span> ad revenue '
        f'+ <span class="num">{fmt_currency(avg_sub)}</span> subscription revenue '
        f'= <span class="num">{fmt_currency(avg_rev)}</span> revenue / month &nbsp;→&nbsp; '
        f'× <span class="num">{avg_margin:.0%}</span> gross margin '
        f'− <span class="num">{fmt_currency(avg_support)}</span> support cost '
        f'= <span class="num">{fmt_currency(avg_gp)}</span> gross profit / month &nbsp;→&nbsp; '
        f'× <span class="num">{avg_months:.1f}</span> expected retained months '
        f'= <span class="num">{fmt_currency(avg_clv_undisc)}</span> lifetime gross profit '
        f'&nbsp;→&nbsp; discounted at <span class="num">{discount_rate:.0%}</span>/yr '
        f'= <span class="num">{fmt_currency(kpis["avg_clv"])}</span> gross CLV'
        + (f' &nbsp;→&nbsp; − <span class="num">{fmt_currency(acquisition_cost)}</span> '
           f'acquisition cost = <span class="num">'
           f'{fmt_currency(kpis["avg_clv"] - acquisition_cost)}</span> net CLV'
           if acquisition_cost > 0 else "")
        + f'</div>', unsafe_allow_html=True)
    st.caption("This is the whole model in one line — five drivers, two minutes to "
               "explain. Each driver is a lever the planning team can act on.")

    # --- Gross vs net CLV: the CLV-vs-CAC lens -------------------------------
    st.subheader("Gross vs net CLV — and payback")
    net_clv = kpis["avg_clv"] - acquisition_cost
    pb = payback_month(mdf, discount_rate, acquisition_cost)
    n = st.columns(5)
    n[0].metric("Gross CLV (discounted)", fmt_currency(kpis["avg_clv"]))
    n[1].metric("Acquisition cost / HH", fmt_currency(acquisition_cost))
    n[2].metric("Net CLV", fmt_currency(net_clv),
                delta=None if net_clv >= 0 else "underwater")
    n[3].metric("CLV : CAC",
                f"{kpis['avg_clv'] / acquisition_cost:.1f}x"
                if acquisition_cost > 0 else "—")
    n[4].metric("Payback month",
                "Immediate" if pb == 0 else
                (f"Month {pb}" if pb else f"> {CLV_HORIZON_MONTHS} mo"))
    st.caption("**Gross CLV** values a household once acquired; **net CLV** "
               "subtracts what it cost to acquire it — device subsidy + "
               "acquisition marketing (sidebar assumption). Payback = first month "
               "cumulative discounted gross profit covers the acquisition cost. "
               "Scenario and Prioritizer pages model already-acquired households, "
               "so their incremental values are unaffected by CAC.")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.plotly_chart(revenue_mix(kpis), width="stretch")
        st.caption(f"**Read:** ads carry {kpis['ad_revenue_share']:.0%} of household "
                   "revenue — engagement (hours watched) is the primary monetization "
                   "engine; subscriptions are the upside lever.")
    with c2:
        st.subheader("Formulas in plain English")
        for name, formula, why in FORMULA_EXPLAINERS:
            with st.expander(f"**{name}**"):
                st.code(formula, language=None)
                st.caption(why)

    st.subheader("CLV by market, device type, and behavior segment")
    t1, t2, t3 = st.tabs(["By market", "By device type", "By engagement segment"])
    with t1:
        st.plotly_chart(clv_by_dim(segment_summary(df, "market"), "market",
                                   "Average CLV by market"), width="stretch")
    with t2:
        st.plotly_chart(clv_by_dim(segment_summary(df, "device_type"), "device_type",
                                   "Average CLV by device type"), width="stretch")
    with t3:
        st.plotly_chart(clv_by_dim(segment_summary(df, "engagement_segment"),
                                   "engagement_segment",
                                   "Average CLV by engagement segment"),
                        width="stretch")

    with st.expander("Baseline cohort-level calculations (auditable detail)"):
        show_cols = ["cohort_month", "market", "device_type", "engagement_segment",
                     "households", "ad_revenue_per_household",
                     "subscription_revenue_per_household",
                     "total_monthly_revenue_per_household", "gross_profit_per_household",
                     "expected_retained_months", "baseline_clv", "discounted_clv"]
        st.dataframe(mdf[show_cols].round(2), width="stretch", hide_index=True,
                     height=320)

    claude_section("CLV driver interpretation",
                   lambda: narrative_agent.clv_driver_explanation(df), "clv")


# ===========================================================================
# 4 · SCENARIO PLANNER
# ===========================================================================
elif page.startswith("4"):
    page_header("Scenario Planner",
                "Move the levers, watch CLV respond. Engagement lifts flow into "
                "retention through the documented elasticities in the sidebar "
                "assumptions.",
                mode="forward")

    with st.expander("📏 What this page measures — and where the numbers come from"):
        st.markdown(f"""
**What a scenario measures:** the *steady-state, run-rate* impact of an
initiative once its lifts are fully realized — (scenario − baseline)
discounted lifecycle value over the {CLV_HORIZON_MONTHS}-month horizon, for
the households in scope below. It is **not** a launch ramp: in a real cycle
the lift would phase in over an adoption curve, so treat this as the value
of the destination, not the journey.

**Where the elasticities come from:** documented planning assumptions
(top of `src/scenario_agent.py`, also in the sidebar) — first-week→retention
×{ELASTICITY['first_week_to_retention']}, installs→retention
×{ELASTICITY['app_install_to_retention']}, free-channel→retention
×{ELASTICITY['trc_to_retention']} (+×{ELASTICITY['trc_to_hours']} flow-through
to hours). With real data these would be calibrated from historical A/B
tests and holdout experiments.

**Margin on initiatives:** there is no per-initiative margin — incremental
revenue flows through each cohort's existing gross margin, and the cost
field is a one-time program cost used only for ROI / payback.

**Experience risk penalty:** two modeled effects — retention drops by
penalty × (CPM + subscription lifts), and streaming hours drop by
×{ELASTICITY['risk_to_hours']} × penalty × CPM lift. Because ad revenue is
hours-driven, an aggressive ad push partially cannibalizes its own
inventory — the trade-off is self-limiting by design.
""")

    # --- Scope: run the scenario against a specific population --------------
    sc1, sc2, sc3 = st.columns(3)
    scope_mkt = sc1.selectbox("Scope: market",
                              ["All markets"] + sorted(df["market"].unique()))
    scope_dev = sc2.selectbox("Scope: device type",
                              ["All devices"] + sorted(df["device_type"].unique()))
    scope_seg = sc3.selectbox("Scope: engagement segment",
                              ["All segments", "High", "Medium", "Low"])
    sdf = df
    if scope_mkt != "All markets":
        sdf = sdf[sdf["market"] == scope_mkt]
    if scope_dev != "All devices":
        sdf = sdf[sdf["device_type"] == scope_dev]
    if scope_seg != "All segments":
        sdf = sdf[sdf["engagement_segment"] == scope_seg]
    if sdf.empty:
        st.info("No households match this scope — widen the filters above.")
        st.stop()
    scope_label = ", ".join(x for x in (scope_mkt, scope_dev, scope_seg)
                            if not x.startswith("All")) or "All households"
    st.caption(f"🎯 Scenario applies to **{int(sdf['households'].sum()):,} "
               f"households** in scope: **{scope_label}** — all impact figures "
               "below are for this population only.")

    SLIDER_KEYS = {"fw": 0.0, "ai": 0.0, "trc": 0.0, "sub": 0.0,
                   "ret": 0.0, "cpm": 0.0, "gm": 0.0, "xrisk": 0.0}
    for k, v in SLIDER_KEYS.items():
        st.session_state.setdefault(f"sc_{k}", v)
    st.session_state.setdefault("sc_cost", 0)

    def set_preset(vals: dict):
        """Preset buttons: set slider state before widgets render."""
        for k, v in SLIDER_KEYS.items():
            st.session_state[f"sc_{k}"] = vals.get(k, 0.0)
        st.session_state["sc_cost"] = vals.get("cost", 0)

    st.markdown("**Start from a preset** *(mirrors the initiative portfolio)* "
                "**or build your own:**")
    p1, p2, p3, p4 = st.columns(4)
    p1.button("🚀 Onboarding push", width="stretch", on_click=set_preset,
              args=({"fw": 0.15, "ai": 0.10, "cost": 750_000},))
    p2.button("📺 Engagement push", width="stretch", on_click=set_preset,
              args=({"trc": 0.20, "cost": 900_000},))
    p3.button("💰 Monetization push", width="stretch", on_click=set_preset,
              args=({"cpm": 0.10, "sub": 0.15, "cost": 600_000},))
    p4.button("↩️ Reset to baseline", width="stretch", on_click=set_preset, args=({},))

    with st.container(border=True):
        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown("**Engagement levers**")
            fw = st.slider("First-week engagement lift", 0.0, 0.50, step=0.01,
                           key="sc_fw", help="Also lifts retention ×0.25 elasticity.")
            ai = st.slider("App install / onboarding lift", 0.0, 0.50, step=0.01,
                           key="sc_ai", help="Also lifts retention ×0.15 elasticity.")
            trc = st.slider("Roku-Channel-style usage lift", 0.0, 0.50, step=0.01,
                            key="sc_trc", help="Also lifts hours ×0.40 and retention "
                                               "×0.20 elasticity.")
        with g2:
            st.markdown("**Conversion & monetization**")
            sub = st.slider("Subscription conversion lift", 0.0, 0.50, step=0.01,
                            key="sc_sub")
            cpm = st.slider("CPM / ad monetization lift", 0.0, 0.50, step=0.01,
                            key="sc_cpm")
        with g3:
            st.markdown("**Retention & economics**")
            ret = st.slider("Retention lift (direct)", 0.0, 0.30, step=0.01,
                            key="sc_ret")
            gm = st.slider("Gross margin change (pts)", -0.10, 0.10, step=0.01,
                           key="sc_gm")
            xrisk = st.slider("Experience risk penalty", 0.0, 0.50, step=0.05,
                              key="sc_xrisk",
                              help="Guardrail with two effects: retention falls by "
                                   "penalty × (CPM + subscription lifts), and "
                                   "streaming hours fall by 0.5 × penalty × CPM "
                                   "lift — so aggressive ad load also cannibalizes "
                                   "its own hours-driven ad revenue. 0 = assume "
                                   "monetization does no harm.")
            initiative_cost = st.number_input("Initiative cost (optional, $)",
                                              min_value=0, step=50_000, key="sc_cost")

    scenario = {"first_week_lift": fw, "app_install_lift": ai, "trc_usage_lift": trc,
                "sub_conversion_lift": sub, "retention_lift": ret, "cpm_lift": cpm,
                "gross_margin_change": gm, "experience_risk_penalty": xrisk}

    # Plain-language statement of assumptions
    labels = [("first_week_lift", "first-week engagement"),
              ("app_install_lift", "onboarding app installs"),
              ("trc_usage_lift", "free-channel usage"),
              ("sub_conversion_lift", "subscription conversion"),
              ("retention_lift", "retention (direct)"),
              ("cpm_lift", "CPM"), ("gross_margin_change", "gross margin (pts)"),
              ("experience_risk_penalty", "experience risk penalty")]
    parts = [f"{name} **{scenario[key]:+.0%}**" for key, name in labels if scenario[key]]
    if parts:
        cost_txt = (f", at a one-time cost of **{fmt_currency(initiative_cost, 0)}**"
                    if initiative_cost else "")
        st.markdown("🎯 **This scenario assumes:** " + ", ".join(parts) + cost_txt + ".")
    else:
        st.markdown("🎯 **Baseline** — no lifts applied. Pick a preset or move a "
                    "slider to model an initiative.")

    scen_df = apply_scenario(sdf, scenario, discount_rate)
    cmp = compare_scenario(sdf, scen_df, initiative_cost or None)
    base, scen = cmp["baseline"], cmp["scenario"]

    c = st.columns(6)
    c[0].metric("Avg CLV", fmt_currency(scen["avg_clv"]),
                delta=fmt_currency(scen["avg_clv"] - base["avg_clv"]))
    c[1].metric("Total lifecycle value", fmt_currency(scen["total_lifecycle_value"]),
                delta=fmt_currency(cmp["incremental_value"]))
    c[2].metric("Revenue / HH / mo", fmt_currency(scen["avg_revenue_per_household"]),
                delta=fmt_currency(scen["avg_revenue_per_household"]
                                   - base["avg_revenue_per_household"]))
    c[3].metric("Gross profit / HH / mo", fmt_currency(scen["avg_gross_profit_per_household"]),
                delta=fmt_currency(scen["avg_gross_profit_per_household"]
                                   - base["avg_gross_profit_per_household"]))
    c[4].metric("Incremental value", fmt_currency(cmp["incremental_value"]),
                delta=fmt_pct(cmp["clv_lift_pct"]) + " CLV lift")
    if cmp["roi"] is not None:
        payback = ("∞" if cmp["payback_months"] == float("inf")
                   else f"{cmp['payback_months']:.1f} mo payback")
        c[5].metric("ROI proxy", f"{cmp['roi']:.1f}x", delta=payback)
    else:
        c[5].metric("ROI proxy", "—", help="Enter an initiative cost to see ROI/payback.")

    st.plotly_chart(scenario_impact(cmp), width="stretch")
    st.caption("**Read:** incremental value = (scenario − baseline) total discounted "
               "lifecycle value across all households. ROI = incremental value ÷ "
               "one-time cost; payback assumes value accrues evenly over the "
               "24-month horizon.")

    # --- Monetization depth & experience guardrail read-out -----------------
    st.subheader("Monetization & experience guardrails")
    scen_m = add_monetization_metrics(scen_df)
    w_b, w_s = sdf["households"], scen_m["households"]
    base_mph = float((sdf["monetization_per_streaming_hour"] * w_b).sum() / w_b.sum())
    scen_mph = float((scen_m["monetization_per_streaming_hour"] * w_s).sum() / w_s.sum())
    base_m6 = base["avg_month_6_retention"]
    scen_m6 = scen["avg_month_6_retention"]
    m6_delta_pts = (scen_m6 - base_m6) * 100
    base_hrs = float((sdf["monthly_streaming_hours"] * w_b).sum() / w_b.sum())
    scen_hrs = float((scen_m["monthly_streaming_hours"] * w_s).sum() / w_s.sum())

    g = st.columns(4)
    g[0].metric("Monetization / streaming hour", f"${scen_mph:.3f}",
                delta=f"{(scen_mph / base_mph - 1):+.1%}" if base_mph else None)
    g[1].metric("Month-6 retention", fmt_pct(scen_m6), delta=f"{m6_delta_pts:+.1f} pts")
    g[2].metric("Streaming hours / HH / mo", f"{scen_hrs:,.0f}",
                delta=f"{(scen_hrs / base_hrs - 1):+.1%}" if base_hrs else None)
    g[3].metric("Incremental CLV / HH", fmt_currency(cmp["incremental_clv_per_household"]))

    # Deterministic balanced recommendation (the guardrail verdict)
    monetization_up = scen_mph > base_mph * 1.001
    if cmp["incremental_value"] > 0 and m6_delta_pts >= -0.5:
        st.success("**Balanced ✓** — value up with experience protected "
                   f"(retention {m6_delta_pts:+.1f} pts). This scenario passes the "
                   "guardrail: monetization deepens without trading away retention.",
                   icon="✅")
    elif cmp["incremental_value"] > 0 and m6_delta_pts < -0.5:
        st.warning("**Guardrail flag** — the scenario creates value but drags "
                   f"month-6 retention {m6_delta_pts:+.1f} pts. Short-term revenue may "
                   "be borrowing from lifetime value; consider pairing with an "
                   "engagement or onboarding lever.", icon="⚠️")
    elif monetization_up:
        st.warning("**Net negative** — monetization per hour rises but total "
                   "lifecycle value falls. The experience cost outweighs the "
                   "revenue gain at these settings.", icon="🚫")
    else:
        st.info("Move a lever (or pick a preset) to evaluate the "
                "monetization-vs-experience trade-off.", icon="🎛️")

    # Persist for the Executive Memo page
    st.session_state["last_scenario"] = scenario
    st.session_state["last_comparison"] = cmp
    st.session_state["last_scope"] = scope_label
    st.session_state["last_guardrails"] = {
        "monetization_per_hour_baseline": round(base_mph, 4),
        "monetization_per_hour_scenario": round(scen_mph, 4),
        "month_6_retention_delta_pts": round(m6_delta_pts, 2),
        "streaming_hours_change_pct": round(scen_hrs / base_hrs - 1, 4) if base_hrs else 0,
    }

    claude_section("Scenario read-out",
                   lambda: narrative_agent.scenario_interpretation(
                       cmp, scenario, st.session_state.get("last_guardrails"),
                       scope_label),
                   "scenario")


# ===========================================================================
# 5 · INITIATIVE PRIORITIZER
# ===========================================================================
elif page.startswith("5"):
    page_header("Initiative Prioritizer",
                "Initiatives are inputs, not facts: edit the assumptions below — "
                "or add your own — and the ranking recomputes through the CLV "
                "engine instantly.",
                mode="forward")

    with st.expander("📊 How scoring works (methodology)"):
        st.markdown("""
**Where initiatives come from:** each row is a planning hypothesis with three kinds
of input assumptions — *driver lifts* (which model levers it moves, sized from
experiments, benchmarks, or product-team estimates), *cost* (one-time investment),
and *1–5 qualitative scores* from cross-functional sizing sessions.

**Financial columns are modeled, not guessed** — each initiative's driver lifts run
through the same CLV engine as the Scenario Planner, against the current dataset.

**Composite score (0–100):** 30% incremental value · 15% CLV lift % · 15% ROI ·
10% confidence · 10% speed to impact · 10% strategic fit · −10% complexity ·
−10% risk.

**Classification:** meaningful modeled lift + low complexity = **Quick win** ·
meaningful lift + high complexity = **Strategic bet** · no direct driver lift =
**Enabler** (value is indirect: infrastructure, measurement, decision speed).

**Modeled metric definitions** (both computed, not judged):
*Monetization lift* = % change in revenue per household per month when the
initiative's driver lifts run through the CLV engine against the current
dataset. *Experience impact* = blended modeled % change in the experience
drivers the initiative moves — 50% month-6 retention, 30% steady-state
streaming hours, 20% first-week hours. *Retention risk* (1–5) is the one
judgment call in the balanced score: a planning estimate of how likely the
initiative is to degrade the experience, editable in Step 1.

**What the financial columns measure:** the same steady-state, run-rate
impact as the Scenario Planner — the value once the lift is fully realized,
not the launch ramp.
""")

    # --- Editable input assumptions ------------------------------------------
    st.subheader("Step 1 — Initiative assumptions (inputs · editable)")
    st.caption("➕ **This is where you add your own project:** click the empty row "
               "at the bottom of the table, give it a name, set the driver lifts "
               "it would move (0–0.50 = 0–50%), its one-time cost, and 1–5 "
               "planning scores — the ranking below recomputes its modeled "
               "financials through the CLV engine instantly. Every preset row is "
               "editable the same way.")
    pct_cfg = {f: st.column_config.NumberColumn(format="%.2f", min_value=0.0,
                                                max_value=0.5, step=0.01)
               for f in LIFT_FIELDS}
    qual_cfg = {q: st.column_config.NumberColumn(format="%d", min_value=1,
                                                 max_value=5, step=1)
                for q in QUAL_FIELDS}
    edited = st.data_editor(
        initiatives_table(), num_rows="dynamic", key="init_editor",
        width="stretch", hide_index=True,
        column_config={
            "initiative": st.column_config.TextColumn(width="medium"),
            "thesis": st.column_config.TextColumn(width="large"),
            "cost": st.column_config.NumberColumn(format="$%d", min_value=0,
                                                  step=50_000),
            **pct_cfg, **qual_cfg,
        },
    )

    ranked = score_initiatives(df, discount_rate, edited)
    st.session_state["ranked_custom"] = ranked
    if ranked.empty:
        st.info("Add at least one initiative with a name to see the ranking.")
        st.stop()

    st.subheader("Step 2 — Modeled ranking (outputs · computed)")
    display = ranked.copy()
    display["incremental_value"] = display["incremental_value"].map(lambda v: f"${v:,.0f}")
    display["clv_lift_pct"] = display["clv_lift_pct"].map(lambda v: f"{v:.1%}")
    display["monetization_lift"] = display["monetization_lift"].map(lambda v: f"{v:+.1%}")
    display["experience_impact"] = display["experience_impact"].map(lambda v: f"{v:+.1%}")
    display["roi"] = display["roi"].map(lambda v: f"{v:.1f}x")
    display["payback_months"] = display["payback_months"].map(
        lambda v: "∞" if v in (None, float("inf")) else f"{v:.1f}")
    display["cost"] = display["cost"].map(lambda v: f"${v:,.0f}")
    st.dataframe(
        display[["rank", "initiative", "classification", "balanced_score",
                 "monetization_lift", "experience_impact", "retention_risk",
                 "incremental_value", "clv_lift_pct", "roi", "payback_months",
                 "cost", "score"]],
        width="stretch", hide_index=True,
    )
    st.caption("**Read:** ranked by **balanced score** — monetization lift counts, "
               "but only when experience impact is healthy and retention risk is "
               "contained. The legacy revenue-weighted `score` is kept for "
               "comparison: where the two diverge is exactly where a "
               "revenue-only ranking would over-fund experience-risky work. "
               "Monetization lift and experience impact are modeled through the "
               "CLV engine; retention risk (1–5) is a planning estimate, editable "
               "in Step 1.")

    st.plotly_chart(impact_complexity_matrix(ranked), width="stretch")
    st.caption("**Read:** top-left is where planning teams want to live — high "
               "modeled impact, low execution complexity. Bubble size = composite "
               "score.")

    # --- Now / Next / Foundational roadmap ----------------------------------
    st.subheader("Planning sequence")
    r1, r2, r3 = st.columns(3)
    buckets = {"Quick win": [], "Strategic bet": [], "Enabler": []}
    for _, r in ranked.iterrows():
        buckets[r["classification"]].append(
            f"**{r['initiative']}** — {fmt_currency(r['incremental_value'])} "
            f"modeled, {r['roi']:.1f}x ROI" if r["roi"] else f"**{r['initiative']}**")
    with r1:
        st.success("**Now — quick wins**\n\nFund this quarter; low complexity, "
                   "modeled impact above median.")
        for line in buckets["Quick win"]:
            st.markdown(f"- {line}")
    with r2:
        st.info("**Next — strategic bets**\n\nStage-gate: fund discovery now, "
                "scale on evidence.")
        for line in buckets["Strategic bet"]:
            st.markdown(f"- {line}")
    with r3:
        st.warning("**Foundational — enablers**\n\nFund for decision speed and "
                   "measurement, not modeled CLV.")
        for line in buckets["Enabler"]:
            st.markdown(f"- {line}")

    with st.expander("Initiative theses"):
        for _, r in ranked.iterrows():
            st.markdown(f"**{r['initiative']}** — {r['thesis']}")

    claude_section("Prioritization rationale",
                   lambda: narrative_agent.prioritization_rationale(ranked), "prior")


# ===========================================================================
# 6 · MONETIZATION DEPTH & EXPERIENCE GUARDRAILS
# ===========================================================================
elif page.startswith("6"):
    page_header("Monetization Depth & Experience Guardrails",
                "Are we monetizing engaged households effectively — and is "
                "monetization ever coming at the expense of engagement, retention, "
                "or long-term CLV? Scores are transparent percentile blends "
                "(weights in `src/monetization_agent.py`).",
                mode="descriptive")

    mk = portfolio_monetization_kpis(df)
    c = st.columns(6)
    c[0].metric("Avg revenue / HH / mo", fmt_currency(mk["avg_revenue_per_household"]))
    c[1].metric("Monetization / streaming hr", f"${mk['avg_monetization_per_hour']:.3f}")
    c[2].metric("Avg CLV", fmt_currency(portfolio_kpis(df)["avg_clv"]))
    c[3].metric("Avg experience health", f"{mk['avg_experience_health']:.0f} / 100")
    c[4].metric("Top under-monetized", mk["top_under_monetized"])
    c[5].metric("Highest experience risk", mk["top_experience_risk"])

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(monetization_per_hour_by_dim(
            monetization_summary(df, "market"), "market",
            "Monetization per streaming hour by market"), width="stretch")
        st.caption("**Read:** yield on attention. A low bar with healthy engagement "
                   "is an under-monetization gap, not a demand problem — pricing, "
                   "fill, and subscription attach are the levers.")
    with c2:
        st.plotly_chart(monetization_per_hour_by_dim(
            monetization_summary(df, "device_type"), "device_type",
            "Monetization per streaming hour by device type"), width="stretch")
        st.caption("**Read:** device mix shapes monetizable inventory — partner-TV "
                   "households often watch plenty but monetize lighter.")

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(health_vs_depth(df), width="stretch")
        st.caption("**Read:** the guardrail map. **Top-left** = engaged but "
                   "under-monetized — safest place to deepen monetization. "
                   "**Bottom-right** = monetizing hard with weak experience — "
                   "revenue that may be borrowing from lifetime value.")
    with c4:
        st.plotly_chart(clv_vs_depth(df), width="stretch")
        st.caption("**Read:** depth and CLV should rise together. Deep-monetization "
                   "cells colored red/orange (weak experience) are the ones to "
                   "watch — their CLV depends on a retention curve under stress.")

    g = guardrail_segments(df)
    show_cols = ["segment", "households", "revenue_per_household",
                 "monetization_per_streaming_hour", "monetization_depth_score",
                 "experience_health_score", "balanced_value_score", "avg_clv",
                 "avg_month_6_retention"]
    t1, t2, t3 = st.tabs(["🎯 Engaged, under-monetized", "⚠️ Monetized, experience risk",
                          "🏆 Best balanced value"])
    with t1:
        st.caption("High experience health, low monetization depth — these cohorts "
                   "already love the product; subscription attach and yield levers "
                   "can deepen monetization with the least experience risk.")
        st.dataframe(g["under_monetized"][show_cols].round(2), width="stretch",
                     hide_index=True)
    with t2:
        st.caption("High monetization depth, weak experience health — current "
                   "revenue may be unsustainable. Pair any further monetization "
                   "with engagement/onboarding investment, or expect churn to "
                   "claw it back.")
        st.dataframe(g["experience_risk"][show_cols].round(2), width="stretch",
                     hide_index=True)
    with t3:
        st.caption("The healthiest monetization opportunities: strong on both "
                   "axes with retention intact — the playbooks to study and "
                   "replicate elsewhere.")
        st.dataframe(g["best_balanced"][show_cols].round(2), width="stretch",
                     hide_index=True)

    claude_section("Monetization & guardrail insights",
                   lambda: narrative_agent.monetization_guardrails_insight(df),
                   "monetization")


# ===========================================================================
# 7 · EXECUTIVE MEMO
# ===========================================================================
elif page.startswith("7"):
    page_header("Executive Memo",
                "A planning-meeting-ready memo grounded in the current dataset, the "
                "latest scenario, and the initiative ranking. Download as Markdown "
                "and paste straight into a doc or slide.")

    cmp = st.session_state.get("last_comparison")
    scenario = st.session_state.get("last_scenario")
    if cmp is None:
        st.info("Tip: run a scenario on the **Scenario Planner** page first to include "
                "scenario assumptions in the memo. Otherwise the memo uses baseline + "
                "prioritization only.")
    else:
        active = {k: f"{v:+.0%}" for k, v in scenario.items() if v}
        scope_note = st.session_state.get("last_scope", "All households")
        st.markdown("**Scenario included:** " +
                    (", ".join(f"{k} {v}" for k, v in active.items())
                     if active else "baseline (no lifts)") +
                    f" · scope: **{scope_note}**")

    claude_section(
        "Executive memo",
        lambda: narrative_agent.executive_memo(
            df, cmp, scenario, ranked, gaps,
            st.session_state.get("last_scope")),
        "memo",
    )

    memo = st.session_state.get("claude_memo")
    if memo and memo.get("ok"):
        st.download_button("⬇️ Download memo (Markdown)", memo["text"],
                           file_name="executive_memo.md")
