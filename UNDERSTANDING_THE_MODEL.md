# Understanding the Model: What Each Section Measures and Why

A plain-English companion to the app. For each page: what is being measured,
how it's actually computed, and why it matters for a Consumer Planning &
Optimization role. Read this once slowly and you can answer any "walk me
through how this works" question without touching the code.

---

## Core concepts used everywhere

**Cohort.** A group of households that activated in the same month, sliced
further by market and device type. We analyze cohorts instead of individuals
because planning teams rarely get household-level data, and because cohorts
reveal the thing that matters: how behavior *ages*. A row in this dataset is
"households that activated in March 2025, in Brazil, on a Smart TV."

**Retention curve.** The share of a cohort still active at month 1, 3, 6, and
12. It always slopes down. The two things to read from it: the *level* (how
many survive) and the *slope* (how fast they decay). A flatter slope is worth
more than a higher starting point, because value compounds over months.

**Household-weighted average.** Every average in the app weights by cohort
size. A 50,000-household US cohort moves the portfolio average more than a
3,000-household German one. Unweighted averages would let small cohorts
distort the story; this is the single most common analytical mistake in
cohort reporting, and the app avoids it everywhere.

**Discounting.** A dollar of gross profit 20 months from now is worth less
than a dollar today. The model discounts each future month's profit at an
adjustable annual rate (default 10%). This is why "discounted CLV" is the
headline metric: it's the finance-grade version.

**Percentile score.** Several metrics (engagement, monetization depth,
experience health) are 0-100 scores built by ranking every cohort row against
the others. Percentiles are used instead of raw values so the scores stay
meaningful if someone uploads a dataset with different units or scales.

**Elasticity.** A documented assumption about flow-through: "if first-week
engagement rises 10%, retention rises 2.5% (a 0.25 elasticity)." These are
planning estimates, deliberately visible, and the honest answer about them is
that real data would calibrate them from A/B tests.

---

## Page 1: Executive Overview

**What's measured:** portfolio-level KPIs (total households, average
discounted CLV, total lifecycle value, month-6 retention, monthly revenue per
household) plus three computed takeaways: the CLV premium of high-engagement
households over low, the retention gap that explains it, and how concentrated
value is by market.

**How:** every KPI is a household-weighted aggregate of the cohort-level
model outputs. Total lifecycle value is discounted CLV per household times
households, summed. The takeaways are simple ratios of the segment summaries
(for example, High-segment average CLV divided by Low-segment average CLV).

**Why it matters for the role:** this is the "monthly business review"
surface. The skill being demonstrated is leading with conclusions a VP can
act on rather than a wall of data. The three takeaways are also the thesis of
the whole tool: early engagement predicts lifetime value, so engagement is
where planning dollars should go.

---

## Page 2: Cohort Explorer

**What's measured:** the same KPIs and four relationships, on any filtered
slice: CLV by market, CLV by activation cohort, retention curves by
engagement segment, and engagement score vs. CLV per cohort cell.

**How the engagement segments work:** each cohort row gets an engagement
score, the equal-weight average of its percentile ranks on four behaviors:
first-week hours, first-week app installs, free-channel (Roku Channel-style)
usage rate, and steady-state monthly streaming hours. The top third of scores
is the High segment, middle third Medium, bottom third Low.

**What to read in the charts:** the retention chart shows High decaying
*slower*, not just starting higher. The scatter shows the engagement-to-CLV
relationship the initiatives exploit. CLV by cohort month shows seasonality:
holiday-quarter cohorts are bigger but slightly lower intent.

**Why it matters for the role:** this is consumer analytics in its purest
form: find where value concentrates and why, before deciding where to act.
The filtering matters because real planning questions arrive pre-sliced
("what's happening with international Partner TV households?").

---

## Page 3: CLV Model

**What's measured:** customer lifetime value per household, built from five
auditable drivers.

**How, step by step (this is the chain to internalize):**

1. **Ad revenue per household per month.** Hours streamed × share of hours
   that are ad-supported × ad impressions per hour × fill rate (share of ad
   slots actually sold) × CPM ÷ 1,000. That gives the total ad value a
   household generates. It's then multiplied by a **10% platform monetization
   share**, because most viewing happens inside third-party apps where the
   platform gets little or no ad inventory. This 10% is what makes the model
   match public ARPU figures.
2. **Subscription revenue per household per month.** Conversion rate × ARPU ×
   a **20% revenue share**, because platforms earn a billing cut, not the
   subscriber's full payment.
3. **Gross profit per household per month.** Total revenue × gross margin,
   minus a per-household support cost.
4. **Expected retained months.** The area under the retention curve over 24
   months. The curve is interpolated through the observed month 1/3/6/12
   points and extrapolated for months 13-24 using the decay rate implied
   between months 6 and 12. Intuition: "on average, how many months of profit
   does one activated household deliver?"
5. **Discounted CLV.** Each month's expected profit (profit × probability the
   household is still active) discounted back to today and summed.

**The one-line version:** revenue per month, times margin, minus cost to
serve, times how long they stay, discounted.

**Why it matters for the role:** CLV is the unit economics backbone of every
planning decision: it converts behavioral metrics (hours, retention,
conversion) into dollars, which is what makes initiative ROI comparable. The
reason the model is deliberately simple and visible is trust: finance
partners sign off on models they can rebuild, and a planning team's
recommendations are only as strong as finance's trust in their math.

---

## Page 4: Scenario Planner

**What's measured:** what happens to CLV, revenue, gross profit, total
lifecycle value, ROI, and payback when you change a driver. Plus two
guardrail metrics: monetization per streaming hour and the month-6 retention
delta.

**How:** each slider multiplies a driver up or down across every cohort row,
then the entire CLV model reruns. Engagement sliders also flow into retention
through the documented elasticities (first-week 0.25, installs 0.15,
free-channel usage 0.20, plus a 0.40 flow-through from free-channel usage to
streaming hours). The **experience risk penalty** is the reverse lever: it
drags retention down in proportion to how hard the monetization levers (CPM,
subscription conversion) are being pushed, modeling the risk that aggressive
monetization degrades the viewing experience.

**The output metrics:**
- *Incremental value* = scenario total lifecycle value minus baseline. This
  is the size of the prize.
- *ROI proxy* = incremental value ÷ one-time initiative cost.
- *Payback proxy* = months to recover the cost if the incremental value
  accrues evenly over the 24-month horizon.
- *The verdict banner* is deterministic logic, not AI: value up with
  retention roughly flat or better = Balanced; value up but retention down
  more than half a point = Guardrail flag ("revenue borrowing from lifetime
  value"); monetization up but total value down = Net negative.

**Why it matters for the role:** this is business case analysis. Every
initiative pitch eventually becomes "what is it worth and what does it cost,"
and this page answers that in seconds with assumptions on the table. The
guardrail verdict encodes the platform's real strategic constraint: ad-first
businesses can always raise short-term revenue by degrading the experience,
so a good planning tool must make that trade-off visible rather than letting
revenue numbers hide it.

---

## Page 5: Initiative Prioritizer

**What's measured:** a ranked portfolio of eight initiatives, each scored on
modeled financials plus planning judgment.

**How, in two steps:**

*Step 1, inputs (editable).* Each initiative is defined by which driver
levers it moves and how much (its scenario), what it costs, and five 1-5
planning scores: confidence, speed to impact, execution complexity, strategic
fit, general risk, plus a dedicated *retention risk* score (how likely the
initiative is to annoy users). The lifts are hypotheses that would come from
experiments and product-team sizing in a real cycle; here they're editable so
the assumptions are never hidden.

*Step 2, outputs (computed).* Every row runs through the same scenario engine
as page 4, producing its incremental value, CLV lift, *monetization lift* (%
change in revenue per household), *experience impact* (a blend of the % changes
in retention, streaming hours, and first-week hours), ROI, and payback. Then
two composite scores:
- The **legacy score** weights financial impact most heavily (a revenue-first
  ranking).
- The **balanced score** weights monetization lift, value, and experience
  impact positively, and penalizes complexity and retention risk. The ranking
  uses this one.

The gap between the two rankings is the insight: Ad Monetization Optimization
has the largest monetization lift on the board but ranks lower on balance
because its retention risk is high. A revenue-only ranking would fund it
first; the balanced view says de-risk it first.

**Classification logic:** initiatives with no meaningful direct lift are
*Enablers* (reporting infrastructure: its value is decision speed, not
modeled CLV). The rest split by complexity: low complexity = *Quick win*,
high = *Strategic bet*. That feeds the Now / Next / Foundational sequence,
which is how planning teams actually present funding recommendations.

**Why it matters for the role:** initiative prioritization is the core
deliverable of a planning function: take more good ideas than budget, score
them on comparable terms, and defend a sequence. The two-step structure
demonstrates the discipline that matters most: keep inputs (assumptions) and
outputs (modeled results) visibly separate so the debate happens on
assumptions, not on whose spreadsheet is right.

---

## Page 6: Monetization Depth & Experience Guardrails

**What's measured:** whether engaged households are being monetized
effectively, and whether monetization anywhere looks unsustainable.

**The three scores (all 0-100 percentile blends, weights in
`src/monetization_agent.py`):**
- **Monetization depth**: how deeply a cohort is monetized. Weighted blend of
  revenue per household (35%), monetization per streaming hour (25%),
  subscription conversion (20%), ad-supported share (10%), fill rate (10%).
- **Experience health**: how strong the consumer experience is. Month-6
  retention (25%), month-12 retention (20%), monthly hours (20%), first-week
  hours (15%), installs (10%), month-1 retention (10%).
- **Balanced value**: 40% CLV percentile + 30% depth + 30% health, minus up
  to a 15-point penalty for weak retention. By construction, a cohort can
  only score high if monetization is NOT coming at the expense of experience.

**The key ratio:** *monetization per streaming hour* (revenue ÷ hours). Hours
are the platform's inventory; this is the yield on attention. A market with
healthy engagement but low yield is an under-monetization gap, which is a
pricing/attach problem, not a demand problem.

**The quadrant map:** experience health (y) vs. monetization depth (x).
Top-left = engaged but under-monetized: the safest place to deepen
monetization, because the relationship with the household can absorb it.
Bottom-right = monetized but fragile: revenue that may be borrowing from
lifetime value. The three tables list the largest gaps in each direction plus
the best balanced segments whose playbook is worth replicating.

**Why it matters for the role:** this is the page that maps most directly to
a streaming platform's actual strategy: platform revenue growth is the
engine, but the company is famously protective of the viewing experience. A
planning team's job is to find monetization headroom that doesn't trigger
churn, and this page is that search made systematic.

---

## Page 7: Executive Memo (and the Verifier)

**What's produced:** a planning-review memo drafted by Claude from the model
outputs: a 5-bullet summary, a recommendation, supporting insights, risks and
assumptions, a proposed pilot with a success metric, and a one-sentence
slide-ready headline.

**How the AI is kept honest (three layers):**
1. **Grounding**: Claude never sees raw data, only small summarized tables
   and KPI dictionaries. It cannot compute anything; it can only interpret
   numbers it was handed.
2. **Prompt constraints**: strict word budgets, "lead with the verdict,"
   every claim must cite a figure from the inputs, and the recommendation
   must be the best *balance* of monetization, CLV, confidence, feasibility,
   and experience health, never simply the highest-revenue option.
3. **The Verifier** (`src/verifier_agent.py`): after Claude drafts, a pure
   parsing step (no AI) extracts every figure from the text ($94, 12%, 3.2x)
   and checks each against the numbers that were in the prompt, including
   derived forms like rate-to-percent, monthly-to-annual, and
   baseline-vs-scenario deltas. Matching is precision-aware: a figure quoted
   as "9.9" must match within ±0.05, so an invented number can't hide behind
   a nearby real one. Anything untraceable gets flagged in amber before a
   human relies on it.

**Why it matters for the role:** the recruiter flagged AI tooling as part of
this job. This page is the demonstration of *mature* AI use: AI compresses
the hours between "model is done" and "memo is meeting-ready," while the
architecture guarantees the math never comes from the AI and the AI's
language never goes unchecked. That division of labor is the defensible
answer to "how would you use Claude on this team?"

---

## The thread that ties it together

Pages 1-3 answer *where is the value and what drives it* (analytics).
Page 4 answers *what is a change worth* (business case).
Pages 5-6 answer *what should we fund, in what order, within what constraints*
(planning).
Page 7 answers *how do we communicate it upward* (executive communication).

That sequence (measure, model, simulate, prioritize, communicate) is the
planning and analysis job in miniature, which is the point of the project.
