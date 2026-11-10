"""Pure-Python evaluators. Each returns plain dicts; a missing or unparseable fact is UNKNOWN."""
import logging
import operator as op

from app.system1 import normalizer as nz
from app.system1.decisions.schemas import Condition, DecisionSpec

log = logging.getLogger("knowpilot.decisions")

_PARSERS = {
    "inr": nz.parse_inr, "cgpa": nz.parse_cgpa, "percentage": nz.parse_percentage, "year": nz.parse_year,
    "category": nz.parse_category, "bool": nz.parse_bool, "days": nz.parse_days,
    "number": lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else _float(v),
    "text": lambda v: str(v).strip().lower() if v is not None and str(v).strip() else None,
}
_OPS = {">=": op.ge, "<=": op.le, ">": op.gt, "<": op.lt, "==": op.eq, "!=": op.ne}


def _float(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def parse(value, value_type: str):
    return None if value is None else _PARSERS[value_type](value)


def _user_value(cond: Condition, spec: DecisionSpec):
    """The user's fact for this condition, normalized. CGPA <-> percentage only with the document's multiplier."""
    value = parse(spec.user_facts.get(cond.field), cond.value_type)
    if value is not None:
        return value, None
    mult = spec.conversions.cgpa_to_percentage if spec.conversions else None
    if mult and cond.value_type == "percentage":
        cgpa = parse(spec.user_facts.get("cgpa"), "cgpa")
        if cgpa is not None:
            return round(cgpa * mult, 2), f"CGPA {cgpa} x {mult}"
    if mult and cond.value_type == "cgpa":
        pct = parse(spec.user_facts.get("percentage"), "percentage")
        if pct is not None:
            return round(pct / mult, 2), f"{pct}% / {mult}"
    return None, None


def evaluate_condition(cond: Condition, spec: DecisionSpec) -> dict:
    out = {"id": cond.id, "label": cond.label, "field": cond.field, "operator": cond.operator,
           "required_value": cond.value, "user_value": None, "converted_by": None,
           "result": "UNKNOWN", "required": cond.required,
           "source": cond.source.model_dump() if cond.source else None}
    try:
        user, how = _user_value(cond, spec)
        out["user_value"], out["converted_by"] = user, how
        if user is None:
            return out
        if cond.operator in ("in", "not_in"):
            options = cond.value if isinstance(cond.value, list) else [cond.value]
            allowed = {parse(o, cond.value_type) for o in options} - {None}
            if not allowed:
                return out
            hit = user in allowed
            out["result"] = "TRUE" if hit == (cond.operator == "in") else "FALSE"
            return out
        target = parse(cond.value, cond.value_type)
        if target is None:
            return out
        out["result"] = "TRUE" if _OPS[cond.operator](user, target) else "FALSE"
    except Exception as e:  # a broken condition is UNKNOWN, never a crash
        log.warning("Condition %s could not be evaluated: %s", cond.id, type(e).__name__)
        out["result"] = "UNKNOWN"
    return out


def combine(results: list[str], mode: str = "ALL") -> str:
    if mode == "ANY":
        return "TRUE" if "TRUE" in results else "UNKNOWN" if "UNKNOWN" in results else "FALSE"
    return "FALSE" if "FALSE" in results else "UNKNOWN" if "UNKNOWN" in results else "TRUE"


def evaluate_boolean(spec: DecisionSpec) -> dict:
    conditions = [evaluate_condition(c, spec) for c in spec.conditions]
    required = [c["result"] for c in conditions if c["required"]]
    return {"result": combine(required, spec.combine) if required else "UNKNOWN", "conditions": conditions}


def evaluate_choice(spec: DecisionSpec) -> dict:
    for choice in spec.choices:
        if all(evaluate_condition(c, spec)["result"] == "TRUE" for c in choice.criteria):
            return {"choice_id": choice.id, "label": choice.label}
    return {"choice_id": None, "label": None}


def score(spec: DecisionSpec) -> dict:
    """Weighted share of TRUE conditions (UNKNOWN counts half), 0-100."""
    points = {"TRUE": 1.0, "UNKNOWN": 0.5, "FALSE": 0.0}
    total = sum(c.weight for c in spec.conditions)
    if not total:
        return {"score": 0}
    got = sum(c.weight * points[evaluate_condition(c, spec)["result"]] for c in spec.conditions)
    return {"score": round(100 * got / total)}
