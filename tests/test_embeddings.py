from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from google.genai import errors

from app.errors import AppError
from app.llm import embeddings


class FakeModels:
    def __init__(self, fail_times=0, code=503):
        self.calls, self.fail_times, self.code = [], fail_times, code

    def embed_content(self, model, contents, config):
        self.calls.append((model, list(contents), config))
        if len(self.calls) <= self.fail_times:
            raise errors.APIError(self.code, {"error": {"message": "boom"}})
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0] + [0.0] * 766) for _ in contents])


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(embeddings, "BACKOFF_SECONDS", 0)

    def install(**kw):
        m = FakeModels(**kw)
        monkeypatch.setattr(embeddings, "get_client", lambda: SimpleNamespace(models=m))
        return m

    return install


def test_batches_of_50_and_task_type(fake):
    m = fake()
    out = embeddings.embed_documents(["t"] * 120)
    assert len(out) == 120
    assert [len(c[1]) for c in m.calls] == [50, 50, 20]
    assert all(c[2].task_type == "RETRIEVAL_DOCUMENT" and c[2].output_dimensionality == 768 for c in m.calls)


def test_query_task_type_and_normalized(fake):
    m = fake()
    v = embeddings.embed_query("q")
    assert m.calls[0][2].task_type == "RETRIEVAL_QUERY"
    assert len(v) == 768 and np.isclose(np.linalg.norm(v), 1.0)


def test_retries_twice_then_succeeds(fake):
    m = fake(fail_times=2)
    embeddings.embed_query("q")
    assert len(m.calls) == 3


@pytest.mark.parametrize("code", [429, 503])
def test_gives_up_with_503(fake, code):
    m = fake(fail_times=99, code=code)
    with pytest.raises(AppError) as e:
        embeddings.embed_query("q")
    assert (e.value.code, e.value.status) == ("llm_unavailable", 503)
    assert len(m.calls) == 3


def test_non_retryable_fails_fast(fake):
    m = fake(fail_times=99, code=400)
    with pytest.raises(AppError):
        embeddings.embed_query("q")
    assert len(m.calls) == 1


def test_timeout_is_retried():
    n = {"c": 0}

    def fn():
        n["c"] += 1
        raise httpx.ReadTimeout("slow")

    embeddings.BACKOFF_SECONDS = 0
    with pytest.raises(AppError):
        embeddings.call_with_retry(fn)
    assert n["c"] == 3


@pytest.mark.live
def test_live_gemini():
    from app.config import get_settings
    from app.llm.client import get_client

    v = embeddings.embed_query("merit scholarship eligibility")
    assert len(v) == 768 and np.isclose(np.linalg.norm(v), 1.0)
    reply = get_client().models.generate_content(model=get_settings().GEMINI_CHAT_MODEL, contents="Reply with OK")
    assert reply.text.strip()
