"""
Claude Agent (centralized API access)
=====================================
All Claude API calls go through this module. Design rules:

  * Grounding: prompts receive ONLY summarized model outputs (small JSON
    blocks), never raw datasets. The system prompt forbids unsupported claims.
  * Brevity: the system prompt enforces executive-grade concision; each task
    carries an explicit word budget.
  * Robust error handling: missing key / API failures return a structured
    result the UI turns into a clear, actionable message.
  * Caching: identical prompts within a session are cached to avoid
    redundant calls and keep the demo snappy.
"""

import os
import json

from dotenv import load_dotenv

load_dotenv()

# Models available in the app's sidebar selector. Sonnet is the default —
# well-suited to analysis and concise executive writing at reasonable cost.
AVAILABLE_MODELS = {
    "claude-sonnet-4-6": "Sonnet 4.6 — balanced quality & speed (default)",
    "claude-haiku-4-5-20251001": "Haiku 4.5 — fastest, lowest cost",
    "claude-opus-4-8": "Opus 4.8 — deeper analysis, slower",
    "claude-fable-5": "Fable 5 — most capable, highest cost",
}
CLAUDE_MODEL = "claude-sonnet-4-6"  # current selection; change via set_model()
MAX_TOKENS = 900


def set_model(model_id: str):
    """Switch the model used for all narrative calls (sidebar selector)."""
    global CLAUDE_MODEL
    if model_id in AVAILABLE_MODELS:
        CLAUDE_MODEL = model_id


def get_model() -> str:
    return CLAUDE_MODEL

SYSTEM_PROMPT = """You are a senior planning analyst presenting to a VP of Consumer \
Planning & Optimization at a streaming TV platform. Your job is interpretation, not \
computation — a transparent driver-based model produced the numbers you receive.

Style rules (strict):
- Lead with the answer or verdict in the first sentence. No throat-clearing.
- Respect the word budget given in each task. Shorter is better.
- Every claim must cite a figure from the structured inputs. Never invent numbers, \
segments, or initiatives not present in the data.
- Round sensibly ($94, 12%, 3.9 months) — no false precision.
- Plain business language. No hedging filler, no AI self-reference.
- All data is synthetic; never speculate about any real company's internal data.
- Format exactly as the task specifies (bullets vs. prose)."""

_cache: dict = {}


def is_configured() -> bool:
    """True if an API key is available."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def ask_claude(instruction: str, context: dict, temperature: float = 0.3) -> dict:
    """
    Send a grounded request to Claude.

    instruction : what to produce (with an explicit word budget)
    context     : dict of summarized model outputs (small — never raw data)

    Returns {"ok": bool, "text": str | None, "error": str | None}
    """
    if not is_configured():
        return {
            "ok": False, "text": None,
            "error": (
                "No Anthropic API key found. Paste your key in the sidebar field, or "
                "add `ANTHROPIC_API_KEY=sk-ant-...` to a `.env` file in the project "
                "root (see `.env.example`) and restart. Keys: console.anthropic.com."
            ),
        }

    context_json = json.dumps(context, indent=2, default=str)
    cache_key = hash((CLAUDE_MODEL, instruction, context_json))
    if cache_key in _cache:
        return _cache[cache_key]

    prompt = (
        f"Structured model outputs (synthetic data):\n```json\n{context_json}\n```\n\n"
        f"Task: {instruction}"
    )

    try:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        result = {"ok": True, "text": response.content[0].text, "error": None,
                  "context": context}  # returned so the Verifier can ground-check
        _cache[cache_key] = result
        return result
    except Exception as e:  # noqa: BLE001 — surface any API failure to the UI
        return {
            "ok": False, "text": None,
            "error": (
                f"Claude API call failed: {e}. Check that your ANTHROPIC_API_KEY is "
                "valid and you have API credit, then try again."
            ),
        }
