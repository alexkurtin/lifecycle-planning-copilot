"""
CLV Modeling Agent
==================
Transparent, driver-based CLV model. Every column added here maps to a
formula a finance partner can audit in Excel.

Formulas (per household, per month unless noted)
------------------------------------------------
ad_revenue_per_household =
    monthly_streaming_hours * ad_supported_share * ad_impressions_per_hour
    * fill_rate * cpm / 1000 * PLATFORM_AD_MONETIZATION_SHARE

subscription_revenue_per_household =
    subscription_conversion_rate * subscription_arpu * SUBSCRIPTION_REVENUE_SHARE

total_monthly_revenue_per_household =
    ad_revenue_per_household + subscription_revenue_per_household

gross_profit_per_household =
    total_monthly_revenue_per_household * gross_margin
    - support_cost_per_household

expected_retained_months =
    area under the monthly survival curve over a 24-month horizon.
    The survival curve is interpolated through the observed retention
    points (month 1, 3, 6, 12) and extrapolated from months 13-24 using
    the implied month-over-month decay between months 6 and 12.

baseline_clv = gross_profit_per_household * expected_retained_months

discounted_clv =
    sum over t = 1..24 of  gross_profit * survival(t) / (1 + r/12)^t,
    where r is a user-adjustable annual discount rate.
"""

import numpy as np
import pandas as pd

from src.utils import CLV_HORIZON_MONTHS

# ---------------------------------------------------------------------------
# Calibration constants — sanity-checked against public streaming-platform
# disclosures (e.g., Roku's reported ~38.7B quarterly streaming hours across
# 90M+ households, and last-reported platform ARPU of roughly $41-45/year):
#
# PLATFORM_AD_MONETIZATION_SHARE — the platform captures only a fraction of
#   the ad inventory value its households generate: most viewing happens in
#   third-party apps where the platform gets little or no inventory. ~10% is
#   a stylized blend of owned free-channel viewing plus inventory-share deals.
#
# SUBSCRIPTION_REVENUE_SHARE — platforms typically earn a revenue share on
#   subscriptions billed through the platform (~20%), not the full ARPU.
#
# Both are deliberately visible, single-line levers. With real data they
# would be replaced by actual monetization rates from the revenue team.
# ---------------------------------------------------------------------------
PLATFORM_AD_MONETIZATION_SHARE = 0.10
SUBSCRIPTION_REVENUE_SHARE = 0.20

FORMULA_EXPLAINERS = [
    ("Ad revenue / household / month",
     "monthly streaming hours × ad-supported share × ad impressions per hour × fill rate × CPM ÷ 1,000 × 10% platform monetization share",
     "How much ad inventory a household generates — then the platform's slice of it. "
     "Most viewing happens in third-party apps where the platform gets little or no "
     "inventory, so only ~10% of the inventory value is captured (calibrated to "
     "public platform-ARPU disclosures)."),
    ("Subscription revenue / household / month",
     "subscription conversion rate × subscription ARPU × 20% revenue share",
     "Expected subscription revenue across all households in the cohort. The platform "
     "earns a billing revenue share (~20%), not the subscriber's full ARPU."),
    ("Total monthly revenue / household",
     "ad revenue + subscription revenue",
     "The two monetization engines combined."),
    ("Gross profit / household / month",
     "total monthly revenue × gross margin − support cost per household",
     "What's left after content/revenue-share costs and the cost to serve."),
    ("Expected retained months",
     "area under the retention (survival) curve over 24 months",
     "Interpolated through observed month 1/3/6/12 retention; months 13–24 extrapolated at the months 6→12 decay rate."),
    ("Baseline CLV",
     "gross profit per household × expected retained months",
     "Undiscounted lifetime gross profit — simple and great for quick comparisons."),
    ("Discounted CLV",
     "Σ gross profit × survival(t) ÷ (1 + r/12)^t, t = 1…24",
     "Time-value-adjusted CLV. The discount rate r is adjustable in the sidebar."),
    ("Net CLV (after acquisition cost)",
     "discounted CLV − acquisition cost per household",
     "Gross CLV values a household once acquired; net CLV subtracts what it "
     "cost to acquire it — device subsidy plus acquisition marketing (the "
     "classic CLV-vs-CAC lens; CAC is a sidebar assumption). For a "
     "platform that sells hardware near cost, the device subsidy IS the "
     "acquisition cost, so this distinction matters."),
]


def _survival_curve(m1, m3, m6, m12, horizon=CLV_HORIZON_MONTHS):
    """
    Build a monthly survival vector for months 1..horizon from the four
    observed retention points, vectorized over cohort rows.

    Inputs are arrays of shape (n_rows,). Output shape: (n_rows, horizon).
    Months 1-12: log-linear interpolation through (1,m1),(3,m3),(6,m6),(12,m12).
    Months 13-24: extrapolated using the implied monthly decay between
    months 6 and 12: decay = (m12/m6)^(1/6).
    """
    m1 = np.clip(np.asarray(m1, dtype=float), 1e-4, 1.0)
    m3 = np.clip(np.asarray(m3, dtype=float), 1e-4, 1.0)
    m6 = np.clip(np.asarray(m6, dtype=float), 1e-4, 1.0)
    m12 = np.clip(np.asarray(m12, dtype=float), 1e-4, 1.0)

    known_t = np.array([1, 3, 6, 12])
    months = np.arange(1, horizon + 1)
    n = m1.shape[0]
    surv = np.empty((n, horizon))

    log_known = np.log(np.stack([m1, m3, m6, m12], axis=1))  # (n, 4)
    for i in range(n):
        # Interpolate in log space (exponential-ish decay between points)
        interp = np.interp(months[:12], known_t, log_known[i])
        surv[i, :12] = np.exp(interp)

    # Extrapolate months 13..horizon with implied month 6 -> 12 decay
    decay = (m12 / m6) ** (1 / 6)          # monthly decay factor
    decay = np.clip(decay, 0.5, 1.0)
    for j, t in enumerate(range(13, horizon + 1)):
        surv[:, 12 + j] = m12 * decay ** (t - 12)

    return np.clip(surv, 0.0, 1.0)


def run_clv_model(df: pd.DataFrame, annual_discount_rate: float = 0.10) -> pd.DataFrame:
    """Append all CLV model columns to the cohort dataframe."""
    df = df.copy()

    # --- Revenue drivers ---------------------------------------------------
    # Ad revenue: hours watched -> ad-supported hours -> impressions -> filled
    # impressions -> dollars (CPM is per 1,000 impressions) -> the platform's
    # ~10% slice of that inventory value (see calibration constants above).
    df["ad_revenue_per_household"] = (
        df["monthly_streaming_hours"]
        * df["ad_supported_share"]
        * df["ad_impressions_per_hour"]
        * df["fill_rate"]
        * df["cpm"] / 1000.0
        * PLATFORM_AD_MONETIZATION_SHARE
    )

    # Subscription revenue: expected value across the cohort
    # (conversion x ARPU x the platform's ~20% billing revenue share).
    df["subscription_revenue_per_household"] = (
        df["subscription_conversion_rate"] * df["subscription_arpu"]
        * SUBSCRIPTION_REVENUE_SHARE
    )

    df["total_monthly_revenue_per_household"] = (
        df["ad_revenue_per_household"] + df["subscription_revenue_per_household"]
    )

    # --- Profitability -----------------------------------------------------
    df["gross_profit_per_household"] = (
        df["total_monthly_revenue_per_household"] * df["gross_margin"]
        - df["support_cost_per_household"]
    )

    # --- Retention / lifetime ----------------------------------------------
    surv = _survival_curve(
        df["month_1_retention"], df["month_3_retention"],
        df["month_6_retention"], df["month_12_retention"],
    )
    df["expected_retained_months"] = surv.sum(axis=1)

    # --- CLV -----------------------------------------------------------------
    df["baseline_clv"] = df["gross_profit_per_household"] * df["expected_retained_months"]

    monthly_rate = annual_discount_rate / 12.0
    discount = 1.0 / (1.0 + monthly_rate) ** np.arange(1, CLV_HORIZON_MONTHS + 1)
    df["discounted_clv"] = (surv * discount).sum(axis=1) * df["gross_profit_per_household"]

    # Cohort-level totals (per-household value x cohort size)
    df["total_lifecycle_value"] = df["discounted_clv"] * df["households"]
    return df


def payback_month(df: pd.DataFrame, annual_discount_rate: float,
                  acquisition_cost: float) -> int | None:
    """
    First month in which the household-weighted cumulative DISCOUNTED gross
    profit per household covers the acquisition cost (device subsidy +
    acquisition marketing). Returns 0 if cost is 0, None if the cost is not
    recovered within the CLV horizon.
    """
    if acquisition_cost <= 0:
        return 0
    surv = _survival_curve(
        df["month_1_retention"], df["month_3_retention"],
        df["month_6_retention"], df["month_12_retention"],
    )
    w = df["households"].to_numpy(dtype=float)
    gp = df["gross_profit_per_household"].to_numpy(dtype=float)
    monthly_rate = annual_discount_rate / 12.0
    disc = 1.0 / (1.0 + monthly_rate) ** np.arange(1, CLV_HORIZON_MONTHS + 1)
    # Weighted-average discounted gross-profit stream per household per month
    stream = ((surv * disc) * gp[:, None] * w[:, None]).sum(axis=0) / w.sum()
    cum = stream.cumsum()
    if cum[-1] < acquisition_cost:
        return None
    return int(np.argmax(cum >= acquisition_cost)) + 1


def portfolio_kpis(df: pd.DataFrame) -> dict:
    """Household-weighted headline KPIs for the current (filtered) dataset."""
    w = df["households"]
    total_w = w.sum()
    if total_w == 0:
        return {}
    return {
        "total_households": int(total_w),
        "avg_clv": float((df["discounted_clv"] * w).sum() / total_w),
        "total_lifecycle_value": float(df["total_lifecycle_value"].sum()),
        "avg_month_6_retention": float((df["month_6_retention"] * w).sum() / total_w),
        "avg_revenue_per_household": float(
            (df["total_monthly_revenue_per_household"] * w).sum() / total_w
        ),
        "avg_gross_profit_per_household": float(
            (df["gross_profit_per_household"] * w).sum() / total_w
        ),
        "avg_expected_retained_months": float(
            (df["expected_retained_months"] * w).sum() / total_w
        ),
        "ad_revenue_share": float(
            (df["ad_revenue_per_household"] * w).sum()
            / max((df["total_monthly_revenue_per_household"] * w).sum(), 1e-9)
        ),
    }
