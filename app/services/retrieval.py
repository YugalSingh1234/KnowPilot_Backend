"""Hybrid retrieval: pgvector cosine + Postgres full-text, merged with Reciprocal Rank Fusion.

Both SQL queries filter by org_id and only see documents with status 'ready'.
"""
import re
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.llm.embeddings import embed_query

RRF_K = 60
CANDIDATES = 24  # per search, before fusion

# Dropped from the keyword query so "is/the/kya/hai" don't count as a keyword match.
STOPWORDS = set(
    "a an the is are was were be been am i me my we our you your he she it its they them this that these those "
    "of in on at to for from by with and or not no do does did can could will would should shall may might "
    "what which who whom whose when where why how if then than so as about into over under after before "
    "kya hai hain ka ki ke ko se me mein mai main hoon hu ho tha thi the aur ya bhi to toh kaise kitna kitni "
    "kitne mera meri mere mujhe hum ham aap tum yeh ye woh wo kab kahan kyun kaun koi kuch par pe liye wala "
    "wali".split()
)

_SELECT = """
    select c.id, d.filename, c.page_number, c.content,
           1 - (c.embedding <=> cast(:qvec as vector))           as vector_score,
           coalesce(ts_rank_cd(c.tsv, q.query), 0)               as keyword_score
    from chunks c
    join documents d on d.id = c.document_id
    cross join (select to_tsquery('simple',
                  replace(websearch_to_tsquery('simple', :terms)::text, ' & ', ' | ')) as query) q
    where c.org_id = :org_id and d.org_id = :org_id and d.status = 'ready' and c.embedding is not null
"""
_VECTOR_SQL = text(_SELECT + " order by c.embedding <=> cast(:qvec as vector) limit :n")
_KEYWORD_SQL = text(_SELECT + " and c.tsv @@ q.query order by keyword_score desc limit :n")


def keyword_terms(query: str) -> str:
    words = [w for w in re.split(r"\s+", query) if w.strip(".,?!।:;'\"()").lower() not in STOPWORDS]
    return " ".join(words)


def retrieve(db: Session, org_id: uuid.UUID, query: str, k: int = 6) -> list[dict]:
    qvec = "[" + ",".join(f"{x:.7f}" for x in embed_query(query)) + "]"
    params = {"org_id": org_id, "qvec": qvec, "terms": keyword_terms(query), "n": CANDIDATES}
    vector_rows = db.execute(_VECTOR_SQL, params).mappings().all()
    keyword_rows = db.execute(_KEYWORD_SQL, params).mappings().all() if params["terms"] else []

    fused: dict = {}
    for rows in (vector_rows, keyword_rows):
        for rank, row in enumerate(rows, start=1):
            item = fused.setdefault(row["id"], {
                "chunk_id": str(row["id"]), "filename": row["filename"], "page_number": row["page_number"],
                "content": row["content"], "vector_score": round(float(row["vector_score"]), 4),
                "keyword_score": round(float(row["keyword_score"]), 4), "rrf_score": 0.0,
            })
            item["rrf_score"] += 1 / (RRF_K + rank)
    ranked = sorted(fused.values(), key=lambda c: c["rrf_score"], reverse=True)[:k]
    for c in ranked:
        c["rrf_score"] = round(c["rrf_score"], 5)
    return ranked
