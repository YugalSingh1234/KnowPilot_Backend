"""Seed the two demo organizations through the running API (default http://localhost:8000).

    python scripts/seed_demo.py [base_url]

Registers each org (or logs in if it already exists), uploads its PDFs from sample-data/orgN/
(skipping files already uploaded) and prints the assistant URL.
"""
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PASSWORD = "Demo@12345"
ORGS = [
    ("Navodaya Institute of Technology", "admin@navodaya.test", "org1"),
    ("Navyug Infotech Pvt. Ltd.", "hr@navyug.test", "org2"),
]


def login(client: httpx.Client, name: str, email: str) -> str:
    r = client.post("/api/auth/register", json={"org_name": name, "email": email, "password": PASSWORD})
    if r.status_code == 201:
        print("  registered")
    elif r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        print("  already registered, logged in")
    else:
        sys.exit(f"  register failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=180) as client:
        try:
            client.get("/api/health").raise_for_status()
        except httpx.HTTPError as e:
            sys.exit(f"API not reachable at {BASE_URL} ({e}). Start it with: uvicorn app.main:app --port 8000")
        for name, email, folder in ORGS:
            print(f"\n{name} <{email}>")
            client.headers["Authorization"] = f"Bearer {login(client, name, email)}"
            existing = {d["filename"] for d in client.get("/api/documents").json()["documents"]}
            for pdf in sorted((ROOT / "sample-data" / folder).glob("*.pdf")):
                if pdf.name in existing:
                    print(f"  skip      {pdf.name} (already uploaded)")
                    continue
                r = client.post("/api/documents", files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")})
                if r.status_code == 201:
                    print(f"  uploaded  {pdf.name}: {r.json()['page_count']} pages, {r.json()['chunk_count']} chunks")
                else:
                    print(f"  FAILED    {pdf.name}: {r.status_code} {r.json().get('error')}")
            print(f"  assistant {client.get('/api/assistant').json()['assistant_url']}")
            del client.headers["Authorization"]


if __name__ == "__main__":
    main()
