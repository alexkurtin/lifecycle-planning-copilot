"""
Initiative Prioritization Agent
===============================
Scores and ranks a portfolio of lifecycle initiatives.

Where initiatives come from
---------------------------
Initiatives are INPUTS, not facts. Each row is a planning hypothesis with
three kinds of input assumptions (all editable in the app):

  1. Driver lifts — which model levers the initiative moves, and by how much
     (e.g., Onboarding Optimization = +15% first-week engagement, +10% app
     installs). In a real cycle these come from experiment results, vendor
     benchmarks, or product-team sizing.
  2. Cost — estimated one-time investment, used for the ROI/payback proxy.
  3. Qualitative 1-5 scores — confidence, speed to impact, execution
     complexity, strategic fit, risk. These come from cross-functional
     sizing sessions.

Financial impact is MODELED, not hand-waved: each initiative's driver lifts
run through the Scenario Agent against the current dataset, producing its
incremental discounted lifecycle value, CLV lift, and ROI/payback.

Composite score (0-100):
  30% financial impact (normalized incremental value)
  15% CLV lift %
  15% ROI proxy (normalized)
  10% confidence
  10% speed to impact
  10% strategic fit
  -10% execution complexity (penalty)
  -10% risk (penalty)

Classification:
  Quick win       -> above-median impact, complexity <= 2.5
  Strategic bet   -> above-median impact, complexity > 2.5
  Enabler         -> below-median direct impact (value is indirect:
                     infrastructure, measurement, decision speed)
"""

import pandas as pd

from src.scenario_agent import apply_scenario, compare_scenario

# Driver-lift fields each initiative can move (same levers as the Scenario Planner)
LIFT_FIELDS = ["first_week_lift", "app_install_lift", "trc_usage_lift",
               "sub_conversion_lift", "retention_lift", "cpm_lift"]

QUAL_FIELDS = ["confidence", "speed", "complexity", "strategic_fit", "risk",
               "retention_risk"]  # retention_risk: 1 = experience-safe, 5 = likely to annoy users

# ---------------------------------------------------------------------------
# Preset initiative portfolio: a realistic starting point for a Consumer
# Planning & Optimization cycle. Every value below is a PLANNING ESTIMATE —
# edit them in the app (Initiative Prioritizer page) or replace with your own.
# ---------------------------------------------------------------------------
PRESET_INITIATIVES = [
    dict(initiative="Onboarding Optimization",
         first_week_lift=0.15, app_install_lift=0.10, trc_usage_lift=0.0,
         sub_conversion_lift=0.0, retention_lift=0.0, cpm_lift=0.0,
         cost=750_000, confidence=4, speed=4, complexity=2, strategic_fit=5,
         risk=2, retention_risk=1,
         thesis="Improve first-week setup and content discovery: strong experience "
                "and retention lift, indirect monetization lift."),
    dict(initiative="Home Screen Discovery Personalization",
         first_week_lift=0.08, app_install_lift=0.0, trc_usage_lift=0.10,
         sub_conversion_lift=0.0, retention_lift=0.02, cpm_lift=0.0,
         cost=1_500_000, confidence=3, speed=3, complexity=4, strategic_fit=5,
         risk=3, retention_risk=2,
         thesis="Personalized rows and recommendations: strong experience impact, "
                "medium/high monetization lift through engagement, low retention risk."),
    dict(initiative="Roku Channel-Style Engagement Push",
         first_week_lift=0.0, app_install_lift=0.0, trc_usage_lift=0.20,
         sub_conversion_lift=0.0, retention_lift=0.0, cpm_lift=0.0,
         cost=900_000, confidence=4, speed=4, complexity=2, strategic_fit=4,
         risk=2, retention_risk=2,
         thesis="Drive owned free-channel viewing: medium/high monetization lift "
                "(high-margin ad inventory) with positive engagement impact."),
    dict(initiative="Subscription Merchandising",
         first_week_lift=0.0, app_install_lift=0.0, trc_usage_lift=0.0,
         sub_conversion_lift=0.18, retention_lift=0.0, cpm_lift=0.0,
         cost=600_000, confidence=4, speed=5, complexity=2, strategic_fit=4,
         risk=2, retention_risk=3,
         thesis="Better placement, bundling, and offers: high monetization lift, "
                "medium experience risk if merchandising gets too aggressive."),
    dict(initiative="Ad Monetization Optimization",
         first_week_lift=0.0, app_install_lift=0.0, trc_usage_lift=0.0,
         sub_conversion_lift=0.0, retention_lift=0.0, cpm_lift=0.12,
         cost=800_000, confidence=4, speed=4, complexity=3, strategic_fit=4,
         risk=3, retention_risk=4,
         thesis="Better yield management, fill, and pricing: high monetization "
                "lift, but possible experience risk if it drifts into ad load."),
    dict(initiative="Win-back / Reactivation Campaign",
         first_week_lift=0.0, app_install_lift=0.0, trc_usage_lift=0.0,
         sub_conversion_lift=0.0, retention_lift=0.05, cpm_lift=0.0,
         cost=1_100_000, confidence=3, speed=3, complexity=3, strategic_fit=3,
         risk=3, retention_risk=2,
         thesis="Targeted campaigns to recover lapsing households: medium "
                "monetization lift, medium confidence."),
    dict(initiative="International Lifecycle Optimization",
         first_week_lift=0.10, app_install_lift=0.0, trc_usage_lift=0.0,
         sub_conversion_lift=0.0, retention_lift=0.03, cpm_lift=0.08,
         cost=2_000_000, confidence=2, speed=2, complexity=4, strategic_fit=4,
         risk=4, retention_risk=3,
         thesis="Localize onboarding and monetization in international markets "
                "where retention and CPMs lag the US."),
    dict(initiative="Reporting Infrastructure / BI Automation",
         first_week_lift=0.0, app_install_lift=0.0, trc_usage_lift=0.0,
         sub_conversion_lift=0.0, retention_lift=0.0, cpm_lift=0.0,
         cost=500_000, confidence=5, speed=3, complexity=3, strategic_fit=4,
         risk=1, retention_risk=1,
         thesis="Automate cohort/CLV reporting: an enabler — no direct revenue, "
                "but improves planning quality and decision speed."),
]

INPUT_COLUMNS = (["initiative"] + LIFT_FIELDS + ["cost"] + QUAL_FIELDS + ["thesis"])


def initiatives_table() -> pd.DataFrame:
    """The preset portfolio as a flat, editable table of INPUT assumptions."""
    return pd.DataFrame(PRESET_INITIATIVES)[INPUT_COLUMNS]


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize to 0-1; constant series -> 0.5."""
    lo, hi = series.min(), series.max()
    if hi - lo < 1e-12:
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


def score_initiatives(baseline_df: pd.DataFrame,
                      annual_discount_rate: float = 0.10,
                      initiatives_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Run each initiative's driver lifts through the CLV engine and build the
    ranked table. `initiatives_df` defaults to the preset portfolio; pass an
    edited table (from the in-app editor) to score custom initiatives.
    """
    if initiatives_df is None:
        initiatives_df = initiatives_table()

    rows = []
    for _, r in initiatives_df.iterrows():
        name = str(r.get("initiative") or "").strip()
        if not name:
            continue  # skip empty editor rows

        # Driver lifts -> scenario -> modeled financials. NaN-safe: blank
        # cells in editor-added rows arrive as NaN (and `NaN or 0` is NaN!).
        def _num(v, default=0.0):
            return float(v) if pd.notna(v) else default
        scenario = {f: _num(r.get(f)) for f in LIFT_FIELDS}
        cost = _num(r.get("cost"))
        scen_df = apply_scenario(baseline_df, scenario, annual_discount_rate)
        cmp = compare_scenario(baseline_df, scen_df, cost if cost > 0 else None)

        # --- Monetization & experience impacts (MODELED, not guessed) -------
        def _wmean(d, col):
            return float((d[col] * d["households"]).sum() / d["households"].sum())
        base_rev = _wmean(baseline_df, "total_monthly_revenue_per_household")
        scen_rev = _wmean(scen_df, "total_monthly_revenue_per_household")
        monetization_lift = scen_rev / base_rev - 1 if base_rev else 0.0

        # Experience impact: blended % change in the experience drivers the
        # scenario moved (retention 50%, steady-state hours 30%, first-week 20%)
        base_m6, scen_m6 = _wmean(baseline_df, "month_6_retention"), _wmean(scen_df, "month_6_retention")
        base_hrs, scen_hrs = _wmean(baseline_df, "monthly_streaming_hours"), _wmean(scen_df, "monthly_streaming_hours")
        base_fw, scen_fw = _wmean(baseline_df, "first_week_hours"), _wmean(scen_df, "first_week_hours")
        experience_impact = (
            0.5 * (scen_m6 / base_m6 - 1 if base_m6 else 0)
            + 0.3 * (scen_hrs / base_hrs - 1 if base_hrs else 0)
            + 0.2 * (scen_fw / base_fw - 1 if base_fw else 0)
        )

        thesis = r.get("thesis")
        rows.append({
            "initiative": name,
            "thesis": str(thesis) if pd.notna(thesis) else "",
            "incremental_value": cmp["incremental_value"],
            "clv_lift_pct": cmp["clv_lift_pct"],
            "monetization_lift": monetization_lift,
            "experience_impact": experience_impact,
            "roi": cmp["roi"] if cmp["roi"] is not None else 0.0,
            "payback_months": cmp["payback_months"],
            "cost": cost,
            # Qualitative planning scores (default 3 = neutral if blank)
            **{q: _num(r.get(q), 3.0) for q in QUAL_FIELDS},
        })

    t = pd.DataFrame(rows)
    if t.empty:
        return t

    # Composite score (see module docstring for weights)
    t["score"] = (
        0.30 * _normalize(t["incremental_value"])
        + 0.15 * _normalize(t["clv_lift_pct"])
        + 0.15 * _normalize(t["roi"])
        + 0.10 * (t["confidence"] / 5)
        + 0.10 * (t["speed"] / 5)
        + 0.10 * (t["strategic_fit"] / 5)
        - 0.10 * (t["complexity"] / 5)
        - 0.10 * (t["risk"] / 5)
    )
    # Rescale to 0-100 for readability
    t["score"] = (100 * _normalize(t["score"])).round(1)

    # --- Balanced score: monetization depth WITH experience guardrails ------
    # Not a pure revenue ranking: initiatives only rank high when monetization
    # lift comes with healthy experience impact and contained retention risk.
    #   25% monetization lift · 20% incremental value · 15% experience impact
    #   10% confidence · 10% strategic fit · 5% speed
    #   −10% complexity · −15% retention risk
    t["balanced_score"] = (
        0.25 * _normalize(t["monetization_lift"])
        + 0.20 * _normalize(t["incremental_value"])
        + 0.15 * _normalize(t["experience_impact"])
        + 0.10 * (t["confidence"] / 5)
        + 0.10 * (t["strategic_fit"] / 5)
        + 0.05 * (t["speed"] / 5)
        - 0.10 * (t["complexity"] / 5)
        - 0.15 * (t["retention_risk"] / 5)
    )
    t["balanced_score"] = (100 * _normalize(t["balanced_score"])).round(1)

    # Rank by the BALANCED view (the legacy `score` column is kept for
    # comparison — the gap between the two is itself a talking point).
    t = t.sort_values("balanced_score", ascending=False).reset_index(drop=True)
    t.insert(0, "rank", t.index + 1)

    # Classification
    # Classification: Enabler = no meaningful direct driver lift (value is
    # indirect); otherwise complexity splits quick wins from strategic bets.
    def classify(row):
        if row["monetization_lift"] < 0.005 and row["experience_impact"] < 0.005:
            return "Enabler"
        return "Quick win" if row["complexity"] <= 2.5 else "Strategic bet"
    t["classification"] = t.apply(classify, axis=1)

    return t
