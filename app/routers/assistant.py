import html
from itertools import zip_longest

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AssistantToken, Document, Organization
from app.security import get_current_org
from app.services import ratelimit, tokens

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _out(org: Organization, tok: AssistantToken) -> dict:
    url = f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/a/{tok.token}"
    title = html.escape(f"{org.name} Assistant", quote=True)
    embed = (
        f'<iframe src="{html.escape(url, quote=True)}" width="100%" height="600" '
        f'style="border:0;border-radius:12px" title="{title}" loading="lazy"></iframe>'
    )
    return {"assistant_url": url, "token": tok.token, "created_at": tok.created_at.isoformat(), "embed_code": embed}


@router.get("")
def get_assistant(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    return _out(org, tokens.active_token(db, org.id))


@router.post("/regenerate")
def regenerate(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    return _out(org, tokens.regenerate(db, org.id))


@router.get("/{token}/info")
def public_info(token: str, request: Request, db: Session = Depends(get_db)):
    ratelimit.check_ip(ratelimit.client_ip(request))
    org_id = tokens.resolve_assistant_token(token, db)
    ratelimit.check_token(token)
    name = db.scalar(select(Organization.name).where(Organization.id == org_id))
    per_doc = db.scalars(
        select(Document.suggested_questions)
        .where(Document.org_id == org_id, Document.status == "ready")
        .order_by(Document.created_at)
    ).all()
    return {"org_name": name, "suggested_questions": pick_suggestions(per_doc)}


def pick_suggestions(per_doc: list[list[str]], limit: int = 6) -> list[str]:
    """Round-robin across documents so one PDF can't fill every slot; no duplicates."""
    out: list[str] = []
    for round_ in zip_longest(*(q or [] for q in per_doc)):
        for q in round_:
            if q and q not in out and len(out) < limit:
                out.append(q)
    return out
