import re

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import APP_VERSION, get_settings
from app.db import get_db
from app.errors import register_error_handlers
from app.routers import ask, assistant, auth, documents, status, usage

# Public (any origin): /api/ask and /api/assistant/{token}/info. Admin routes stay on FRONTEND_ORIGIN.
PUBLIC_PATH = re.compile(r"^/api/ask(/.*)?$|^/api/assistant/[^/]+/info$")


class SplitCORS:
    """Public routes allow any origin; everything else only FRONTEND_ORIGIN."""

    def __init__(self, app: ASGIApp):
        kw = dict(allow_methods=["*"], allow_headers=["*"])
        self.public = CORSMiddleware(app, allow_origins=["*"], **kw)
        self.private = CORSMiddleware(
            app, allow_origins=get_settings().frontend_origins, allow_credentials=True, **kw
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and PUBLIC_PATH.match(scope["path"]):
            return await self.public(scope, receive, send)
        return await self.private(scope, receive, send)


app = FastAPI(title="KnowPilot", version=APP_VERSION)
app.add_middleware(SplitCORS)
register_error_handlers(app)
for module in (auth, documents, assistant, ask, usage):
    app.include_router(module.router)
app.include_router(status.router)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
