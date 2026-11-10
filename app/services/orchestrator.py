"""POST /api/ask pipeline: language -> classifier -> retrieval -> gate -> decision -> answer."""
import logging
import time

from sqlalchemy.orm import Session

from app.errors import AppError
from app.llm import generate
from app.models import QuestionLog
from app.services import retrieval
from app.system1 import answerability, classifier, language as lang
from app.system1.decisions import engine

log = logging.getLogger("knowpilot.ask")

NO_ANSWER = {
    "en": "I couldn't find an answer to this in the uploaded documents. Please contact the office for help.",
    "hi": "मुझे अपलोड किए गए दस्तावेज़ों में इसका उत्तर नहीं मिला। कृपया सहायता के लिए कार्यालय से संपर्क करें।",
    "hinglish": "Mujhe uploaded documents mein iska jawab nahi mila. Kripya madad ke liye office se sampark karein.",
}
BUSY = "The AI service is busy; here are the most relevant passages:"
SNIPPET = 220


class Trace:
    def __init__(self):
        self.steps, self._t = [], time.perf_counter()

    def add(self, step: str, kind: str):
        now = time.perf_counter()
        self.steps.append({"step": step, "kind": kind, "ms": round((now - self._t) * 1000, 1)})
        self._t = now


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

    chunks = retrieval.retrieve(db, org_id, question)
    trace.add("retrieval", "retrieval")
    gate = answerability.is_answerable(chunks)
    trace.add("answerability_gate", "system1")

    decision, references = None, []
    if qtype == "out_of_scope" or not gate["answerable"]:
        status, answer = "no_answer", NO_ANSWER[language]
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
            status, answer = "answered", out["answer_text"]
            references = [_reference(chunks, s["filename"], s["page"]) for s in out["used_sources"]]
        except AppError:
            trace.add("generate_answer_failed", "fallback")
            pages = list(dict.fromkeys((c["filename"], c["page_number"]) for c in chunks))[:3]
            references = [_reference(chunks, f, p) for f, p in pages]
            status = "passages_only"
            answer = BUSY + "\n\n" + "\n\n".join(
                f"{r['filename']} — Page {r['page']}: {r['snippet']}" for r in references)

    decision_out = _decision_out(decision) if decision else None
    db.add(QuestionLog(  # no question text, no personal facts
        org_id=org_id, language=language, question_type=qtype, status=status,
        decision=decision_out["outcome"] if decision_out else None,
        latency_ms=int((time.perf_counter() - started) * 1000),
    ))
    db.commit()
    return {"status": status, "answer": answer, "language": language, "question_type": qtype,
            "references": references, "decision": decision_out, "trace": trace.steps}
