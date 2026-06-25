"""
Monetization Depth & Experience Guardrails Agent
================================================
Evaluates whether cohorts are monetized effectively across ads and
subscriptions WHILE protecting engagement, retention, and long-term CLV —
the central planning tension for an ad-first streaming platform.

All scores are transparent percentile-rank blends (0-100). Percentile ranks
keep the scores scale-free (uploaded CSVs with different units still work)
and avoid false precision — these are planning lenses, not measurements.

Score definitions
-----------------
monetization_depth_score (0-100): how deeply a cohort row is monetized.
    35% revenue_per_household        (the outcome that matters)
    25% monetization_per_streaming_hour (yield on attention)
    20% subscription_conversion_rate (depth beyond advertising)
    10% ad_supported_share           (monetizable inventory mix)
    10% fill_rate                    (how well inventory sells)

experience_health_score (0-100): is the consumer experience strong?
    25% month_6_retention            (medium-term health)
    20% month_12_retention           (long-term health)
    20% monthly_streaming_hours      (steady-state engagement)
    15% first_week_hours             (early habit formation)
    10% first_week_app_installs      (onboarding success)
    10% month_1_retention            (early churn risk, inverted proxy)

balanced_value_score (0-100): the "fund this cohort's playbook" lens.
    40% CLV percentile + 30% monetization depth + 30% experience health,
    minus a 15-point maximum retention-risk penalty (low month-6 retention).
    Cohorts only score high when monetization does NOT come at the expense
    of experience.
"""

import pandas as pd

from src.utils import weighted_mean


def _pct(series: pd.Series) -> pd.Series:
    """Percentile rank 0-100 (scale-free, upload-friendly)."""
    return 100 * series.rank(pct=True)


def add_monetization_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append monetization-depth and experience-health metrics.
    Requires the CLV agent's revenue columns to already exist; every input
    below derives from existing schema columns, so CSV uploads stay
    compatible with no new required columns.
    """
    df = df.copy()

    # --- Plain ratio metrics (auditable one-liners) -------------------------
    df["revenue_per_household"] = df["total_monthly_revenue_per_household"]
    df["monetization_per_streaming_hour"] = (
        df["total_monthly_revenue_per_household"]
        / df["monthly_streaming_hours"].clip(lower=1e-9)
    )
    df["ad_revenue_share"] = (
        df["ad_revenue_per_household"]
        / df["total_monthly_revenue_per_household"].clip(lower=1e-9)
    )
    df["subscription_revenue_share"] = 1.0 - df["ad_revenue_share"]

    # --- Monetization depth score (weights in module docstring) -------------
    df["monetization_depth_score"] = (
        0.35 * _pct(df["revenue_per_household"])
        + 0.25 * _pct(df["monetization_per_streaming_hour"])
        + 0.20 * _pct(df["subscription_conversion_rate"])
        + 0.10 * _pct(df["ad_supported_share"])
        + 0.10 * _pct(df["fill_rate"])
    ).round(1)

    # --- Experience health score (weights in module docstring) --------------
    df["experience_health_score"] = (
        0.25 * _pct(df["month_6_retention"])
        + 0.20 * _pct(df["month_12_retention"])
        + 0.20 * _pct(df["monthly_streaming_hours"])
        + 0.15 * _pct(df["first_week_hours"])
        + 0.10 * _pct(df["first_week_app_installs"])
        + 0.10 * _pct(df["month_1_retention"])
    ).round(1)

    # --- Balanced value score ------------------------------------------------
    # Retention risk penalty: cohorts in the bottom of the month-6 retention
    # distribution lose up to 15 points — monetization that erodes retention
    # should not look attractive.
    retention_risk = (100 - _pct(df["month_6_retention"])) / 100  # 0..1
    df["balanced_value_score"] = (
        0.40 * _pct(df["discounted_clv"])
        + 0.30 * df["monetization_depth_score"]
        + 0.30 * df["experience_health_score"]
        - 15.0 * retention_risk
    ).clip(0, 100).round(1)

    return df


def monetization_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Household-weighted monetization & experience summary by a dimension."""
    groups = []
    for key, g in df.groupby(by):
        w = g["households"]
        groups.append({
            by: key,
            "households": int(w.sum()),
            "revenue_per_household": weighted_mean(g["revenue_per_household"], w),
            "monetization_per_streaming_hour": weighted_mean(
                g["monetization_per_streaming_hour"], w),
            "monetization_depth_score": weighted_mean(g["monetization_depth_score"], w),
            "experience_health_score": weighted_mean(g["experience_health_score"], w),
            "balanced_value_score": weighted_mean(g["balanced_value_score"], w),
            "avg_clv": weighted_mean(g["discounted_clv"], w),
            "avg_month_6_retention": weighted_mean(g["month_6_retention"], w),
        })
    return (pd.DataFrame(groups)
            .sort_values("balanced_value_score", ascending=False)
            .reset_index(drop=True))


def guardrail_segments(df: pd.DataFrame) -> dict:
    """
    The three planning lists, at market x device granularity:
      under_monetized -> engaged households the platform isn't fully
                         monetizing (experience health exceeds monetization
                         depth by > 5 points; top 5 by gap)
      experience_risk -> monetizing well but experience lags (depth exceeds
                         experience health by > 5 points; top 5 by gap)
      best_balanced   -> healthiest monetization opportunities (top
                         balanced-value scores)
    """
    seg = df.copy()
    seg["segment"] = seg["market"] + " · " + seg["device_type"]
    s = monetization_summary(seg, "segment")

    # Gap-based selection: rank segments by the spread between the two scores.
    # (More robust than strict tercile intersections, which can come up empty
    # when engagement and monetization are tightly correlated.)
    gap = s["experience_health_score"] - s["monetization_depth_score"]
    under_monetized = (
        s[gap > 5].assign(opportunity_gap=gap[gap > 5].round(1))
        .sort_values("opportunity_gap", ascending=False).head(5)
    )
    experience_risk = (
        s[gap < -5].assign(risk_gap=(-gap[gap < -5]).round(1))
        .sort_values("risk_gap", ascending=False).head(5)
    )
    best_balanced = s.head(5)

    return {
        "summary": s,
        "under_monetized": under_monetized.reset_index(drop=True),
        "experience_risk": experience_risk.reset_index(drop=True),
        "best_balanced": best_balanced.reset_index(drop=True),
    }


def portfolio_monetization_kpis(df: pd.DataFrame) -> dict:
    """Headline monetization & experience KPIs for the current dataset."""
    w = df["households"]
    g = guardrail_segments(df)
    return {
        "avg_revenue_per_household": weighted_mean(df["revenue_per_household"], w),
        "avg_monetization_per_hour": weighted_mean(
            df["monetization_per_streaming_hour"], w),
        "avg_monetization_depth": weighted_mean(df["monetization_depth_score"], w),
        "avg_experience_health": weighted_mean(df["experience_health_score"], w),
        "avg_balanced_value": weighted_mean(df["balanced_value_score"], w),
        "top_under_monetized": (g["under_monetized"]["segment"].iloc[0]
                                if len(g["under_monetized"]) else "None flagged"),
        "top_experience_risk": (g["experience_risk"]["segment"].iloc[0]
                                if len(g["experience_risk"]) else "None flagged"),
    }
