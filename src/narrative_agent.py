"""
Executive Narrative Agent
=========================
Builds grounded context summaries from model outputs and asks the Claude
Agent for business-oriented narratives. Each function returns the
{"ok", "text", "error"} dict from claude_agent.ask_claude.

Grounding pattern: summarize first, then ask. We never pass raw cohort rows —
only small aggregated tables and KPI dicts. Every task carries an explicit
word budget so outputs stay executive-grade.
"""

import pandas as pd

from src.claude_agent import ask_claude
from src.clv_agent import portfolio_kpis
from src.segmentation_agent import segment_summary


def _round_records(df: pd.DataFrame, n: int = 12) -> list:
    """Compact a summary table into rounded records for the prompt."""
    return df.head(n).round(3).to_dict(orient="records")


def _base_context(df: pd.DataFrame) -> dict:
    """Shared grounding context: KPIs + segment/market/device summaries."""
    return {
        "portfolio_kpis": {k: round(v, 3) for k, v in portfolio_kpis(df).items()},
        "by_engagement_segment": _round_records(segment_summary(df, "engagement_segment")),
        "by_market": _round_records(segment_summary(df, "market")),
        "by_device_type": _round_records(segment_summary(df, "device_type")),
    }


def overview_insight(df: pd.DataFrame, gap_insights: dict | None = None) -> dict:
    ctx = _base_context(df)
    if gap_insights:
        ctx["gap_insights_non_obvious"] = gap_insights
    return ask_claude(
        "Portfolio overview for a VP who already knows this business cold. "
        "MAX 80 WORDS, prose. Do NOT restate familiar levels (which market is "
        "biggest, that ads dominate revenue, that engaged users are worth "
        "more) — leadership knows. Lead with the most actionable NON-OBVIOUS "
        "finding from gap_insights_non_obvious, with a figure. Then the one "
        "opportunity you would chase first and what it is worth.",
        ctx,
    )


def cohort_insights(df: pd.DataFrame, filters: dict) -> dict:
    ctx = _base_context(df)
    ctx["active_filters"] = filters
    ctx["by_cohort_month"] = _round_records(segment_summary(df, "cohort_month"), 12)
    return ask_claude(
        "Exactly 3 bullets, each UNDER 20 words, each with a figure: which cohorts/"
        "segments over- or under-perform on retention and CLV in this filtered view. "
        "Then one final line starting 'Worth investigating:' with a testable hypothesis.",
        ctx,
    )


def clv_driver_explanation(df: pd.DataFrame) -> dict:
    ctx = _base_context(df)
    k = portfolio_kpis(df)
    ctx["revenue_mix"] = {
        "ad_revenue_share": round(k.get("ad_revenue_share", 0), 3),
        "subscription_revenue_share": round(1 - k.get("ad_revenue_share", 0), 3),
    }
    return ask_claude(
        "For a finance audience, MAX 90 WORDS: rank the 3 biggest CLV drivers in this "
        "portfolio (revenue mix, retention/retained months, engagement spread across "
        "segments/markets), with one figure each. End with one bullet: the single "
        "highest-leverage driver to improve and why.",
        ctx,
    )


def scenario_interpretation(comparison: dict, scenario_params: dict,
                            guardrails: dict | None = None,
                            scope: str | None = None) -> dict:
    ctx = {
        "scenario_scope": scope or "All households",
        "scenario_levers": scenario_params,
        "baseline_kpis": {k: round(v, 3) for k, v in comparison["baseline"].items()},
        "scenario_kpis": {k: round(v, 3) for k, v in comparison["scenario"].items()},
        "incremental_value": round(comparison["incremental_value"], 0),
        "clv_lift_pct": round(comparison["clv_lift_pct"], 4),
        "roi": comparison["roi"],
        "payback_months": comparison["payback_months"],
        "initiative_cost": comparison["initiative_cost"],
    }
    if guardrails:
        ctx["monetization_and_experience_guardrails"] = guardrails
    return ask_claude(
        "Scenario read-out for a planning meeting. MAX 110 WORDS, prose. First "
        "sentence = verdict (e.g., 'Worth funding', 'Marginal — test first', 'Does "
        "not clear the bar') with the headline figure. If scenario_scope is not "
        "all households, name the scope. Then: what was assumed, what "
        "it does to CLV and monetization depth, and — explicitly — whether the "
        "experience guardrail holds (retention delta). If monetization rises while "
        "retention falls, say plainly that revenue may be borrowing from lifetime "
        "value. End with the single biggest sensitivity in the assumptions.",
        ctx,
    )


def monetization_guardrails_insight(df: pd.DataFrame) -> dict:
    """Narrative for the Monetization Depth & Experience Guardrails page."""
    from src.monetization_agent import guardrail_segments, portfolio_monetization_kpis
    g = guardrail_segments(df)
    ctx = {
        "portfolio_monetization_kpis": {
            k: (round(v, 3) if isinstance(v, float) else v)
            for k, v in portfolio_monetization_kpis(df).items()},
        "engaged_under_monetized_segments": _round_records(g["under_monetized"], 5),
        "monetized_experience_risk_segments": _round_records(g["experience_risk"], 5),
        "best_balanced_segments": _round_records(g["best_balanced"], 5),
    }
    return ask_claude(
        "Monetization guardrail read-out for a VP. MAX 110 WORDS. Exactly 3 bullets "
        "with figures: (1) the most attractive engaged-but-under-monetized segment "
        "and which lever fits it, (2) the segment where monetization may be "
        "outrunning experience health and what to watch, (3) the healthiest "
        "balanced segment whose playbook to replicate. End with one line starting "
        "'Guardrail:' stating whether the portfolio's monetization depth looks "
        "sustainable given experience health.",
        ctx,
    )


def prioritization_rationale(ranked: pd.DataFrame) -> dict:
    ctx = {"ranked_initiatives": _round_records(
        ranked[["rank", "initiative", "classification", "balanced_score",
                "monetization_lift", "experience_impact", "retention_risk",
                "incremental_value", "clv_lift_pct", "roi", "payback_months",
                "confidence", "complexity", "score"]], 12)}
    return ask_claude(
        "Prioritization rationale, MAX 120 WORDS. The ranking uses a BALANCED "
        "score: monetization lift counts only when experience impact is healthy "
        "and retention risk is contained — never recommend the highest-revenue "
        "initiative if it carries high retention risk. First sentence = what to "
        "fund first and why it wins on BALANCE (cite monetization lift AND "
        "experience impact). Then: one high-monetization initiative that ranks "
        "lower because of experience/retention risk, and what would de-risk it. "
        "End with exactly 2 bullets: 'Now:' (quick wins) and 'Next:' (strategic "
        "bets to stage-gate).",
        ctx,
    )


def executive_memo(df: pd.DataFrame, comparison: dict | None,
                   scenario_params: dict | None, ranked: pd.DataFrame,
                   gap_insights: dict | None = None,
                   scope: str | None = None) -> dict:
    ctx = _base_context(df)
    if gap_insights:
        ctx["gap_insights_non_obvious"] = gap_insights
    cols = ["rank", "initiative", "classification", "incremental_value",
            "roi", "payback_months", "score"]
    for extra in ["balanced_score", "monetization_lift", "experience_impact",
                  "retention_risk"]:
        if extra in ranked.columns:
            cols.append(extra)
    ctx["top_initiatives"] = _round_records(ranked[cols], 8)
    if comparison:
        ctx["active_scenario"] = {
            "levers": scenario_params,
            "scope": scope or "All households",
            "incremental_value": round(comparison["incremental_value"], 0),
            "clv_lift_pct": round(comparison["clv_lift_pct"], 4),
            "roi": comparison["roi"],
            "payback_months": comparison["payback_months"],
        }
    return ask_claude(
        "Write an executive memo for a Consumer Planning & Optimization review, "
        "in Markdown with EXACTLY these sections:\n"
        "## Executive Summary — exactly 5 bullets, each under 20 words, each with a "
        "figure; at least one bullet must address monetization depth and one must "
        "address experience/retention guardrails\n"
        "## Recommendation — the single initiative to fund now (max 60 words). "
        "Do NOT simply pick the highest-revenue option: recommend the best BALANCE "
        "of monetization lift, CLV impact, confidence, execution feasibility, and "
        "consumer experience health — and say explicitly why it balances "
        "monetization and experience\n"
        "## Supporting Insights — 3 bullets, each with a figure, drawn from "
        "gap_insights_non_obvious (the under-monetized pocket, the cohort "
        "vintage trend, marginal retention economics). NEVER restate obvious "
        "levels the room already knows (largest market, ad-heavy mix, "
        "engaged-users-are-worth-more)\n"
        "## Risks & Assumptions — 3 bullets; be honest that elasticities are planning "
        "estimates and the data is synthetic\n"
        "## Next Test or Pilot — one concrete pilot with a success metric and "
        "timeframe (max 40 words)\n"
        "## Slide-Ready Recommendation — ONE sentence, max 25 words, written as a "
        "slide headline (assertion, not description).",
        ctx,
        temperature=0.4,
    )
