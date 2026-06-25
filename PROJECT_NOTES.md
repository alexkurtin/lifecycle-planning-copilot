# Project Notes: Lifecycle Planning Copilot

Context handoff file. If you are Claude starting a fresh session: read this and
README.md before touching anything. If you are Alex: point a new session here.

## What this is

Interview demo project for a Consumer Planning & Optimization / Planning &
Analysis role at a streaming TV platform (Roku-style). Streamlit app: cohort
CLV model, scenario planner, initiative prioritizer, monetization guardrails,
Claude-generated executive narratives. All data synthetic. Run with
`python -m streamlit run app.py` (deps in requirements.txt; key in `.env`,
already configured locally; never print or move the key).

## Current state: COMPLETE AND TESTED (round 2 — June 2026 feedback pass)

All 7 pages pass end-to-end (verified via streamlit.testing.v1 AppTest):
1 Executive Overview · 2 Cohort Explorer · 3 CLV Model · 4 Scenario Planner ·
5 Initiative Prioritizer · 6 Monetization Guardrails · 7 Executive Memo.

Round-2 changes (from Alex's reviewer feedback — "insights too obvious,
what is this measuring, CLV vs CAC"):
- **Insight Agent** (`src/insight_agent.py`, NEW): gap analysis replaces
  level-based takeaways on Overview + grounds the Memo. Three insights:
  under-monetized engaged pocket (with $/yr of closing half the yield gap),
  cohort vintage trend (with honest driver attribution — falls back to
  "cohort mix" when neither retention nor revenue matches the CLV move),
  marginal retention value by market (+1% retention pushed through the CLV
  engine per market; US$0.26/HH vs Brazil $0.04, 6x spread). Old "three
  facts" demoted to an "orientation" expander.
- **Net CLV / CAC**: sidebar acquisition-cost assumption (default $8 ≈
  device subsidy + marketing; $8 → 2.1x CLV:CAC, month-9 payback;
  Mexico·Stick goes underwater — that's the talking point).
  `clv_agent.payback_month()` computes cumulative-discounted-GP payback.
  CLV page has market/device selectors + gross/net/CLV:CAC/payback row.
- **Scenario scope** (market/device/segment selectors) — scenario runs on
  the scoped population only; scope persists to the Memo.
- **Risk penalty extended**: also drags streaming hours by
  ELASTICITY["risk_to_hours"]=0.5 × penalty × cpm_lift (self-limiting ad
  load — it cannibalizes its own hours-driven inventory).
- **Engagement weights**: add_engagement_segments(df, weights=) + sliders
  on Cohort Explorer (keys ew_fw/ew_ai/ew_trc/ew_hrs, setdefault before
  load_baseline; qcut has a rank-cut fallback for tie-heavy weights).
- **Framing**: page_header(mode=) chips descriptive vs forward-looking;
  "What this page measures" expander on Scenario page (steady-state
  run-rate, not launch ramp; no per-initiative margin); prioritizer
  methodology now defines monetization lift / experience impact.
- **Cosmetics**: charts.py LAYOUT t=84 + title_y/yanchor (title-legend
  collision fix); KPI metric CSS wraps; Top-initiative card truncates at
  22 chars with full name in tooltip.

DEMO_SCRIPT.md has the ~3-minute interview walkthrough. README.md has the
architecture, formulas, calibration notes, and Q&A prep.

## Key design decisions (do not silently undo)

- **Deterministic code computes money; AI only writes language.** Claude calls
  are centralized in `src/claude_agent.py`, receive only summarized model
  outputs (never raw rows), under strict word budgets. Sidebar model selector
  (Sonnet default).
- **Verifier** (`src/verifier_agent.py`): every figure in a Claude draft is
  machine-checked against the prompt's grounding context, precision-aware
  (a quoted "9.9" must match within ±0.05). Wired into `claude_section()` in
  app.py. ask_claude returns `context` in its result dict for this purpose.
- **Calibration to public Roku disclosures** (user asked for this explicitly):
  ~140 streaming hrs/HH/mo; blended revenue ≈ $3.58/HH/mo ≈ $43/yr ARPU
  (public: ~$41-45). Achieved via two visible constants in `src/clv_agent.py`:
  PLATFORM_AD_MONETIZATION_SHARE = 0.10, SUBSCRIPTION_REVENUE_SHARE = 0.20.
- **Monetization guardrails layer** (user's "Roku prioritizes monetization"
  request): `src/monetization_agent.py` percentile-blend scores (depth,
  experience health, balanced value), gap-based guardrail segment tables,
  experience_risk_penalty lever in the scenario agent (drags retention by
  penalty × (cpm_lift + sub_conversion_lift)), deterministic Balanced/Flagged
  verdict on the Scenario page.
- **Prioritizer ranks by balanced_score** (monetization lift + experience
  impact + retention risk + value/feasibility), NOT pure revenue. Legacy
  `score` kept for comparison. Initiatives are an editable st.data_editor
  table (inputs) feeding the CLV engine (outputs). Talking point: Ad
  Monetization Optimization ranks #2 on legacy score, #3 on balanced.
- **Scenario elasticities** documented at top of `src/scenario_agent.py`
  (first-week→retention 0.25, installs 0.15, TRC→retention 0.20, TRC→hours
  0.40). Planning estimates by design; "calibrate from experiments" is the
  interview answer.
- **Theme:** dark blue default via `.streamlit/config.toml`; charts are
  plotly_dark with transparent backgrounds; KPI-card CSS in app.py.
- Synthetic dataset: 12 cohorts × 6 markets × 4 devices = 288 rows,
  regenerated only if `data/synthetic_cohort_data.csv` is missing. A latent
  quality factor links engagement→retention→CLV. Schema in
  `src/utils.py REQUIRED_COLUMNS`; CSV upload validates against it.

## Session-tooling quirks (for Claude, not Alex)

- This OneDrive-mounted folder has a stale-size cache in the sandbox mount:
  after editing an existing file via file tools, bash often sees it truncated
  (or null-padded). The Windows-side file is always correct. Test pattern that
  works: copy project to /tmp, null-strip (`tr -d '\000'`), ast.parse each
  file, re-apply any missing tails programmatically, then run AppTest from
  /tmp. Brand-new files sync fine; edits to existing files are the problem.
- README.md is sometimes EBUSY-locked (user has it open); retry after a pause.
- Deletes in mounted folders need user permission (was declined once for
  __pycache__; leave cache files alone).

## Backlog ideas (user has NOT asked for these yet)

PowerPoint export of the memo, CSV export of scenario runs, experimentation
module to calibrate elasticities, parametric retention curves (sBG),
automated monthly business review deck, adoption-ramp option for scenarios
(current framing: steady-state run-rate only), per-market CAC.
