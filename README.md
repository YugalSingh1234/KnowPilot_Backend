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

## Known limitations

- **Rate limiter is in-memory (use Redis in production).** Counters live in one process: they
  reset on restart and aren't shared across instances. Each store holds at most 50,000 live keys
  (IPs grouped by IPv4 address / IPv6 /64). When full, it refuses new keys (fail closed) rather
  than evicting live counters, so a botnet-scale flood from more than 50,000 distinct networks
  per minute would block new visitors while existing ones keep working. Evicting instead would
  let the same attacker reset their own limits. Moving the counters to Redis with TTLs removes
  both the capacity limit and the single-instance restriction.
