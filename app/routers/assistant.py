import html

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AssistantToken, Organization
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
    ratelimit.check(token, request.client.host if request.client else "unknown")
    org_id = tokens.resolve_assistant_token(token, db)
    name = db.scalar(select(Organization.name).where(Organization.id == org_id))
    return {"org_name": name, "suggested_questions": []}
