# Lifecycle Planning Copilot: Interview Demo Script (v2)

**Purpose:** the 5-7 minute hiring-manager walkthrough. Each section has four
parts: **DO** (exact clicks), **VERIFY** (what you should see if the app is
healthy), **SAY** (the spoken line), and **WHY IT LANDS** (what it proves).
Timings assume the 6-minute pace; the "flex" beats are what you cut to hit 5
or add to fill 7.

**The arc of the story:** descriptive → diagnostic → forward-looking →
decision → deliverable. You're not demoing software; you're demonstrating how
you'd run a planning cycle for this team.

---

## Pre-flight checklist (before any live demo)

1. Open PowerShell and run:
   ```powershell
   cd "$HOME\OneDrive\Claude Folder\lifecycle planning copilot"
   python -m streamlit run app.py
   ```
2. Sidebar shows **"Claude API: ✅ configured"**. If ❌, check `.env` and restart.
3. Synthetic-data banner visible at the top — you *want* them to see it.
4. Sidebar: discount rate **10%**, acquisition cost **$8** (the defaults).
5. Pre-draft the slow AI sections so nothing loads live: **Draft portfolio
   overview** (page 1) and **Draft executive memo** (page 7). Cached for the
   session after one click.
6. Leave the app on page 1.

---

## Section 1: Executive Overview — lead with the non-obvious (0:00 – 1:00)

**DO:** Stay on page 1. Gesture across the six KPI cards, then slow down on
the three **"What the model says — beyond the obvious"** cards. Open the
**"familiar frame"** expander briefly and close it.

**VERIFY:**
- KPIs: roughly **1.27M households**, **~$17 avg CLV**, **~$3.50–3.60
  revenue/HH/mo** (calibrated to public platform disclosures).
- The three insight cards read (numbers from the current dataset):
  **Mexico · Smart TV OS** under-monetized at **$0.011/hr vs $0.025**
  portfolio, half-gap worth **≈ $0.9M/yr** · newest cohorts **−2% CLV**,
  driver **cohort mix** · +1% retention worth **$0.26/HH in the US vs $0.04
  in Brazil (6× spread)**.
- The expander contains the three "facts everyone knows" (CLV premium,
  retention gap, US concentration).

**SAY:**
> "I built this to mirror the work this role owns: lifecycle modeling, CLV,
> scenario planning, prioritization, and executive communication. The data is
> synthetic but calibrated to your public disclosures, and the architecture
> has one rule: deterministic code computes the money, AI only writes the
> language.
>
> One design choice I want to flag immediately. Leadership already knows the
> US is the biggest market and ads carry the revenue — so the insight engine
> is forbidden from reporting levels. It reports **gaps**. Right now it's
> saying: Mexico Smart-TV households are as engaged as the portfolio average
> but monetize at less than half the yield — closing half that gap is worth
> about $900K a year. And a retention point is worth six times more per
> household in the US than in Brazil — which tells you a uniform retention
> budget is mis-allocated. The familiar facts still exist — I demoted them to
> this expander. The headline space is reserved for what the room *doesn't*
> already know."

**WHY IT LANDS:** This answers the toughest interview question — "why would
an executive need this?" — before it's asked. It also shows you think about
audience, not just analysis.

---

## Section 2: Cohort Explorer (1:00 – 1:45)

**DO:** Page 2. Filter **Market = United States**, point at the retention
curves, then the engagement-vs-CLV scatter. Clear the filter.
**Flex (+20s):** open the **"What counts as engaged?"** expander and drag
one weight slider; watch the segments recompute, then set it back to 1.0.

**VERIFY:**
- KPI cards recompute on filter (household-weighted, live).
- High-engagement retention curve is visibly **flatter**, not just higher.
- Weight sliders re-segment the app live (and the takeaway numbers shift).

**SAY:**
> "Everything filters live. Two patterns matter: the high-engagement curve
> decays *slower* — the slope difference is what compounds into lifetime
> value — and the scatter is the engagement-to-CLV relationship every
> initiative here is built to exploit."

**Flex line, if you open the weights:**
> "Even the definition of 'engaged' is an assumption, not a fact — these
> weights re-segment the whole app, so we can stress-test whether a finding
> survives a different definition of engagement. Planning models should
> expose their judgment calls, not bury them."

**WHY IT LANDS:** Causal chart-reading plus epistemic honesty about
definitions — both rare in demos.

---

## Section 3: CLV Model — gross vs net (1:45 – 2:45)

**DO:** Page 3. Read the walkthrough line left to right. Then point at the
**Gross vs net CLV** row. Then set **Market = Mexico, Device = Streaming
Stick** and let the row go negative. Reset both selectors to All.

**VERIFY:**
- Walkthrough line chains to **gross CLV (~$17)**, then **− $8 acquisition
  cost = net CLV (~$9)**.
- Metrics row: **CLV:CAC ≈ 2.1x**, **payback ≈ month 9**.
- Mexico × Streaming Stick: gross ≈ **$5**, net ≈ **−$3**, CLV:CAC **0.6x**,
  payback **> 24 mo** — the row goes visibly underwater.
- Donut still shows ads ≈ 90% of revenue mix.

**SAY:**
> "The whole model is one sentence: ad revenue plus subscription revenue,
> times margin, minus cost to serve, times expected retained months,
> discounted back. Every formula is in plain English below — a finance
> partner could rebuild this in Excel.
>
> And it's explicit about gross versus net. Gross CLV values a household once
> you have it; net subtracts what it cost to acquire — and for a platform
> that sells hardware near cost, the device subsidy *is* the acquisition
> cost. At an $8 assumption the portfolio runs about two-to-one CLV-to-CAC
> with month-nine payback. But watch the slice level —" *(switch to Mexico ×
> Streaming Stick)* "— this cell is underwater: we lose money acquiring these
> households at current monetization. That's not a reason to exit Mexico;
> it's the case for the under-monetization fix the overview page already
> sized. The model connects its own dots."

**WHY IT LANDS:** Gross-vs-net is the exact distinction a hiring manager will
probe, and the underwater slice shows the tool finding something actionable,
not just describing.

---

## Section 4: Scenario Planner — the heart (2:45 – 4:15)

Three beats: scoped value, the guardrail flip, and what it measures.

**DO (beat 1):** Page 4. Set **Scope: market = Mexico**. Click the
**🚀 Onboarding push** preset.

**VERIFY:**
- Caption shows the scoped household count ("Scenario applies to … households
  in scope: Mexico").
- Sliders fill (first-week +0.15, installs +0.10, cost $750K); incremental
  value, ROI, payback all populate; verdict **Balanced ✓**.

**SAY:**
> "The question planning teams actually get asked — what's it worth if
> onboarding improves *in Mexico*? Scope the population, one click loads the
> assumption set, and the lift flows into retention through a documented
> elasticity. Incremental lifecycle value, ROI, payback — for that population
> specifically, not a portfolio-wide generality."

**DO (beat 2):** Reset scope to All markets, click **↩️ Reset to baseline**,
then set **CPM lift 0.20** and **Experience risk penalty 0.30**.

**VERIFY:**
- Monetization per streaming hour **up**; month-6 retention **down ~3-4
  pts**; **streaming hours down** (the new effect); banner flips to amber
  **Guardrail flag**.

**SAY:**
> "Now the trade-off case: push ad monetization hard and assume some
> experience cost. Yield per hour rises, retention falls — and notice hours
> fall too. That's deliberate: ad revenue is hours-driven, so an aggressive
> ad push partially cannibalizes its own inventory. The trade-off is
> self-limiting in the model because it is in reality. The verdict flips:
> this revenue is borrowing from lifetime value."

**DO (beat 3):** Briefly open **"What this page measures"** — don't read it,
just show it exists — then reset to baseline.

**SAY:**
> "And the page states its own epistemics: this is steady-state run-rate
> value once a lift is fully realized, not a launch ramp; the elasticities
> are planning assumptions I'd calibrate from your historical A/B tests on
> day one. The model never pretends to know more than it does."

**WHY IT LANDS:** Scoping makes impact concrete; the self-limiting loop shows
modeling judgment; the framing beat preempts "how do you know these numbers?"

---

## Section 5: Initiative Prioritizer (4:15 – 5:05)

**DO:** Page 5. Scroll from the Step 1 editable table to the Step 2 ranking.
**Flex (+20s):** add a blank row, type a name like "Kids profile launch," set
trc_usage_lift 0.05 and a cost, and watch it get ranked.

**VERIFY:**
- Eight editable initiatives; add-row works; ranking recomputes.
- **Ad Monetization Optimization** has the highest monetization lift but ranks
  below better-balanced work (retention risk 4/5); the legacy `score` column
  would rank it higher.

**SAY:**
> "Initiatives are inputs, not facts: which levers each one moves, cost, and
> 1-to-5 sizing scores — editable live, mid-meeting. Step two runs every row
> through the same CLV engine. Monetization lift and experience impact are
> *modeled*, not opinions — and the ranking is balanced: the biggest revenue
> lift on the board still ranks below the engagement push because its
> retention risk is high. Compare the two score columns and you can see
> exactly where a revenue-only ranking would over-fund risky work. The output
> is a funding sequence — now, next, foundational — not just a ranked list."

**WHY IT LANDS:** An editable, auditable prioritization process is the core
deliverable of this role.

---

## Section 6: Monetization Guardrails (5:05 – 5:40)

**DO:** Page 6. Point at the two segment KPI cards, the quadrant map, then
click one tab.

**SAY:**
> "This page asks the strategic question directly: are we monetizing engaged
> households effectively, and is monetization anywhere coming at the expense
> of the experience? Top-left of the map is the opportunity — engaged,
> under-monetized, where yield and attach levers are safest. Bottom-right is
> the watch list — revenue sitting on a weak experience. Transparent
> percentile blends, weights documented in code."

**WHY IT LANDS:** Mirrors the platform's actual posture: monetization depth
with experience discipline.

---

## Section 7: Executive Memo + Verifier (5:40 – 6:30)

**DO:** Page 7. Show the pre-drafted memo; point at the scenario-and-scope
line above it, then the verifier line below it. Click download.

**VERIFY:**
- Memo has all six sections; Supporting Insights cite the **gap insights**
  (under-monetized pocket, vintage trend, marginal retention) — not "US is
  the biggest market."
- The scope from your last scenario run is shown and lands in the memo.
- Verifier line: green ("all N figures trace") or amber (flagged figures) —
  either is a win.

**SAY:**
> "The deliverable. Claude drafts the planning-review memo from the model
> outputs — and it's instructed to build its supporting insights from the
> gap analysis, never from restating what the room already knows. The line
> underneath is the part I care most about: a verifier machine-checks every
> figure in the draft against the model outputs it was given. The AI never
> goes unchecked, and the math never comes from the AI. One click exports
> for a deck or doc."

**WHY IT LANDS:** Responsible AI plus audience awareness, in one artifact.

---

## Close (6:30 – 6:50)

**SAY:**
> "The value to the team is cycle time, trust, and altitude. The analysis
> that takes a week of pulls and deck-building happens in one session; every
> number traces to a formula a finance partner can audit; and the insight
> layer is pointed at what leadership *doesn't* already know. The data here
> is synthetic — but plug in real cohort data and this exact workflow runs
> unchanged. That's how I'd structure the real thing on day one."

---

## If they interrupt with questions (likely — and good)

- **"How do you know the elasticities?"** → "I don't — they're visible
  planning assumptions, and the page says so. With your data I'd calibrate
  them from historical experiments; the Experimentation module is the top
  future enhancement."
- **"Is this gross or net CLV?"** → Page 3 shows both; CAC is a sidebar
  assumption (default $8 ≈ device subsidy + marketing); 2.1x CLV:CAC,
  month-9 payback at defaults.
- **"Aren't these insights obvious?"** → "The levels are — that's why the
  insight engine only reports gaps, trends, and marginal economics. On real
  data it surfaces real exceptions to what leadership believes."
- **"What changes with real data?"** → Only the Data Agent. Schema-stable
  validation; swap the CSV for a warehouse query and everything downstream
  holds.
- **"Why trust the AI?"** → It only narrates summarized model outputs under
  word budgets, and the verifier machine-checks every figure it cites.

## Rehearsal checklist

- [ ] Page 1: three gap-insight cards populated; familiar-frame expander works
- [ ] Page 2: filters recompute; weight slider re-segments live (reset to 1.0!)
- [ ] Page 3: net CLV ≈ $9, CLV:CAC ≈ 2.1x, payback month 9; Mexico × Stick
      goes negative; reset selectors to All
- [ ] Page 4: Mexico scope + Onboarding preset = Balanced ✓; CPM 0.20 +
      penalty 0.30 = Guardrail flag with hours down; reset everything
- [ ] Page 5: add-row works; Ad Monetization ranks lower on balanced than legacy
- [ ] Page 7: memo cites gap insights; scope line shows; verifier line present
- [ ] AI drafts pre-generated on pages 1 and 7

## Troubleshooting

- **CLV in the hundreds:** stale dataset — delete
  `data/synthetic_cohort_data.csv`, restart, it regenerates calibrated.
- **Claude ❌:** check `.env`, restart, or paste the key in the sidebar.
- **AI section errors mid-demo:** every verdict, chart, and ranking works
  without Claude. Say "the narrative layer drafts from these same numbers"
  and keep moving.
- **Verifier amber flag live:** use it — "that's the verifier doing its job:
  it can't trace that figure one-to-one, so it tells me to confirm before
  sharing."
- **Insight card numbers differ from this script:** they recompute from the
  live dataset — read what's on screen; the *structure* of each line
  (gap → value, trend → driver, best vs worst market) is what you rehearse.
