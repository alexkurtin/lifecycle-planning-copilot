"""
Narrative Verifier Agent
========================
Deterministic grounding check for AI-generated narratives: every figure
Claude cites is machine-checked against the structured model outputs that
were in its prompt, BEFORE a human relies on the draft.

This is the guardrail that matters for an analysis tool: the narrative layer
is generated language, so its claims get verified against the deterministic
model — not the other way around.

How it works (no AI involved — pure parsing):
  1. Extract substantive figures from the draft ($94, $1.3M, 12%, 3.2x,
     +2.4 pts, 11.4 months, 1,268,059). Bare small integers without units
     are ignored (months names, bullet counts, etc. would be noise).
  2. Collect every number in the grounding context, plus transparent derived
     variants: ×100 / ÷100 (rate ↔ percent), ×12 (monthly ↔ annual), and
     baseline-vs-scenario differences and % changes for matching KPI keys
     (so "a $12 CLV lift" traces even though only the two levels appear).
  3. A figure is "verified" if it matches any context number within a 3.5%
     relative tolerance (or ±0.5 absolute for rounded small numbers).

Figures that don't trace are flagged in the UI — they may be legitimate
derivations (a ratio of two segment CLVs), but the analyst should confirm
them before sharing. Honest amber beats false green.
"""

import re

_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9}

# Substantive figures only: currency, percents/points, multiples, durations,
# decimals, and thousands-separated numbers. Bare small ints are skipped.
_FIGURE_RE = re.compile(
    r"\$\s?\d[\d,]*\.?\d*(?:\s?[KkMmBb](?![A-Za-z]))?"  # $94, $1.3M (not '$3 monthly')
    r"|[-+]?\d[\d,]*\.?\d*\s?(?:%|pts?\b)"             # 12%, +3.5 pts
    r"|\b\d+\.?\d*\s?x\b"                              # 3.2x
    r"|\b\d+\.\d+\s?(?:months?|mo)\b"                  # 11.4 months
    r"|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"               # 1,268,059
    r"|\b\d+\.\d+\b"                                   # 11.4
)


def _parse_figure(raw: str):
    """
    Convert a matched figure string to (value, tolerance).

    Tolerance is precision-aware: a figure quoted as "9.9" implies ±0.05,
    "$94" implies ±0.5, "$21.2M" implies ±0.05M. This is what makes the
    check strict — an invented "9.9x" can't hide behind a nearby 10.0%.
    """
    s = raw.strip().lstrip("$").replace(",", "").replace("+", "").strip()
    mult = 1.0
    low = s.lower()
    for suf, m in _SUFFIX.items():
        if low.endswith(suf):
            s, mult = s[:-1], m
            break
    s = re.sub(r"(%|pts?|months?|mo|x)\s*$", "", s, flags=re.I).strip()
    try:
        val = float(s) * mult
    except ValueError:
        return None
    decimals = len(s.split(".")[1]) if "." in s else 0
    tol = 0.5 * (10 ** -decimals) * mult  # half a unit of quoted precision
    return val, tol


def extract_figures(text: str) -> list:
    """All substantive (raw, value, tolerance) figures cited in a narrative."""
    out = []
    for m in _FIGURE_RE.finditer(text):
        raw = m.group(0)
        parsed = _parse_figure(raw)
        if parsed is not None:
            out.append((raw.strip(), parsed[0], parsed[1]))
    return out


def _walk_numbers(obj, pool: set):
    """Recursively collect every number in the grounding context."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        pool.add(float(obj))
    elif isinstance(obj, str):
        for m in re.finditer(r"-?\d[\d,]*\.?\d*", obj):
            try:
                pool.add(float(m.group(0).replace(",", "")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, pool)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, pool)


def collect_context_numbers(context: dict) -> set:
    """Context numbers + transparent derived variants (see module docstring)."""
    base: set = set()
    _walk_numbers(context, base)

    derived: set = set()
    for n in base:
        derived.update((n, n * 100, n / 100, n * 12))

    # Baseline-vs-scenario derivations: differences and % changes for the
    # same KPI key, so "lift" figures trace back to the two levels.
    b = context.get("baseline_kpis") or {}
    s = context.get("scenario_kpis") or {}
    for k in set(b) & set(s):
        try:
            bv, sv = float(b[k]), float(s[k])
        except (TypeError, ValueError):
            continue
        diff = sv - bv
        derived.update((diff, abs(diff), diff * 100, abs(diff) * 100))
        if bv:
            pct = (sv / bv - 1) * 100
            derived.update((pct, abs(pct), pct / 100))
    return derived


def _matches(fig: float, tol: float, pool: set) -> bool:
    """Match within the figure's quoted precision (plus a 0.1% float floor)."""
    afig = abs(fig)
    for n in pool:
        eps = max(tol, 0.001 * max(abs(n), afig))
        if abs(fig - n) <= eps:
            return True
        # Sign-agnostic for deltas quoted without direction
        if abs(afig - abs(n)) <= eps:
            return True
    return False


def verify_narrative(text: str, context: dict) -> dict:
    """
    Check every substantive figure in a narrative against the grounding
    context. Returns {"total", "verified", "unverified": [raw strings]}.
    """
    if not text or not context:
        return {"total": 0, "verified": 0, "unverified": []}
    pool = collect_context_numbers(context)
    figures = extract_figures(text)
    unverified = [raw for raw, val, tol in figures if not _matches(val, tol, pool)]
    return {
        "total": len(figures),
        "verified": len(figures) - len(unverified),
        "unverified": unverified,
    }
