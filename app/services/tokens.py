import secrets
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import AssistantToken, Organization

MAX_TOKEN_LENGTH = 100


def _invalid() -> AppError:
    return AppError("invalid_token", "This assistant link is not active.", 404)


def resolve_assistant_token(token: str, db: Session) -> uuid.UUID:
    """Public assistant token -> org_id. Unknown, inactive or oversized tokens -> 404."""
    if not token or len(token) > MAX_TOKEN_LENGTH:
        raise _invalid()
    org_id = db.scalar(
        select(AssistantToken.org_id).where(AssistantToken.token == token, AssistantToken.is_active)
    )
    if org_id is None:
        raise _invalid()
    return org_id


def active_token(db: Session, org_id) -> AssistantToken:
    tok = db.scalar(select(AssistantToken).where(AssistantToken.org_id == org_id, AssistantToken.is_active))
    return tok or regenerate(db, org_id)


def regenerate(db: Session, org_id) -> AssistantToken:
    """Revoke the active token and issue a new one, in one transaction."""
    # Lock the org row so concurrent regenerations run one after the other.
    db.execute(select(Organization.id).where(Organization.id == org_id).with_for_update())
    db.execute(
        update(AssistantToken)
        .where(AssistantToken.org_id == org_id, AssistantToken.is_active)
        .values(is_active=False, revoked_at=func.now())
    )
    tok = AssistantToken(org_id=org_id, token=secrets.token_urlsafe(32), is_active=True)
    db.add(tok)
    db.commit()
    db.refresh(tok)
    return tok
