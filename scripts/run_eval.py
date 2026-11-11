"""Run sample-data/test_questions.json against a live API and write docs/eval_results.md.

    python scripts/run_eval.py [base_url]        (default http://localhost:8000)
    python scripts/run_eval.py --md              (only regenerate sample-data/test_questions.md)

Logs in as the two seeded demo admins (see sample-data/README.md) to look up their assistant tokens.
"""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "sample-data" / "test_questions.json"
ADMINS = {"org1": "admin@navodaya.test", "org2": "hr@navyug.test"}
PASSWORD = "Demo@12345"


def token(c: httpx.Client, email: str) -> str:
    jwt = c.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return c.get("/api/assistant", headers={"Authorization": f"Bearer {jwt}"}).json()["token"]


def ask(c: httpx.Client, tok: str, q: str) -> dict:
    for _ in range(4):
        r = c.post("/api/ask", json={"assistant_token": tok, "question": q})
        if r.status_code != 429:
            return r.json()
        time.sleep(30)
    return {"status": "rate_limited"}


def write_md() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    lines = ["# Test questions", "",
             "14 questions across both sample organizations (org1 = Navodaya Institute of Technology, "
             "org2 = Navyug Infotech). Machine-readable copy: `test_questions.json`; "
             "run them with `python scripts/run_eval.py`.", "",
             "| # | Org | Category | Question | Status | Type | Outcome | Reference |",
             "|---|---|---|---|---|---|---|---|"]
    for t in cases:
        lines.append(f"| {t['id']} | {t['org']} | {t['category']} | {t['question']} | {t['status']} | "
                     f"{t['question_type'] or 'any'} | {t['outcome'] or '-'} | {t['reference'] or '-'} |")
    lines += ["", "Cross-tenant rows (11, 12) ask one org about the other org's data and must return "
              "`no_answer` with no references."]
    (ROOT / "sample-data" / "test_questions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if "--md" in sys.argv:
        return write_md()
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    rows, passed = [], 0
    with httpx.Client(base_url=base, timeout=120) as c:
        tokens = {k: token(c, e) for k, e in ADMINS.items()}
        for t in cases:
            r = ask(c, tokens[t["org"]], t["question"])
            files = [x["filename"] for x in r.get("references", [])]
            checks = {
                "status": r.get("status") == t["status"],
                "type": t["question_type"] is None or r.get("question_type") == t["question_type"],
                "outcome": t["outcome"] is None or (r.get("decision") or {}).get("outcome") == t["outcome"],
                "ref": t["reference"] is None or t["reference"] in files,
                "lang": t.get("language") is None or r.get("language") == t["language"],
            }
            ok = all(checks.values())
            passed += ok
            rows.append((t, r, files, ok, [k for k, v in checks.items() if not v]))
            time.sleep(4)  # stay under the 20 requests/min per-IP limit
    out = [f"# Evaluation results\n\nRun against `{base}` on {time.strftime('%Y-%m-%d')}. "
           f"**{passed}/{len(cases)} passed.**\n",
           "| # | Category | Expected (status / type / outcome / ref) | Got (status / type / outcome / refs) | Result |",
           "|---|---|---|---|---|"]
    for t, r, files, ok, bad in rows:
        exp = f"{t['status']} / {t['question_type'] or '-'} / {t['outcome'] or '-'} / {t['reference'] or '-'}"
        got = (f"{r.get('status')} / {r.get('question_type')} / {(r.get('decision') or {}).get('outcome') or '-'} / "
               f"{', '.join(dict.fromkeys(files)) or '-'}")
        out.append(f"| {t['id']} | {t['category']} | {exp} | {got} | {'PASS' if ok else 'FAIL (' + ', '.join(bad) + ')'} |")
    (ROOT / "docs" / "eval_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
