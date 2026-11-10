"""Runs boolean, choice and score evaluations in parallel and aggregates the outcome."""
import asyncio
import logging
import time

from app.system1.decisions import evaluators
from app.system1.decisions.schemas import DecisionSpec

log = logging.getLogger("knowpilot.decisions")

ELIGIBLE, NOT_ELIGIBLE, NEEDS_MORE_INFO = "ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_MORE_INFO"
_FALLBACK = {
    "boolean": {"result": "UNKNOWN", "conditions": []},
    "choice": {"choice_id": None, "label": None},
    "score": {"score": None},
}


async def _timed(name: str, fn, spec: DecisionSpec, t0: float) -> tuple[str, dict, dict]:
    start = (time.perf_counter() - t0) * 1000
    try:
        result, error = await asyncio.to_thread(fn, spec), None
    except Exception as e:  # one failing evaluator becomes UNKNOWN; the engine keeps going
        log.warning("Evaluator %s failed: %s", name, type(e).__name__)
        result, error = dict(_FALLBACK[name]), type(e).__name__
    end = (time.perf_counter() - t0) * 1000
    return name, result, {"decision": name, "start_ms": round(start, 2), "end_ms": round(end, 2), "error": error}


async def run(spec: DecisionSpec, evaluators_override: dict | None = None) -> dict:
    fns = {"boolean": evaluators.evaluate_boolean, "choice": evaluators.evaluate_choice, "score": evaluators.score}
    fns.update(evaluators_override or {})
    t0 = time.perf_counter()
    done = await asyncio.gather(*(_timed(name, fn, spec, t0) for name, fn in fns.items()))
    results = {name: result for name, result, _ in done}

    conditions = results["boolean"]["conditions"]
    required = [c for c in conditions if c["required"]]
    if any(c["result"] == "FALSE" for c in required) and spec.combine == "ALL":
        outcome = NOT_ELIGIBLE
    else:
        outcome = {"TRUE": ELIGIBLE, "FALSE": NOT_ELIGIBLE}.get(results["boolean"]["result"], NEEDS_MORE_INFO)
    missing = sorted({c["field"] for c in required if c["result"] == "UNKNOWN"}) if outcome == NEEDS_MORE_INFO else []

    return {
        "outcome": outcome,
        "missing_facts": missing,
        "conditions": conditions,
        "choice": results["choice"],
        "score": results["score"]["score"],
        "timings": [t for _, _, t in done],
    }


def run_sync(spec: DecisionSpec) -> dict:
    return asyncio.run(run(spec))
