# KnowPilot Backend

FastAPI backend for KnowPilot, a multi-tenant AI knowledge & decision assistant for Indian organizations.

Frontend: [knowpilot-frontend](#) <!-- TODO: add repo link -->

## Run

```
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then fill in the values
python scripts/setup_db.py      # applies db/schema.sql
uvicorn app.main:app --reload --port 8000
pytest
```

Health check: http://localhost:8000/api/health

On Render, start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Don't add `--forwarded-allow-ips="*"`: the rate limiter reads the client IP itself from the
rightmost `X-Forwarded-For` entry (the one Render's proxy appends, which visitors can't forge).
