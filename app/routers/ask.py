from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import orchestrator, ratelimit, tokens

router = APIRouter(prefix="/api", tags=["ask"])


class AskIn(BaseModel):
    assistant_token: Annotated[str, Field(min_length=1, max_length=200)]
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


@router.post("/ask")
def ask(body: AskIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check_ip(ratelimit.client_ip(request))
    org_id = tokens.resolve_assistant_token(body.assistant_token, db)
    ratelimit.check_token(body.assistant_token)
    return orchestrator.ask(db, org_id, body.question)
