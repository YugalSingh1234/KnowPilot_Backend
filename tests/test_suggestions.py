from app.llm import generate
from app.routers.assistant import pick_suggestions
from app.services.orchestrator import NO_ANSWER, retrieval_summary


def test_pick_round_robins_dedupes_and_caps():
    docs = [["a1", "a2", "a3"], [], ["b1", "a1", "b3"], ["c1"]]
    assert pick_suggestions(docs) == ["a1", "b1", "c1", "a2", "a3", "b3"]
    assert pick_suggestions([]) == []


def test_suggest_questions_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("gemini down")
    monkeypatch.setattr(generate, "_generate", boom)
    assert generate.suggest_questions("some text") == []


def test_no_answer_names_the_org_in_each_language():
    for lang in ("en", "hi", "hinglish"):
        assert "Sunrise College" in NO_ANSWER[lang].format(org="Sunrise College")


def test_retrieval_summary_reports_top_match():
    chunks = [{"vector_score": 0.41, "filename": "a.pdf", "page_number": 2},
              {"vector_score": 0.83, "filename": "b.pdf", "page_number": 5}]
    assert retrieval_summary(chunks) == "2 passages; top match 0.83 in b.pdf — Page 5"
    assert retrieval_summary([]) == "No matching passages"
