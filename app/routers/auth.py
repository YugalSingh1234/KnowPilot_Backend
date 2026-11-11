import logging
import secrets
import time

import email_validator
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import AssistantToken, Organization
from app.security import create_access_token, get_current_org, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("knowpilot.auth")

# Allow the reserved ".test" TLD so demo accounts (admin@navodaya.test) can't collide with real domains.
if "test" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")


class RegisterIn(BaseModel):
    org_name: Annotated[str, Field(min_length=2, max_length=100)]
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("password must be at most 72 bytes")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _org_out(org: Organization) -> dict:
    return {"id": str(org.id), "name": org.name, "email": org.email}


def _auth_out(org: Organization) -> dict:
    return {"access_token": create_access_token(org.id), "org": _org_out(org)}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    exists = AppError("email_exists", "This email is already registered.", 409)
    if db.scalar(select(Organization.id).where(Organization.email == email)):
        raise exists
    org = Organization(name=body.org_name.strip(), email=email, password_hash=hash_password(body.password))
    try:
        db.add(org)
        db.flush()  # org.id for the token row
        db.add(AssistantToken(org_id=org.id, token=secrets.token_urlsafe(32), is_active=True))
        db.commit()  # org + first token in one transaction
    except IntegrityError:  # lost a race on the unique email
        db.rollback()
        raise exists
    return _auth_out(org)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    org = db.scalar(select(Organization).where(Organization.email == body.email.lower()))
    t1 = time.perf_counter()
    ok = org is not None and verify_password(body.password, org.password_hash)
    t2 = time.perf_counter()
    log.info("login timing db=%.0fms bcrypt=%.0fms total=%.0fms", (t1 - t0) * 1000, (t2 - t1) * 1000, (t2 - t0) * 1000)
    if not ok:
        raise AppError("invalid_credentials", "Invalid email or password.", 401)
    return _auth_out(org)


@router.get("/me")
def me(org: Organization = Depends(get_current_org)):
    return _org_out(org)
