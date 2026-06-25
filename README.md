# 📺 Lifecycle Planning Copilot

A cohort-based **customer lifetime value (CLV) and scenario planning tool for streaming households**, built as a polished Streamlit app with a transparent, driver-based financial model and Claude-powered executive narratives.

> 🧪 **All data is synthetic.** No real company data, logos, or proprietary branding are used. The product is generic to streaming households, with fields *inspired by* streaming TV platform economics (including Roku-Channel-style usage).

---

## What it does

The tool helps a **Consumer Planning & Optimization** team answer:

- How do lifecycle behaviors (first-week engagement, free-channel usage, subscription conversion, retention) translate into **CLV, revenue, gross profit, and ROI**?
- Which cohorts, markets, devices, and engagement segments concentrate value?
- What happens to lifetime value if we lift onboarding, engagement, conversion, retention, or monetization — and what is the **ROI / payback** of paying for that lift?
- Which initiatives should we fund first — **quick wins, strategic bets, or enablers** — and in what sequence?
- How do we communicate all of this in an **executive-ready memo**?

The numerical model is fully transparent and auditable. Claude does **not** compute anything — it interprets and narrates the model's outputs under strict word budgets, grounded in summarized results, so every claim traces back to a formula you can inspect.

## Why this is relevant to Consumer Planning & Optimization

The app mirrors the core workflow of a planning & analysis role: lifecycle modeling, CLV analysis, consumer analytics, business performance reporting, scenario planning, business case analysis, initiative prioritization, and executive communication — with AI used the way a modern analyst should use it: to accelerate insight and storytelling, never to obscure the math.

## Multi-agent architecture

See `multi_agent_pipeline.svg` for the architecture diagram.

```
Data Agent → Segmentation Agent → CLV Agent → Scenario Agent → Prioritization Agent
                                      ↘ ─────────  Claude Narrative Agent  ───────── ↙
```

| Agent | File | Responsibility |
|---|---|---|
| **Data Agent** | `src/data_agent.py` | Generates synthetic cohort data (or loads an uploaded CSV), validates required columns, flags missing/unusual values, outputs a clean dataset with UI warnings |
| **Lifecycle Segmentation Agent** | `src/segmentation_agent.py` | Builds a composite engagement score; assigns High/Med/Low segments; produces segment-level retention, engagement, revenue, and CLV summaries |
| **CLV Modeling Agent** | `src/clv_agent.py` | Transparent driver-based CLV: ad revenue, subscription revenue, gross profit, expected retained months (retention-curve integration), discounted CLV |
| **Scenario Planning Agent** | `src/scenario_agent.py` | Applies what-if lifts with documented elasticities; recalculates CLV, revenue, gross profit, incremental value, ROI/payback proxy |
| **Initiative Prioritization Agent** | `src/prioritization_agent.py` | Initiatives are *editable inputs*: each row defines driver lifts, cost, and 1–5 planning scores (edit or add rows in-app); financial impact is modeled through the scenario engine; classifies quick wins, strategic bets, enablers |
| **Insight Agent** | `src/insight_agent.py` | Finds the *non-obvious* story — gaps, trends, marginal economics, never levels: the biggest under-monetized engaged pocket (with the $/yr value of closing half the yield gap), the cohort vintage trend (with honest driver attribution), and where the next retention point pays most (a +1% lift pushed through the CLV engine market by market). Feeds the Overview cards and grounds the Memo |
| **Claude Executive Narrative Agent** | `src/claude_agent.py` + `src/narrative_agent.py` | Centralized Claude API access; generates cohort insights, CLV driver interpretation, scenario read-outs, prioritization rationale, and a full executive memo — grounded only in summarized model outputs, under strict word budgets |
| **Narrative Verifier Agent** | `src/verifier_agent.py` | Deterministic grounding check: every figure in a Claude draft ($94, 12%, 3.2x…) is machine-verified against the model outputs that were in its prompt, within the figure's quoted precision; untraceable figures are flagged in the UI before anyone relies on them. The quality gate runs on the generated language, never on the math |

## How to run locally

```powershell
cd "lifecycle planning copilot"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The synthetic dataset (`data/synthetic_cohort_data.csv`) is generated automatically on first run if it does not exist. The app defaults to a dark-blue executive theme (`.streamlit/config.toml`).

## Adding your Claude API key

Two options:

1. **In the app:** paste your key into the sidebar field (held in memory for the session only, never written to disk).
2. **Via .env:** copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY=sk-ant-...`, restart.

If the key is missing or a call fails, the app shows a clear, actionable error instead of breaking. All Claude calls are centralized in `src/claude_agent.py`, receive only **summarized** model outputs (never raw data), and are session-cached.

## Synthetic data vs. CSV upload

- **Synthetic (default):** 12 monthly cohorts × 6 markets (US, Canada, Mexico, Brazil, UK, Germany) × 4 device types (Smart TV OS, Streaming Stick, Streaming Box, Partner TV) = 288 cohort rows. A latent "engagement quality" factor makes the data internally consistent: higher first-week engagement and Roku-Channel-style usage correlate with stronger retention and CLV. International markets carry different monetization and retention profiles.
- **Upload CSV:** choose *Upload CSV* in the sidebar. The Data Agent validates the required columns (listed in the sidebar expander), drops rows with missing values, clips out-of-range rates, and surfaces every issue as a data-quality warning.

## CLV formulas (transparent and auditable)

```
ad_revenue_per_household        = monthly_streaming_hours × ad_supported_share
                                  × ad_impressions_per_hour × fill_rate × cpm / 1000
                                  × platform_ad_monetization_share (10%)
subscription_revenue_per_hh     = subscription_conversion_rate × subscription_arpu
                                  × subscription_revenue_share (20%)
total_monthly_revenue_per_hh    = ad_revenue + subscription_revenue
gross_profit_per_household      = total_monthly_revenue × gross_margin − support_cost_per_household
expected_retained_months        = area under the survival curve over 24 months
                                  (log-interpolated through month 1/3/6/12 retention;
                                   months 13–24 extrapolated at the months 6→12 decay rate)
baseline_clv                    = gross_profit_per_household × expected_retained_months
discounted_clv                  = Σₜ gross_profit × survival(t) / (1 + r/12)ᵗ,  t = 1…24   (gross CLV)
net_clv                         = discounted_clv − acquisition_cost_per_household
                                  (device subsidy + acquisition marketing — the CLV-vs-CAC lens)
payback_month                   = first month where cumulative discounted gross profit ≥ CAC
```

The CLV Model page walks one average household through this chain with live numbers — the whole model in one line.

### Calibration to public benchmarks

The synthetic data is sanity-checked against public streaming-platform disclosures: ~140 streaming hours per household per month (implied by ~38.7B quarterly hours across 90M+ households) and blended platform revenue of roughly $4/household/month (consistent with last-reported platform ARPU of ~$41–45/year). Two visible constants in `src/clv_agent.py` make the economics realistic: the platform captures only ~10% of the ad inventory value its households generate (most viewing happens in third-party apps), and earns a ~20% revenue share on subscriptions rather than full ARPU. Retention curves cannot be benchmarked — platforms don't disclose them — so they remain stylized planning assumptions.

## Model assumptions (all visible in the app)

The sidebar's **Model assumptions** expander surfaces every assumption:

- **CLV horizon:** 24 months; **discount rate:** user-adjustable (default 10%/yr).
- **Acquisition cost:** user-adjustable (default $8/household ≈ a few dollars of
  device subsidy for hardware sold near cost, plus acquisition marketing).
  Drives net CLV, CLV:CAC, and payback on the CLV Model page; scenario pages
  model already-acquired households, so their incremental values are CAC-free.
- **Engagement score weights:** the composite engagement score is a *weighted*
  percentile blend (first-week hours, app installs, free-channel usage,
  steady-state hours) — weights are sliders on the Cohort Explorer, so "what
  counts as engaged" is itself a testable planning choice.
- **Engagement → retention elasticities** (documented at the top of `src/scenario_agent.py`): first-week ×0.25, app installs ×0.15, free-channel usage ×0.20 (plus ×0.40 flow-through to hours). These are planning estimates; with real data they would be calibrated from historical experiments.
- **Initiative scoring weights** (Prioritizer page methodology expander): 30% incremental value, 15% CLV lift, 15% ROI, 10% each confidence/speed/strategic fit, −10% each complexity/risk. Qualitative 1–5 scores represent cross-functional sizing estimates.
- **Classification rules:** above-median impact + low complexity = quick win; + high complexity = strategic bet; below-median direct impact = enabler.

## Monetization Depth & Experience Guardrails

The tool evaluates how to **deepen monetization across ads and subscriptions while protecting engagement, retention, and long-term customer value** — the central planning tension for an ad-first streaming platform.

- **New metrics** (`src/monetization_agent.py`): revenue per household, monetization per streaming hour, ad/subscription revenue shares, plus three transparent percentile-blend scores — *monetization depth* (how deeply a cohort is monetized), *experience health* (retention + engagement strength), and *balanced value* (CLV + depth + health, with a retention-risk penalty so monetization that erodes retention never looks attractive).
- **New page** (*Monetization Guardrails*): yield-per-hour by market and device, a guardrail quadrant map (experience health vs. monetization depth), and three planning tables — engaged-but-under-monetized segments, monetized-but-experience-risk segments, and the best balanced-value playbooks.
- **Scenario guardrails:** an *experience risk penalty* lever with **two modeled effects** — retention falls by penalty × (CPM + subscription lifts), and streaming hours fall by 0.5 × penalty × CPM lift. Because ad revenue is hours-driven, an aggressive ad push partially cannibalizes its own inventory: the trade-off is self-limiting by design. Every scenario gets a deterministic verdict — *Balanced ✓* or *Guardrail flag* — alongside monetization-per-hour, retention, and streaming-hour deltas.
- **Scenario scope:** scenarios run against a selectable population (market × device × engagement segment), so "onboarding push in Mexico" is a concrete, sized statement rather than a portfolio-wide generality. The scope follows the scenario into the Executive Memo.
- **Balanced prioritization:** initiatives are ranked by a balanced score (monetization lift + experience impact + retention risk, alongside value and feasibility), not pure revenue. The legacy revenue-weighted score is kept for comparison — the gap between the two rankings shows exactly where a revenue-only view would over-fund experience-risky work.

## Interview demo script

> "I built this Lifecycle Planning Copilot to mirror the type of planning and analysis work this role appears to own: lifecycle modeling, CLV analysis, consumer analytics, scenario planning, initiative prioritization, and executive communication. The data is synthetic, but the workflow is designed to show how I would structure a real planning analysis. The model is transparent and driver-based, while Claude helps accelerate insight generation and executive-ready storytelling."

**Suggested 5-minute walkthrough:**

1. **Executive Overview** (45s) — KPI cards plus the three computed takeaways: *"the model leads with the 'so what': engagement carries a CLV premium, retention explains it, and value is concentrated by market."*
2. **CLV Model** (60s) — the average-household walkthrough line: *"this is the whole model in one sentence — five drivers, each one a lever the team can act on. Every number is auditable."*
3. **Scenario Planner** (90s) — click the **Onboarding push** preset: *"presets mirror the initiative portfolio. A 15% first-week lift flows into retention through a documented elasticity — incremental value, ROI, and payback update instantly."* Draft the AI read-out: verdict first.
4. **Initiative Prioritizer** (60s) — methodology expander, then the Now/Next/Foundational sequence: *"the financial column is modeled through the same CLV engine, and the output is a planning sequence, not just a ranked list."*
5. **Executive Memo** (60s) — draft and download: *"from raw cohorts to a planning-meeting-ready memo with a slide headline, in minutes."*

**Questions to expect — and answers built into the tool:**

- *"How would you validate the elasticities?"* — They're visible planning estimates; with real data I'd calibrate them from historical A/B tests and holdout experiments (the Experimentation module is the top future enhancement).
- *"Why a 24-month horizon?"* — Streaming household economics are front-loaded; 24 months captures most discounted value while keeping the extrapolation honest. It's a named constant — one line to change.
- *"What would change with real data?"* — Only the Data Agent: the validation layer, model, and narrative pipeline are schema-stable. Swap the CSV for a warehouse query and the rest holds.
- *"Why should I trust the AI commentary?"* — Claude receives only summarized model outputs, is instructed to cite figures from them, and operates under word budgets. It drafts; the analyst reviews — same as any junior analyst's draft.
- *"Isn't all this obvious to leadership?"* — The levels are (US biggest, ads dominate) — which is why the Insight Agent reports **gaps, trends, and marginal economics instead**: the engaged-but-under-monetized pocket and what closing half the gap is worth, whether new cohort vintages are arriving better or worse and why, and where the next retention point pays most. The insight logic looks for exceptions to what the room already believes — so on real data it surfaces real findings.
- *"Is this gross or net CLV?"* — Both, explicitly: gross CLV values a retained household; net CLV subtracts the acquisition cost (device subsidy + marketing — sidebar assumption, default $8). At default settings the portfolio runs ~2x CLV:CAC with month-9 payback, while low-yield slices (e.g., Mexico × Streaming Stick) go underwater — exactly the slice-level economics the net lens exists to expose.
- *"Is a scenario the launch impact?"* — No: it's the steady-state run-rate value once the lift is fully realized, stated on the page. An adoption-ramp option is a listed future enhancement.

## Future enhancements

- PowerPoint export of the executive memo and key charts
- CSV export of model outputs and scenario runs
- Looker/Tableau integration for production reporting
- Real data warehouse connection (with the same validation layer)
- More advanced cohort retention curves (parametric survival models, sBG)
- Experimentation / A-B testing module to calibrate the scenario elasticities
- Automated monthly business review deck generation

## Project structure

```
lifecycle planning copilot/
├── app.py                      # Streamlit app (6 pages, sidebar nav)
├── requirements.txt
├── README.md
├── .env.example                # ANTHROPIC_API_KEY template
├── multi_agent_pipeline.svg    # architecture diagram (slide-ready)
├── .streamlit/config.toml      # dark-blue default theme
├── data/
│   └── synthetic_cohort_data.csv   # auto-generated on first run
└── src/
    ├── data_agent.py           # synthetic data, CSV load, validation
    ├── insight_agent.py        # gap analysis: the non-obvious story
    ├── segmentation_agent.py   # engagement scoring & segments (weighted)
    ├── clv_agent.py            # transparent CLV model
    ├── scenario_agent.py       # what-if engine + elasticities
    ├── prioritization_agent.py # initiative scoring & classification
    ├── claude_agent.py         # centralized Claude API access
    ├── narrative_agent.py      # grounded executive narratives
    ├── charts.py               # Plotly chart builders
    └── utils.py                # schema, constants, formatters
```
