"""POST /api/ask pipeline: language -> classifier -> retrieval -> gate -> decision -> answer."""
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import db_retry
from app.errors import AppError
from app.llm import generate
from app.models import Organization, QuestionLog
from app.services import retrieval
from app.system1 import answerability, classifier, language as lang
from app.system1.decisions import engine

log = logging.getLogger("knowpilot.ask")

NO_ANSWER = {
    "en": "This isn't covered in {org}'s documents. Please contact the organization directly.",
    "hi": "यह जानकारी {org} के दस्तावेज़ों में नहीं है। कृपया सीधे संस्था से संपर्क करें।",
    "hinglish": "Yeh jaankari {org} ke documents mein nahi hai. Kripya seedhe organization se sampark karein.",
}
BUSY = "The AI service is busy; here are the most relevant passages:"
SNIPPET = 220


class Trace:
    def __init__(self):
        self.steps, self._t = [], time.perf_counter()

    def add(self, step: str, kind: str, summary: str | None = None):
        now = time.perf_counter()
        item = {"step": step, "kind": kind, "ms": round((now - self._t) * 1000, 1)}
        if summary:
            item["summary"] = summary
        self.steps.append(item)
        self._t = now


def retrieval_summary(chunks: list[dict]) -> str:
    """What retrieval found, for the Processing steps panel (never the question text)."""
    if not chunks:
        return "No matching passages"
    top = max(chunks, key=lambda c: c["vector_score"])
    return f"{len(chunks)} passages; top match {top['vector_score']:.2f} in {top['filename']} — Page {top['page_number']}"


def _reference(chunks: list[dict], filename: str, page: int) -> dict:
    content = next(c["content"] for c in chunks if c["filename"] == filename and c["page_number"] == page)
    return {"filename": filename, "page": page, "snippet": content[:SNIPPET] + ("…" if len(content) > SNIPPET else "")}


def _decision_out(result: dict) -> dict:
    return {
        "outcome": result["outcome"],
        "score": result["score"],
        "booleans": [{k: c[k] for k in ("label", "result", "user_value", "required_value", "source")}
                     for c in result["conditions"]],
        "missing_facts": result["missing_facts"],
        "timings": result["timings"],
    }


def ask(db: Session, org_id, question: str) -> dict:
    started = time.perf_counter()
    trace = Trace()
    language = lang.detect(question)
    trace.add("language", "system1")
    qtype = classifier.classify(question)["label"]
    trace.add("classifier", "system1")

    chunks = db_retry(db, lambda: retrieval.retrieve(db, org_id, question))
    trace.add("retrieval", "retrieval", retrieval_summary(chunks))
    gate = answerability.is_answerable(chunks)
    trace.add("answerability_gate", "system1")

    org_name = db_retry(db, lambda: db.scalar(select(Organization.name).where(Organization.id == org_id)))
    no_answer = NO_ANSWER[language].format(org=org_name)
    decision, references = None, []
    if qtype == "out_of_scope" or not gate["answerable"]:
        status, answer = "no_answer", no_answer
    else:
        if qtype == "eligibility":
            try:
                spec = generate.extract_decision_spec(question, chunks, language)
                trace.add("extract_decision_spec", "llm")
                decision = engine.run_sync(spec)
                trace.add("decision_engine", "system1")
            except AppError as e:
                trace.add(f"decision_skipped:{e.code}", "fallback")
            except Exception as e:  # engine never should, but an answer still beats an error
                log.warning("Decision step failed: %s", type(e).__name__)
                trace.add("decision_skipped:engine_error", "fallback")
        try:
            out = generate.generate_answer(question, chunks, language, qtype, decision)
            trace.add("generate_answer", "llm")
            if out["covered"]:
                status, answer = "answered", out["answer_text"]
                references = [_reference(chunks, s["filename"], s["page"]) for s in out["used_sources"]]
            else:
                status, answer = "no_answer", no_answer
        except AppError:
            trace.add("generate_answer_failed", "fallback")
            pages = list(dict.fromkeys((c["filename"], c["page_number"]) for c in chunks))[:3]
            references = [_reference(chunks, f, p) for f, p in pages]
            status = "passages_only"
            answer = BUSY + "\n\n" + "\n\n".join(
                f"{r['filename']} — Page {r['page']}: {r['snippet']}" for r in references)

    if status == "no_answer":  # don't reveal which document came closest to an unanswered question
        for step in trace.steps:
            if step["step"] == "retrieval" and chunks:
                step["summary"] = f"{len(chunks)} passages; best match {max(c['vector_score'] for c in chunks):.2f} (not enough)"
    decision_out = _decision_out(decision) if decision else None
    row = QuestionLog(  # no question text, no personal facts
        org_id=org_id, language=language, question_type=qtype, status=status,
        decision=decision_out["outcome"] if decision_out else None,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    db_retry(db, lambda: (db.add(row), db.commit()))
    return {"status": status, "answer": answer, "language": language, "question_type": qtype,
            "references": references, "decision": decision_out, "trace": trace.steps}
