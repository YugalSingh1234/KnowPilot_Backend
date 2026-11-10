from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, QuestionLog
from app.security import get_current_org

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
def usage(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    def counts(column) -> dict:
        rows = db.execute(
            select(column, func.count()).where(QuestionLog.org_id == org.id).group_by(column)
        ).all()
        return {(k or "unknown"): n for k, n in rows}

    by_status = counts(QuestionLog.status)
    return {
        "total_questions": sum(by_status.values()),
        "by_status": by_status,
        "by_question_type": counts(QuestionLog.question_type),
        "by_language": counts(QuestionLog.language),
    }
