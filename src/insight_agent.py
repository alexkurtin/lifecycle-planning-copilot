"""
Insight Agent
=============
Finds the NON-OBVIOUS story in the current dataset: gaps, trends, and
marginal economics — not levels. Executives already know the levels ("the
US is the biggest market", "ads carry most of the revenue", "engaged users
are worth more"); these functions surface what they don't already know:

  1. under_monetized_opportunity — the engaged pocket monetizing furthest
     below the portfolio yield benchmark, with the $ value of closing half
     the gap. Same engagement, less money: a pricing/attach problem, not a
     demand problem.
  2. vintage_trend — are the newest cohorts arriving better or worse than
     the oldest, and which driver (retention vs monetization) explains it.
     Trend, not level: the early-warning signal a level view hides.
  3. marginal_retention_value — where the NEXT retention point pays most,
     computed by pushing a small uniform retention lift through the CLV
     engine market by market. Marginal economics, not averages.

All deterministic, household-weighted, computed from the same model columns
as every other page — so with uploaded real data these become real findings.
Fed into the Claude overview/memo prompts as grounding so the AI narrative
leads with gaps too (and the verifier can trace every figure).
"""

import pandas as pd

from src.scenario_agent import apply_scenario
from src.utils import weighted_mean


def under_monetized_opportunity(df: pd.DataFrame) -> dict | None:
    """
    Largest under-monetized engaged pocket (market × device).

    Candidates: experience health at/above the median, monetization per
    streaming hour below the portfolio average. Sized by the annualized
    revenue value of closing HALF the yield gap to the portfolio average
    (half, because closing it fully assumes away mix effects).
    """
    seg = df.copy()
    seg["segment"] = seg["market"] + " · " + seg["device_type"]
    rows = []
    for key, g in seg.groupby("segment"):
        w = g["households"]
        rows.append({
            "segment": key,
            "households": int(w.sum()),
            "mph": weighted_mean(g["monetization_per_streaming_hour"], w),
            "hours": weighted_mean(g["monthly_streaming_hours"], w),
            "health": weighted_mean(g["experience_health_score"], w),
        })
    t = pd.DataFrame(rows)
    port_mph = weighted_mean(df["monetization_per_streaming_hour"],
                             df["households"])
    cand = t[(t["health"] >= t["health"].median()) & (t["mph"] < port_mph)].copy()
    if cand.empty:
        return None
    cand["annual_gap_value"] = ((port_mph - cand["mph"]) * cand["hours"]
                                * cand["households"] * 12)
    best = cand.sort_values("annual_gap_value", ascending=False).iloc[0]
    return {
        "segment": best["segment"],
        "households": int(best["households"]),
        "segment_yield_per_hour": round(float(best["mph"]), 3),
        "portfolio_yield_per_hour": round(float(port_mph), 3),
        "yield_gap_pct": round(float(best["mph"] / port_mph - 1), 3),
        "experience_health": round(float(best["health"]), 1),
        "annual_value_of_closing_half_gap":
            round(float(best["annual_gap_value"]) * 0.5, 0),
    }


def vintage_trend(df: pd.DataFrame) -> dict | None:
    """
    Newest 3 cohorts vs oldest 3: is the business acquiring better or worse
    households over time, and is the move driven by retention or
    monetization? Requires at least 4 distinct cohort months.
    """
    months = sorted(df["cohort_month"].unique())
    if len(months) < 4:
        return None
    early = df[df["cohort_month"].isin(months[:3])]
    late = df[df["cohort_month"].isin(months[-3:])]

    def stats(d):
        w = d["households"]
        return {
            "clv": weighted_mean(d["discounted_clv"], w),
            "m6": weighted_mean(d["month_6_retention"], w),
            "rev": weighted_mean(d["total_monthly_revenue_per_household"], w),
        }

    e, l = stats(early), stats(late)
    if not e["clv"]:
        return None
    clv_delta = l["clv"] / e["clv"] - 1
    rev_delta_pct = l["rev"] / e["rev"] - 1 if e["rev"] else 0.0
    m6_rel_delta = l["m6"] / e["m6"] - 1 if e["m6"] else 0.0

    # Honest driver attribution: only credit a driver whose direction matches
    # the CLV move. If neither matches (e.g., CLV down while retention AND
    # revenue tick up), the real story is cohort mix shifting toward
    # lower-value markets/devices — say so rather than forcing a driver.
    same_sign = [(abs(m6_rel_delta), "retention")
                 for _ in [0] if (m6_rel_delta >= 0) == (clv_delta >= 0)]
    same_sign += [(abs(rev_delta_pct), "monetization")
                  for _ in [0] if (rev_delta_pct >= 0) == (clv_delta >= 0)]
    primary = (max(same_sign)[1] if same_sign
               else "cohort mix (market/device composition)")
    return {
        "oldest_cohorts": f"{months[0]} – {months[2]}",
        "newest_cohorts": f"{months[-3]} – {months[-1]}",
        "clv_delta_pct": round(clv_delta, 3),
        "month_6_retention_delta_pts": round((l["m6"] - e["m6"]) * 100, 1),
        "revenue_per_hh_delta_pct": round(rev_delta_pct, 3),
        "primary_driver": primary,
    }


def marginal_retention_value(df: pd.DataFrame,
                             annual_discount_rate: float = 0.10) -> dict | None:
    """
    Value of the NEXT retention point by market: push a uniform +5%
    retention lift through the CLV engine per market, express as discounted
    CLV gained per household per +1% retention lift. The spread across
    markets is where uniform retention budgets leave money on the table.
    """
    rows = []
    for mkt, g in df.groupby("market"):
        scen = apply_scenario(g, {"retention_lift": 0.05}, annual_discount_rate)
        w = g["households"]
        delta = (weighted_mean(scen["discounted_clv"], w)
                 - weighted_mean(g["discounted_clv"], w)) / 5.0
        rows.append({"market": mkt, "value_per_hh_per_pct": delta,
                     "households": int(w.sum()),
                     "total_per_pct": delta * float(w.sum())})
    t = pd.DataFrame(rows)
    if len(t) < 2:
        return None
    by_hh = t.sort_values("value_per_hh_per_pct", ascending=False)
    best, worst = by_hh.iloc[0], by_hh.iloc[-1]
    top_total = t.sort_values("total_per_pct", ascending=False).iloc[0]
    return {
        "best_market": best["market"],
        "best_value_per_hh_per_pct_lift": round(float(best["value_per_hh_per_pct"]), 2),
        "worst_market": worst["market"],
        "worst_value_per_hh_per_pct_lift": round(float(worst["value_per_hh_per_pct"]), 2),
        "spread_x": (round(float(best["value_per_hh_per_pct"]
                                 / worst["value_per_hh_per_pct"]), 1)
                     if worst["value_per_hh_per_pct"] else None),
        "largest_total_market": top_total["market"],
        "largest_total_per_pct_lift": round(float(top_total["total_per_pct"]), 0),
    }


def compute_gap_insights(df: pd.DataFrame,
                         annual_discount_rate: float = 0.10) -> dict:
    """All gap insights in one dict (None entries dropped)."""
    out = {
        "under_monetized_opportunity": under_monetized_opportunity(df),
        "vintage_trend": vintage_trend(df),
        "marginal_retention_value":
            marginal_retention_value(df, annual_discount_rate),
    }
    return {k: v for k, v in out.items() if v is not None}
