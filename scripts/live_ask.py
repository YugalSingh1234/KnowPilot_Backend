"""Ask the seeded Navodaya assistant a few questions in-process (real DB + Gemini).

    python scripts/live_ask.py [email] ["question" ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AssistantToken, Organization  # noqa: E402

QUESTIONS = [
    "What is the hostel fee for first year?",
    "I'm in 2nd year, CGPA 8.2, income 6.5 lakh, I already get UP post-matric scholarship. Am I eligible for merit-cum-means?",
    "mera CGPA 8.2 hai aur income 6 lakh hai, kya mujhe merit scholarship milegi?",
    "What is the JEE Main cutoff this year?",
]
email = sys.argv[1] if len(sys.argv) > 1 else "admin@navodaya.test"
questions = sys.argv[2:] or QUESTIONS
with SessionLocal() as db:
    token = db.scalar(select(AssistantToken.token).join(Organization, Organization.id == AssistantToken.org_id)
                      .where(Organization.email == email, AssistantToken.is_active))
client = TestClient(app)
for q in questions:
    r = client.post("/api/ask", json={"assistant_token": token, "question": q}).json()
    d = r.get("decision") or {}
    print(f"\nQ: {q}\n-> status={r.get('status')} type={r.get('question_type')} lang={r.get('language')} "
          f"outcome={d.get('outcome')} missing={d.get('missing_facts')}")
    for b in d.get("booleans", []):
        print(f"   {b['result']:8} {b['label']} (user={b['user_value']}, required={b['required_value']})")
    print("   answer:", (r.get("answer") or json.dumps(r))[:400].replace("\n", " "))
    print("   refs:", [f"{x['filename']} p{x['page']}" for x in r.get("references", [])])
    print("   trace:", [t["step"] for t in r.get("trace", [])])
