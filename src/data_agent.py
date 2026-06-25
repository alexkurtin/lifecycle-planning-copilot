"""
Data Agent
==========
Responsibilities:
  * Generate synthetic streaming household cohort data (clearly synthetic, internally consistent)
  * Load optional CSV uploads
  * Validate required columns and value ranges
  * Flag missing or unusual values for display in the UI

Business logic notes
--------------------
The synthetic generator builds a latent "engagement quality" factor per
cohort row. That factor drives first-week engagement, Roku-Channel-style
(TRC) usage, retention, and streaming hours TOGETHER, so the dataset shows
the real-world pattern this tool is designed to analyze: households that
engage early and adopt free-channel content retain better and are worth more.
"""

import os
import numpy as np
import pandas as pd

from src.utils import REQUIRED_COLUMNS, RATE_COLUMNS, MARKETS, DEVICE_TYPES

DATA_PATH = os.path.join("data", "synthetic_cohort_data.csv")

# Market-level monetization & lifecycle assumptions — synthetic, but scaled
# against public streaming-platform disclosures (streaming hours per household
# of ~140/month implied by ~38.7B quarterly hours across 90M+ households, and
# last-reported platform ARPU of roughly $41-45/year). Combined with the
# platform monetization-share constants in clv_agent.py, blended revenue per
# household lands near ~$4/month. US monetizes best; LatAm has lower CPMs.
MARKET_PROFILES = {
    # cpm, sub_arpu, sub_conv, base_retention, base_households, support_cost
    "United States":  dict(cpm=32.0, arpu=9.99, sub_conv=0.28, ret=0.78, hh=42000, cost=0.55),
    "Canada":         dict(cpm=24.0, arpu=8.99, sub_conv=0.24, ret=0.76, hh=9000,  cost=0.50),
    "Mexico":         dict(cpm=9.0,  arpu=4.99, sub_conv=0.14, ret=0.70, hh=14000, cost=0.25),
    "Brazil":         dict(cpm=7.5,  arpu=4.49, sub_conv=0.13, ret=0.68, hh=16000, cost=0.22),
    "United Kingdom": dict(cpm=21.0, arpu=8.49, sub_conv=0.22, ret=0.75, hh=11000, cost=0.48),
    "Germany":        dict(cpm=18.0, arpu=7.99, sub_conv=0.19, ret=0.73, hh=8000,  cost=0.45),
}

# Device-level engagement multipliers (Smart TV OS owners are the stickiest;
# partner TVs skew lower-engagement).
DEVICE_PROFILES = {
    "Smart TV OS":     dict(eng=1.12, hh_share=0.40),
    "Streaming Stick": dict(eng=1.00, hh_share=0.30),
    "Streaming Box":   dict(eng=1.06, hh_share=0.15),
    "Partner TV":      dict(eng=0.88, hh_share=0.15),
}


def generate_synthetic_data(seed: int = 42) -> pd.DataFrame:
    """Generate 12 monthly cohorts x 6 markets x 4 device types (288 rows)."""
    rng = np.random.default_rng(seed)
    cohort_months = pd.date_range("2025-01-01", periods=12, freq="MS").strftime("%Y-%m")

    rows = []
    for cohort in cohort_months:
        # Mild seasonality: Q4-adjacent cohorts (holiday device activations)
        # are larger but slightly lower-intent.
        month_num = int(cohort.split("-")[1])
        seasonal_size = 1.25 if month_num in (1, 11, 12) else 1.0
        seasonal_quality = 0.96 if month_num in (1, 12) else 1.0

        for market, profile in MARKET_PROFILES.items():
            for device, dev in DEVICE_PROFILES.items():
                # Latent engagement quality factor: drives engagement,
                # retention, and hours together for internal consistency.
                quality = float(
                    np.clip(rng.normal(1.0, 0.10), 0.75, 1.30)
                ) * dev["eng"] * seasonal_quality

                households = int(profile["hh"] * dev["hh_share"] * seasonal_size
                                 * rng.uniform(0.9, 1.1))

                # First week: ~3 hrs/day of early exploration for an average
                # household; steady state ~140 hrs/month (~4.6 hrs/day), in
                # line with public platform engagement disclosures.
                first_week_hours = round(np.clip(20.0 * quality * rng.uniform(0.9, 1.1), 4, 45), 1)
                first_week_app_installs = round(np.clip(5.5 * quality * rng.uniform(0.85, 1.15), 1, 14), 1)
                trc_usage_rate = round(np.clip(0.42 * quality * rng.uniform(0.9, 1.1), 0.05, 0.85), 3)
                monthly_streaming_hours = round(np.clip(140 * quality * rng.uniform(0.9, 1.1), 40, 280), 1)

                # Retention curve: base market retention scaled by engagement
                # quality, decaying over time. Higher quality -> flatter curve.
                m1 = np.clip(profile["ret"] * (0.92 + 0.10 * (quality - 1.0) * 2.5)
                             * rng.uniform(0.98, 1.02), 0.40, 0.95)
                decay = np.clip(0.965 + 0.02 * (quality - 1.0), 0.93, 0.985)
                m3 = m1 * decay ** 2
                m6 = m1 * decay ** 5
                m12 = m1 * decay ** 11

                sub_conv = np.clip(profile["sub_conv"] * (0.85 + 0.30 * (quality - 0.9))
                                   * rng.uniform(0.92, 1.08), 0.02, 0.45)

                rows.append({
                    "cohort_month": cohort,
                    "market": market,
                    "region": MARKETS[market],
                    "device_type": device,
                    "households": households,
                    "activation_rate": round(np.clip(0.86 * quality * rng.uniform(0.95, 1.05), 0.55, 0.98), 3),
                    "first_week_hours": first_week_hours,
                    "first_week_app_installs": first_week_app_installs,
                    "trc_usage_rate": trc_usage_rate,
                    "subscription_conversion_rate": round(float(sub_conv), 3),
                    "monthly_streaming_hours": monthly_streaming_hours,
                    "ad_supported_share": round(np.clip(rng.normal(0.62, 0.05), 0.40, 0.80), 3),
                    "ad_impressions_per_hour": round(rng.uniform(16, 26), 1),
                    "cpm": round(profile["cpm"] * rng.uniform(0.9, 1.1), 2),
                    "fill_rate": round(np.clip(rng.normal(0.80, 0.05), 0.55, 0.95), 3),
                    "subscription_arpu": round(profile["arpu"] * rng.uniform(0.95, 1.05), 2),
                    "gross_margin": round(np.clip(rng.normal(0.55, 0.04), 0.40, 0.68), 3),
                    "month_1_retention": round(float(m1), 3),
                    "month_3_retention": round(float(m3), 3),
                    "month_6_retention": round(float(m6), 3),
                    "month_12_retention": round(float(m12), 3),
                    "support_cost_per_household": round(profile["cost"] * rng.uniform(0.9, 1.1), 2),
                })

    return pd.DataFrame(rows)


def ensure_synthetic_data(path: str = DATA_PATH) -> pd.DataFrame:
    """Create the synthetic CSV if it does not exist, then return it."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        generate_synthetic_data().to_csv(path, index=False)
    return pd.read_csv(path)


def load_csv(uploaded_file) -> pd.DataFrame:
    """Load a user-uploaded CSV (Streamlit UploadedFile or path)."""
    return pd.read_csv(uploaded_file)


def validate_data(df: pd.DataFrame):
    """
    Validate a cohort dataset.

    Returns (clean_df, errors, warnings):
      * errors   -> blocking problems (missing required columns)
      * warnings -> data-quality flags shown in the UI (missing values,
                    out-of-range rates, retention curves that go up over time)
    """
    errors, warnings = [], []

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {', '.join(missing_cols)}")
        return df, errors, warnings

    df = df.copy()

    # Missing values
    na_counts = df[REQUIRED_COLUMNS].isna().sum()
    for col, n in na_counts[na_counts > 0].items():
        warnings.append(f"`{col}` has {n} missing value(s); affected rows were dropped.")
    df = df.dropna(subset=REQUIRED_COLUMNS)

    # Rates must be within [0, 1]
    for col in RATE_COLUMNS:
        bad = ((df[col] < 0) | (df[col] > 1)).sum()
        if bad:
            warnings.append(f"`{col}` has {bad} value(s) outside [0, 1]; clipped.")
            df[col] = df[col].clip(0, 1)

    # Non-negative numeric drivers
    for col in ["households", "monthly_streaming_hours", "cpm", "subscription_arpu",
                "support_cost_per_household", "ad_impressions_per_hour"]:
        bad = (df[col] < 0).sum()
        if bad:
            warnings.append(f"`{col}` has {bad} negative value(s); clipped to 0.")
            df[col] = df[col].clip(lower=0)

    # Retention should decline over time
    inverted = ((df["month_12_retention"] > df["month_1_retention"])).sum()
    if inverted:
        warnings.append(
            f"{inverted} row(s) have month-12 retention above month-1 retention — "
            "check the retention curve inputs."
        )

    if df.empty:
        errors.append("No valid rows remain after cleaning.")

    return df, errors, warnings