"""Run db/schema.sql against DATABASE_URL, then list public tables."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
with psycopg.connect(url, autocommit=True) as conn:
    conn.execute((root / "db" / "schema.sql").read_text(encoding="utf-8"))
    rows = conn.execute(
        "select tablename, rowsecurity from pg_tables where schemaname='public' order by 1"
    ).fetchall()
for name, rls in rows:
    print(f"{name}  rls={rls}")
