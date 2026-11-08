import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.models import Organization


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # e.g. password longer than bcrypt's 72 bytes
        return False


def create_access_token(org_id) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(org_id), "typ": "admin", "exp": exp}, s.JWT_SECRET, "HS256")


def _unauthorized(message: str = "Invalid or missing token.") -> AppError:
    return AppError("unauthorized", message, 401)


def get_current_org(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> Organization:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    try:
        claims = jwt.decode(
            token, get_settings().JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]}
        )
        if claims.get("typ") != "admin":
            raise _unauthorized()
        org = db.get(Organization, uuid.UUID(claims["sub"]))
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired.")
    except (jwt.InvalidTokenError, ValueError):
        raise _unauthorized()
    if org is None:
        raise _unauthorized()
    return org
