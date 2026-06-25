"""
Plotly chart builders — one place for consistent, executive-clean styling.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#8B7CF8", "#2BD9A9", "#4DA8F7", "#FDCB6E", "#FF8A65", "#8CA3C0", "#C4B5FD"]

# Dark-blue native styling to match the app theme (.streamlit/config.toml)
LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#E6EDF7"),
    # Generous top margin with the title pinned to its own row above the
    # horizontal legend — keeps titles, legends, and outside bar labels from
    # colliding (the "bunched-up letters" fix).
    margin=dict(l=10, r=10, t=84, b=10),
    title_font_size=16,
    title_y=0.98, title_yanchor="top",
    legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
)
GRID = dict(gridcolor="#23364F", zerolinecolor="#23364F")


def _style(fig):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**GRID)
    fig.update_yaxes(**GRID)
    return fig


def monetization_per_hour_by_dim(summary: pd.DataFrame, dim: str, title: str):
    """Horizontal bar of monetization yield per streaming hour by a dimension."""
    d = summary.sort_values("monetization_per_streaming_hour")
    fig = px.bar(d, x="monetization_per_streaming_hour", y=dim, orientation="h",
                 title=title, color_discrete_sequence=[PALETTE[1]],
                 labels={"monetization_per_streaming_hour": "Revenue per streaming hour ($)",
                         dim: ""},
                 text=d["monetization_per_streaming_hour"].map(lambda v: f"${v:.3f}"))
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _style(fig)


def health_vs_depth(df: pd.DataFrame):
    """Scatter: experience health vs monetization depth — the guardrail map."""
    fig = px.scatter(
        df, x="monetization_depth_score", y="experience_health_score",
        size="households", color="engagement_segment",
        hover_data=["market", "device_type", "cohort_month"],
        category_orders={"engagement_segment": ["High", "Medium", "Low"]},
        color_discrete_sequence=[PALETTE[1], PALETTE[3], PALETTE[4]],
        title="Experience health vs monetization depth",
        labels={"monetization_depth_score": "Monetization depth (0–100)",
                "experience_health_score": "Experience health (0–100)",
                "engagement_segment": "Segment"},
    )
    # Quadrant guides: top-left = engaged but under-monetized (opportunity);
    # bottom-right = monetized but experience at risk (guardrail).
    fig.add_hline(y=50, line_dash="dot", line_color="#3C5578")
    fig.add_vline(x=50, line_dash="dot", line_color="#3C5578")
    fig.add_annotation(x=12, y=97, text="Engaged, under-monetized →", showarrow=False,
                       font=dict(size=11, color="#2BD9A9"))
    fig.add_annotation(x=88, y=3, text="← Monetized, experience risk", showarrow=False,
                       font=dict(size=11, color="#FF8A65"))
    return _style(fig)


def clv_vs_depth(df: pd.DataFrame):
    """Scatter: does deeper monetization line up with higher CLV?"""
    fig = px.scatter(
        df, x="monetization_depth_score", y="discounted_clv",
        size="households", color="experience_health_score",
        hover_data=["market", "device_type", "cohort_month"],
        color_continuous_scale=["#FF8A65", "#FDCB6E", "#2BD9A9"],
        title="CLV vs monetization depth (color = experience health)",
        labels={"monetization_depth_score": "Monetization depth (0–100)",
                "discounted_clv": "Discounted CLV ($/household)",
                "experience_health_score": "Experience health"},
    )
    return _style(fig)


def clv_by_dim(summary: pd.DataFrame, dim: str, title: str):
    """Horizontal bar of household-weighted average CLV by a dimension."""
    d = summary.sort_values("avg_clv")
    fig = px.bar(d, x="avg_clv", y=dim, orientation="h", title=title,
                 color_discrete_sequence=[PALETTE[0]],
                 labels={"avg_clv": "Avg discounted CLV ($/household)", dim: ""},
                 text=d["avg_clv"].map(lambda v: f"${v:,.0f}"))
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _style(fig)


def clv_by_cohort(summary: pd.DataFrame):
    """Line of average CLV across activation cohorts."""
    d = summary.sort_values("cohort_month")
    fig = px.line(d, x="cohort_month", y="avg_clv", markers=True,
                  title="Average CLV by activation cohort",
                  color_discrete_sequence=[PALETTE[2]],
                  labels={"avg_clv": "Avg discounted CLV ($)", "cohort_month": "Cohort"})
    return _style(fig)


def retention_by_segment(df: pd.DataFrame):
    """Retention curves (m1/3/6/12) by engagement segment, household-weighted."""
    rows = []
    for seg, g in df.groupby("engagement_segment"):
        w = g["households"]
        for label, col in [("Month 1", "month_1_retention"), ("Month 3", "month_3_retention"),
                           ("Month 6", "month_6_retention"), ("Month 12", "month_12_retention")]:
            rows.append({"segment": seg, "month": label,
                         "retention": (g[col] * w).sum() / w.sum()})
    d = pd.DataFrame(rows)
    order = {"Month 1": 1, "Month 3": 3, "Month 6": 6, "Month 12": 12}
    d["m"] = d["month"].map(order)
    d = d.sort_values("m")
    fig = px.line(d, x="month", y="retention", color="segment", markers=True,
                  title="Retention curve by engagement segment",
                  category_orders={"segment": ["High", "Medium", "Low"]},
                  color_discrete_sequence=[PALETTE[1], PALETTE[3], PALETTE[4]],
                  labels={"retention": "Retention", "month": ""})
    fig.update_yaxes(tickformat=".0%")
    return _style(fig)


def engagement_vs_clv(df: pd.DataFrame):
    """Scatter: engagement score vs CLV, sized by households."""
    fig = px.scatter(
        df, x="engagement_score", y="discounted_clv", size="households",
        color="engagement_segment", hover_data=["market", "device_type", "cohort_month"],
        category_orders={"engagement_segment": ["High", "Medium", "Low"]},
        color_discrete_sequence=[PALETTE[1], PALETTE[3], PALETTE[4]],
        title="Engagement vs CLV (bubble = households)",
        labels={"engagement_score": "Engagement score (percentile blend)",
                "discounted_clv": "Discounted CLV ($/household)",
                "engagement_segment": "Segment"},
    )
    return _style(fig)


def revenue_mix(kpis: dict):
    """Donut of ad vs subscription revenue contribution."""
    ad = kpis.get("ad_revenue_share", 0)
    fig = go.Figure(go.Pie(
        labels=["Ad revenue", "Subscription revenue"],
        values=[ad, 1 - ad], hole=0.55,
        marker=dict(colors=[PALETTE[0], PALETTE[1]]),
        textinfo="label+percent",
    ))
    fig.update_layout(title="Revenue mix per household", showlegend=False, **LAYOUT)
    return fig


def scenario_impact(comparison: dict):
    """Grouped bars: baseline vs scenario on the headline metrics."""
    base, scen = comparison["baseline"], comparison["scenario"]
    metrics = [
        ("Avg CLV ($)", base["avg_clv"], scen["avg_clv"]),
        ("Revenue / HH / mo ($)", base["avg_revenue_per_household"], scen["avg_revenue_per_household"]),
        ("Gross profit / HH / mo ($)", base["avg_gross_profit_per_household"], scen["avg_gross_profit_per_household"]),
        ("Retained months", base["avg_expected_retained_months"], scen["avg_expected_retained_months"]),
    ]
    labels = [m[0] for m in metrics]
    fig = go.Figure([
        go.Bar(name="Baseline", x=labels, y=[m[1] for m in metrics],
               marker_color=PALETTE[5], text=[f"{m[1]:,.2f}" for m in metrics], textposition="outside"),
        go.Bar(name="Scenario", x=labels, y=[m[2] for m in metrics],
               marker_color=PALETTE[0], text=[f"{m[2]:,.2f}" for m in metrics], textposition="outside"),
    ])
    fig.update_layout(barmode="group", title="Baseline vs scenario", **LAYOUT)
    return fig


def impact_complexity_matrix(ranked: pd.DataFrame):
    """Impact vs complexity bubble matrix for the initiative portfolio."""
    color_map = {"Quick win": PALETTE[1], "Strategic bet": PALETTE[0], "Enabler": PALETTE[3]}
    fig = px.scatter(
        ranked, x="complexity", y="incremental_value",
        size=ranked["score"].clip(lower=5), color="classification", text="initiative",
        color_discrete_map=color_map,
        title="Impact vs execution complexity",
        labels={"complexity": "Execution complexity (1 = easy, 5 = hard)",
                "incremental_value": "Modeled incremental value ($)",
                "classification": ""},
    )
    fig.update_traces(textposition="top center", textfont_size=11)
    fig.update_xaxes(range=[0.5, 5.5], dtick=1)
    return _style(fig)


def pipeline_diagram():
    """Simple visual of the multi-agent pipeline for the overview page."""
    stages = ["Data\nAgent", "Segmentation\nAgent", "CLV\nAgent",
              "Scenario\nAgent", "Prioritization\nAgent", "Claude Narrative\nAgent"]
    fig = go.Figure()
    for i, s in enumerate(stages):
        fig.add_shape(type="rect", x0=i, x1=i + 0.82, y0=0, y1=1,
                      line=dict(color=PALETTE[0]), fillcolor="rgba(139,124,248,0.12)")
        fig.add_annotation(x=i + 0.41, y=0.5, text=s.replace("\n", "<br>"),
                           showarrow=False, font=dict(size=12, color="#E6EDF7"))
        if i < len(stages) - 1:
            fig.add_annotation(x=i + 0.91, y=0.5, text="➜", showarrow=False,
                               font=dict(size=16, color=PALETTE[0]))
    fig.update_xaxes(visible=False, range=[-0.1, len(stages)])
    fig.update_yaxes(visible=False, range=[-0.2, 1.2])
    fig.update_layout(height=140, margin=dict(l=0, r=0, t=10, b=0),
                      template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig
