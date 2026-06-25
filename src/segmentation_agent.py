"""
Lifecycle Segmentation Agent
============================
Responsibilities:
  * Build a composite engagement score from first-week behavior,
    Roku-Channel-style (TRC) usage, and subscription conversion
  * Bucket cohort rows into High / Medium / Low engagement segments
  * Identify high-value vs. low-value segments
  * Produce segment-level retention, engagement, revenue, and CLV summaries

The segmentation operates at the cohort-row level (cohort x market x device),
which is how planning teams typically slice household data without
household-level PII.
"""

import pandas as pd

from src.utils import weighted_mean


ENGAGEMENT_COMPONENTS = [
    "first_week_hours",         # early habit formation
    "first_week_app_installs",  # content breadth / onboarding success
    "trc_usage_rate",           # free, owned-content engagement
    "monthly_streaming_hours",  # steady-state depth
]
DEFAULT_ENGAGEMENT_WEIGHTS = (1.0, 1.0, 1.0, 1.0)


def add_engagement_segments(df: pd.DataFrame,
                            weights: tuple | None = None) -> pd.DataFrame:
    """
    Score engagement and assign High/Medium/Low segments.

    Composite engagement score = WEIGHTED blend of percentile ranks of the
    four ENGAGEMENT_COMPONENTS. Weights default to equal but are a planning
    choice, not a fact — the app exposes them as sliders (Cohort Explorer)
    so the definition of "engaged" itself can be stress-tested.

    Percentile ranks keep the score scale-free, so uploaded datasets with
    different units still segment sensibly.
    """
    df = df.copy()
    w = list(weights) if weights is not None else list(DEFAULT_ENGAGEMENT_WEIGHTS)
    if len(w) != len(ENGAGEMENT_COMPONENTS) or sum(w) <= 0:
        w = list(DEFAULT_ENGAGEMENT_WEIGHTS)  # all-zero / malformed -> equal
    total = sum(w)
    df["engagement_score"] = (
        sum(wi * df[c].rank(pct=True)
            for wi, c in zip(w, ENGAGEMENT_COMPONENTS)) / total
    ).round(3)

    # Tercile cut: top third = High, middle = Medium, bottom = Low.
    # Extreme weights can create heavy ties; fall back to a rank-based cut.
    try:
        df["engagement_segment"] = pd.qcut(
            df["engagement_score"], q=3, labels=["Low", "Medium", "High"]
        ).astype(str)
    except ValueError:
        r = df["engagement_score"].rank(pct=True)
        df["engagement_segment"] = pd.cut(
            r, [0, 1 / 3, 2 / 3, 1.0], labels=["Low", "Medium", "High"],
            include_lowest=True).astype(str)
    return df


def segment_summary(df: pd.DataFrame, by: str = "engagement_segment") -> pd.DataFrame:
    """
    Household-weighted summary by any dimension (engagement segment, market,
    device type, region, cohort). Expects CLV columns to already exist
    (run the CLV agent first).
    """
    groups = []
    for key, g in df.groupby(by):
        w = g["households"]
        groups.append({
            by: key,
            "households": int(w.sum()),
            "avg_first_week_hours": weighted_mean(g["first_week_hours"], w),
            "avg_trc_usage_rate": weighted_mean(g["trc_usage_rate"], w),
            "avg_sub_conversion": weighted_mean(g["subscription_conversion_rate"], w),
            "avg_month_6_retention": weighted_mean(g["month_6_retention"], w),
            "avg_monthly_revenue": weighted_mean(g["total_monthly_revenue_per_household"], w),
            "avg_clv": weighted_mean(g["discounted_clv"], w),
            "total_lifecycle_value": float((g["discounted_clv"] * w).sum()),
        })
    out = pd.DataFrame(groups).sort_values("avg_clv", ascending=False)
    return out.reset_index(drop=True)


def value_segments(df: pd.DataFrame, top_n: int = 3):
    """Return (highest-value, lowest-value) segment summaries by avg CLV."""
    s = segment_summary(df, by="engagement_segment")
    by_market = segment_summary(df, by="market")
    return {
        "by_engagement": s,
        "top_markets": by_market.head(top_n),
        "bottom_markets": by_market.tail(top_n),
    }
