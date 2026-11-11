"""Gemini calls with structured output. The LLM extracts rules and writes answers; Python decides."""
import logging
from pathlib import Path
from typing import Literal

from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.errors import AppError
from app.llm.client import get_client
from app.llm.embeddings import call_with_retry
from app.system1.decisions.schemas import Condition, Conversions, DecisionSpec, Source

log = logging.getLogger("knowpilot.generate")
PROMPTS = Path(__file__).resolve().parent / "prompts"
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)", "hinglish": "Hinglish (Hindi written in Latin script)"}


# ---------- schemas the model fills (no Any / dict: Gemini needs concrete types) ----------
class LLMSource(BaseModel):
    filename: str
    page: int


class LLMCondition(BaseModel):
    label: str
    field: str
    operator: Literal[">=", "<=", ">", "<", "==", "!=", "in", "not_in"]
    value: str | None = None
    values: list[str] | None = None
    value_type: Literal["number", "inr", "cgpa", "percentage", "year", "category", "bool", "days", "text"]
    source: LLMSource


class LLMFact(BaseModel):
    field: str
    value: str | None = None


class LLMSpec(BaseModel):
    conditions: list[LLMCondition]
    user_facts: list[LLMFact]
    cgpa_to_percentage: float | None = None
    cgpa_to_percentage_source: LLMSource | None = None


class LLMSuggestions(BaseModel):
    questions: list[str]


class LLMAnswer(BaseModel):
    covered: bool
    answer_text: str
    used_sources: list[LLMSource]


# ---------- helpers ----------
def format_excerpts(chunks: list[dict]) -> str:
    return "\n\n".join(
        f'<<<EXCERPT file="{c["filename"]}" page={c["page_number"]}>>>\n{c["content"]}\n<<<END EXCERPT>>>'
        for c in chunks
    )


def _prompt(name: str, **kw) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8").format(**kw)


def _generate(prompt: str, schema: type[BaseModel]):
    config = types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json", response_schema=schema)
    resp = call_with_retry(
        lambda: get_client().models.generate_content(
            model=get_settings().GEMINI_CHAT_MODEL, contents=prompt, config=config
        )
    )
    if resp.parsed is None:
        raise AppError("llm_unavailable", "The AI service is temporarily unavailable. Please try again.", 503)
    return resp.parsed


def _known(chunks: list[dict]) -> set[tuple[str, int]]:
    return {(c["filename"], c["page_number"]) for c in chunks}


# ---------- a) rules -> DecisionSpec ----------
def extract_decision_spec(question: str, chunks: list[dict], language: str) -> DecisionSpec:
    out: LLMSpec = _generate(
        _prompt("extract_spec.txt", language_name=LANGUAGE_NAMES[language], question=question,
                excerpts=format_excerpts(chunks)),
        LLMSpec,
    )
    known = _known(chunks)
    conditions = [
        Condition(id=f"c{i}", label=c.label, field=c.field, operator=c.operator,
                  value=c.values if c.operator in ("in", "not_in") else c.value,
                  value_type=c.value_type, source=Source(filename=c.source.filename, page=c.source.page))
        for i, c in enumerate(out.conditions, 1)
        if (c.source.filename, c.source.page) in known  # drop anything not cited from the given excerpts
    ]
    if not conditions:
        raise AppError("no_rules_found", "No eligibility rules were found in the documents.", 422)
    conv_src = out.cgpa_to_percentage_source
    conversions = None
    if out.cgpa_to_percentage and conv_src and (conv_src.filename, conv_src.page) in known:
        conversions = Conversions(cgpa_to_percentage=out.cgpa_to_percentage,
                                  source=Source(filename=conv_src.filename, page=conv_src.page))
    facts = {f.field: f.value for f in out.user_facts if f.value not in (None, "", "null")}
    return DecisionSpec(user_facts=facts, conditions=conditions, conversions=conversions)


# ---------- b) final answer ----------
def _decision_text(decision: dict) -> tuple[str, str]:
    lines = [f"Outcome: {decision['outcome']}"]
    for c in decision["conditions"]:
        lines.append(f"- {c['label']}: {c['result']} (user: {c['user_value']}, required: {c['required_value']})")
    if decision["missing_facts"]:
        lines.append("Missing facts: " + ", ".join(decision["missing_facts"]))
    block = "\nDECISION (computed by the system; final):\n" + "\n".join(lines) + "\n"
    rules = ("- Start the answer by stating the decision outcome in plain words, then explain using the conditions.\n"
             "- Never contradict or change the decision.\n"
             "- If the outcome is NEEDS_MORE_INFO, ask the user for the missing facts.")
    return block, rules


def generate_answer(question: str, chunks: list[dict], language: str, question_type: str,
                    decision: dict | None = None) -> dict:
    if decision:
        block, rules = _decision_text(decision)
    elif question_type == "eligibility":  # Python couldn't decide, so the model must not either
        block, rules = "", ("- Do NOT say whether the user is eligible or not. Explain the conditions from the "
                            "excerpts and say the user can check them against their own details.")
    else:
        block, rules = "", ""
    out: LLMAnswer = _generate(
        _prompt("answer.txt", language_name=LANGUAGE_NAMES[language], question_type=question_type,
                question=question, decision_block=block, decision_rules=rules, excerpts=format_excerpts(chunks)),
        LLMAnswer,
    )
    known = _known(chunks)
    used, seen = [], set()
    for s in out.used_sources:
        if (s.filename, s.page) in known and (s.filename, s.page) not in seen:
            seen.add((s.filename, s.page))
            used.append({"filename": s.filename, "page": s.page})
    return {"covered": bool(out.covered), "answer_text": out.answer_text.strip(), "used_sources": used}


# ---------- c) suggested questions for a document ----------
SUGGEST_INPUT_CHARS = 30_000


def suggest_questions(text: str) -> list[str]:
    """3 short English questions this document clearly answers. Never raises: failure -> []."""
    try:
        out: LLMSuggestions = _generate(_prompt("suggest.txt", text=text[:SUGGEST_INPUT_CHARS]), LLMSuggestions)
        return [q.strip() for q in out.questions if q.strip()][:3]
    except Exception as e:  # suggestions are optional; the document is still ready
        log.warning("Suggested questions failed: %s", type(e).__name__)
        return []
