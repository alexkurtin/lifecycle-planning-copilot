"""
Scenario Planning Agent
=======================
Applies user-defined "what-if" lifts to the cohort drivers, re-runs the CLV
model, and compares scenario vs. baseline.

How lifts flow through the model (all multiplicative, all documented):

  first_week_lift      -> first_week_hours up by X%; retention curve up by
                          0.25 × X% (engagement→retention elasticity)
  app_install_lift     -> first_week_app_installs up by X%; retention up by
                          0.15 × X%
  trc_usage_lift       -> trc_usage_rate up by X%; monthly streaming hours up
                          by 0.40 × X% (more owned content watched); retention
                          up by 0.20 × X%
  sub_conversion_lift  -> subscription_conversion_rate up by X%
  retention_lift       -> all four retention points up by X% directly
  cpm_lift             -> cpm up by X%
  gross_margin_change  -> gross_margin shifted by X percentage points
  experience_risk_penalty -> guardrail lever with TWO effects:
                          (1) retention dragged DOWN by
                              penalty × (cpm_lift + sub_conversion_lift)
                          (2) streaming hours dragged DOWN by
                              risk_to_hours (0.5) × penalty × cpm_lift —
                              ad-load suppresses viewing itself, and because
                              ad revenue is hours-driven, an aggressive push
                              partially cannibalizes its own inventory (a
                              deliberate, self-limiting feedback loop).
                          0 = assume no harm; 0.5 = half of every
                          monetization push point costs a retention point.

The elasticities are deliberately simple, visible constants — the point is a
transparent planning model, not a black box. In a real engagement they would
be calibrated from historical experiments.
"""

import numpy as np
import pandas as pd

from src.clv_agent import run_clv_model, portfolio_kpis

# Engagement -> retention elasticities (visible, adjustable in code)
ELASTICITY = {
    "first_week_to_retention": 0.25,
    "app_install_to_retention": 0.15,
    "trc_to_retention": 0.20,
    "trc_to_hours": 0.40,
    # Share of the experience-risk penalty that also suppresses streaming
    # hours when the push is ad-load-driven (cpm_lift). Hours feed ad
    # revenue, so this makes aggressive ad pushes self-limiting.
    "risk_to_hours": 0.50,
}

RETENTION_COLS = ["month_1_retention", "month_3_retention",
                  "month_6_retention", "month_12_retention"]

DEFAULT_SCENARIO = {
    "first_week_lift": 0.0,
    "app_install_lift": 0.0,
    "trc_usage_lift": 0.0,
    "sub_conversion_lift": 0.0,
    "retention_lift": 0.0,
    "cpm_lift": 0.0,
    "gross_margin_change": 0.0,   # percentage points, e.g. 0.02 = +2 pts
    "experience_risk_penalty": 0.0,  # guardrail: retention drag per unit of monetization push
}


def apply_scenario(df: pd.DataFrame, scenario: dict,
                   annual_discount_rate: float = 0.10) -> pd.DataFrame:
    """Apply lifts to drivers and re-run the CLV model."""
    s = {**DEFAULT_SCENARIO, **scenario}
    out = df.copy()

    # Direct driver lifts
    out["first_week_hours"] *= (1 + s["first_week_lift"])
    out["first_week_app_installs"] *= (1 + s["app_install_lift"])
    out["trc_usage_rate"] = (out["trc_usage_rate"] * (1 + s["trc_usage_lift"])).clip(0, 1)
    out["monthly_streaming_hours"] *= (1 + ELASTICITY["trc_to_hours"] * s["trc_usage_lift"])
    out["subscription_conversion_rate"] = (
        out["subscription_conversion_rate"] * (1 + s["sub_conversion_lift"])
    ).clip(0, 1)
    out["cpm"] *= (1 + s["cpm_lift"])
    out["gross_margin"] = (out["gross_margin"] + s["gross_margin_change"]).clip(0, 0.95)

    # Experience-risk guardrail, effect 1: ad-load pushes suppress viewing
    # itself. Hours fall by risk_to_hours × penalty × cpm_lift — and because
    # ad revenue is hours-driven, the push partially cannibalizes its own
    # inventory (self-limiting by design).
    hours_drag = (ELASTICITY["risk_to_hours"] * s["experience_risk_penalty"]
                  * s["cpm_lift"])
    out["monthly_streaming_hours"] *= max(0.0, 1 - hours_drag)

    # Retention: direct lift + engagement-driven elasticity flow-through,
    # minus the experience-risk guardrail effect 2 (aggressive monetization
    # pushes degrade the viewing experience and drag retention).
    risk_drag = s["experience_risk_penalty"] * (s["cpm_lift"] + s["sub_conversion_lift"])
    retention_multiplier = (
        (1 + s["retention_lift"])
        * (1 + ELASTICITY["first_week_to_retention"] * s["first_week_lift"])
        * (1 + ELASTICITY["app_install_to_retention"] * s["app_install_lift"])
        * (1 + ELASTICITY["trc_to_retention"] * s["trc_usage_lift"])
        * (1 - risk_drag)
    )
    for col in RETENTION_COLS:
        out[col] = (out[col] * retention_multiplier).clip(0, 0.98)

    return run_clv_model(out, annual_discount_rate)


def compare_scenario(baseline_df, scenario_df, initiative_cost=None):
    base = portfolio_kpis(baseline_df)
    scen = portfolio_kpis(scenario_df)
    incremental_value = scen["total_lifecycle_value"] - base["total_lifecycle_value"]
    roi, payback_months = None, None
    if initiative_cost and initiative_cost > 0:
        roi = incremental_value / initiative_cost
        from src.utils import CLV_HORIZON_MONTHS
        inc_monthly_value = incremental_value / CLV_HORIZON_MONTHS
        payback_months = (initiative_cost / inc_monthly_value
                          if inc_monthly_value > 0 else float("inf"))
    return {
        "baseline": base, "scenario": scen,
        "incremental_value": incremental_value,
        "incremental_clv_per_household": scen["avg_clv"] - base["avg_clv"],
        "clv_lift_pct": (scen["avg_clv"] / base["avg_clv"] - 1) if base["avg_clv"] else 0,
        "roi": roi, "payback_months": payback_months,
        "initiative_cost": initiative_cost,
    }
