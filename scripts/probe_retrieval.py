"""Print the top retrieved chunks for an organization.

    python scripts/probe_retrieval.py admin@navodaya.test "merit scholarship income limit"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Organization  # noqa: E402
from app.services.retrieval import retrieve  # noqa: E402
from app.system1.answerability import is_answerable  # noqa: E402

if len(sys.argv) != 3:
    sys.exit(__doc__)
email, question = sys.argv[1].lower(), sys.argv[2]
with SessionLocal() as db:
    org = db.scalar(select(Organization).where(Organization.email == email))
    if org is None:
        sys.exit(f"No organization with email {email}")
    chunks = retrieve(db, org.id, question)

print(f"Org: {org.name}\nQuestion: {question}\n")
for i, c in enumerate(chunks, 1):
    print(f"#{i} {c['filename']} - Page {c['page_number']}  "
          f"vector={c['vector_score']:.3f} keyword={c['keyword_score']:.3f} rrf={c['rrf_score']:.4f}")
    print("   " + c["content"][:220].replace("\n", " ") + ("..." if len(c["content"]) > 220 else ""))
print("\nGate:", is_answerable(chunks))
