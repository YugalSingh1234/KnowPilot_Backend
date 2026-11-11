"""GET / : a small human-readable status page. Counts only, never names or ids."""
import html
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import APP_VERSION, get_settings
from app.db import get_db
from app.models import Document, Organization

log = logging.getLogger("knowpilot.status")
router = APIRouter(include_in_schema=False)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KnowPilot API</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--text:#1d2433;--muted:#5d6779;--border:#e2e5eb;--accent:#1f5fbf;--ok:#1a7f37;--bad:#c62828}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1218;--card:#181c24;--text:#e6e9ef;--muted:#9aa3b2;--border:#2a303b;--accent:#6ea8ff;--ok:#4cc265;--bad:#ff6b6b}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;
background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{width:100%;max-width:440px;background:var(--card);border:1px solid var(--border);border-radius:14px;padding:28px}}
h1{{margin:0 0 4px;font-size:1.5rem}}.muted{{color:var(--muted);font-size:.9rem;margin:0 0 20px}}
.status{{display:flex;align-items:center;gap:10px;font-weight:600;margin-bottom:18px}}
.dot{{width:12px;height:12px;border-radius:50%;background:var({color})}}.status span{{color:var({color})}}
dl{{display:grid;grid-template-columns:1fr auto;gap:8px 16px;margin:0 0 24px}}dt{{color:var(--muted)}}dd{{margin:0;text-align:right;font-variant-numeric:tabular-nums}}
.buttons{{display:flex;gap:10px;flex-wrap:wrap}}a{{flex:1;text-align:center;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:600;border:1px solid var(--accent)}}
a.primary{{background:var(--accent);color:#fff}}a.secondary{{color:var(--accent)}}
</style></head>
<body><main>
<h1>KnowPilot API</h1>
<p class="muted">Backend for the KnowPilot knowledge assistant</p>
<div class="status"><div class="dot"></div><span>{status}</span></div>
<dl><dt>Version</dt><dd>{version}</dd><dt>Organizations</dt><dd>{orgs}</dd><dt>Documents</dt><dd>{docs}</dd></dl>
<div class="buttons"><a class="primary" href="/docs">API docs</a><a class="secondary" href="{frontend}">Open app</a></div>
</main></body></html>"""


@router.get("/", response_class=HTMLResponse)
def status_page(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        orgs = db.scalar(select(func.count()).select_from(Organization))
        docs = db.scalar(select(func.count()).select_from(Document))
        ok = True
    except Exception as e:  # the page must render even when the database is down
        log.warning("Status page: database check failed (%s)", type(e).__name__)
        ok, orgs, docs = False, "—", "—"
    origins = get_settings().frontend_origins
    return PAGE.format(
        color="--ok" if ok else "--bad",
        status="Running" if ok else "Database issue",
        version=html.escape(APP_VERSION),
        orgs=orgs, docs=docs,
        frontend=html.escape(origins[0] if origins else "#", quote=True),
    )
