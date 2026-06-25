"""
Shared constants and helpers for the Lifecycle Planning Copilot.

All data in this project is SYNTHETIC. No real company data is used.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Dataset schema
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "cohort_month",
    "market",
    "region",
    "device_type",
    "households",
    "activation_rate",
    "first_week_hours",
    "first_week_app_installs",
    "trc_usage_rate",
    "subscription_conversion_rate",
    "monthly_streaming_hours",
    "ad_supported_share",
    "ad_impressions_per_hour",
    "cpm",
    "fill_rate",
    "subscription_arpu",
    "gross_margin",
    "month_1_retention",
    "month_3_retention",
    "month_6_retention",
    "month_12_retention",
    "support_cost_per_household",
]

MARKETS = {
    "United States": "North America",
    "Canada": "North America",
    "Mexico": "Latin America",
    "Brazil": "Latin America",
    "United Kingdom": "Europe",
    "Germany": "Europe",
}

DEVICE_TYPES = ["Smart TV OS", "Streaming Stick", "Streaming Box", "Partner TV"]

# CLV model horizon (months) used for retention-curve integration & discounting
CLV_HORIZON_MONTHS = 24

# Columns that must be in [0, 1]
RATE_COLUMNS = [
    "activation_rate",
    "trc_usage_rate",
    "subscription_conversion_rate",
    "ad_supported_share",
    "fill_rate",
    "gross_margin",
    "month_1_retention",
    "month_3_retention",
    "month_6_retention",
    "month_12_retention",
]


# ---------------------------------------------------------------------------
# Formatting helpers (used across the UI)
# ---------------------------------------------------------------------------

def fmt_currency(x, decimals=2):
    """Format a number as USD, e.g. $12.34 or $1.2M."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.1f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    if abs(x) >= 1e4:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.{decimals}f}"


def fmt_pct(x, decimals=1):
    """Format a 0-1 rate as a percentage string."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x * 100:,.{decimals}f}%"


def fmt_num(x, decimals=0):
    """Format a number with thousands separators."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:,.{decimals}f}"


def weighted_mean(series, weights):
    """Household-weighted mean, safe against zero total weight."""
    total = weights.sum()
    if total == 0:
        return float("nan")
    return float((series * weights).sum() / total)
