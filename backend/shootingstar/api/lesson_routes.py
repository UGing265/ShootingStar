"""API routes for lesson library: public approved catalog and protected admin review endpoints."""

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from shootingstar.adapters.db.repository import LessonRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.api.external_routes import verify_admin_authorization
from shootingstar.application.external_analysis.lessons import LessonService, LessonWorkflowError
from shootingstar.application.external_analysis.url_validator import SSRFValidationError

router = APIRouter(prefix="/lessons", tags=["Lessons"])


class CandidateLessonRequest(BaseModel):
    lesson_id: str
    title: str
    source_name: str
    source_url: str
    short_definition: str
    caveats: str
    source_snippet: Optional[str] = None


class ApproveLessonRequest(BaseModel):
    reason: Optional[str] = None


class RejectLessonRequest(BaseModel):
    reason: str = Field(..., description="Rejection reason is mandatory")


class NewRevisionRequest(BaseModel):
    short_definition: str
    caveats: str
    reason: Optional[str] = None
    source_snippet: Optional[str] = None


@router.get("", status_code=status.HTTP_200_OK)
def get_approved_lessons():
    """Public read endpoint: returns approved lessons with sanitized fields.

    INVARIANTS:
    1. Returns ONLY APPROVED lessons.
    2. Does NOT leak internal file paths, keys, or unapproved candidate data.
    """
    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        return service.get_approved_catalog()


@router.get("/admin/all")
def get_admin_lessons(
    status_filter: Optional[str] = Query(None, alias="status"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Admin endpoint: lists lessons with current revisions and review history."""
    verify_admin_authorization(x_admin_key)

    with get_db_session() as session:
        repo = LessonRepository(session)
        lessons = repo.list_lessons_by_status(status_filter.upper() if status_filter else None)
        result = []
        for l in lessons:
            rev = repo.get_revision(l.current_revision_id) if l.current_revision_id else None
            events = repo.list_review_events(l.id)
            result.append({
                "id": l.id,
                "title": l.title,
                "source_name": l.source_name,
                "source_url": l.source_url,
                "status": l.status,
                "current_revision": {
                    "id": rev.id,
                    "revision_number": rev.revision_number,
                    "short_definition": rev.short_definition,
                    "caveats": rev.caveats,
                    "source_snippet": rev.source_snippet,
                    "reviewer": rev.reviewer,
                    "created_at": rev.created_at.isoformat(),
                } if rev else None,
                "review_events": [
                    {
                        "action": e.action,
                        "reviewer": e.reviewer,
                        "reason": e.reason,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in events
                ],
            })
        return result


@router.post("/admin/candidate", status_code=status.HTTP_201_CREATED)
def submit_candidate_lesson(
    req: CandidateLessonRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Admin endpoint: submits candidate lesson for human review with SSRF validation."""
    verify_admin_authorization(x_admin_key)

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        try:
            lesson = service.submit_candidate(
                lesson_id=req.lesson_id,
                title=req.title,
                source_name=req.source_name,
                source_url=req.source_url,
                short_definition=req.short_definition,
                caveats=req.caveats,
                source_snippet=req.source_snippet,
                submitter="admin_operator",
            )
            session.commit()
            return {"status": "SUCCESS", "lesson_id": lesson.id, "lesson_status": lesson.status}
        except (SSRFValidationError, LessonWorkflowError) as e:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/{lesson_id}/approve")
def approve_lesson_endpoint(
    lesson_id: str,
    req: ApproveLessonRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Admin endpoint: approves pending lesson."""
    verify_admin_authorization(x_admin_key)

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        try:
            lesson = service.approve_lesson(lesson_id, reviewer="admin_operator", reason=req.reason)
            session.commit()
            return {"status": "SUCCESS", "lesson_id": lesson.id, "lesson_status": lesson.status}
        except LessonWorkflowError as e:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/{lesson_id}/reject")
def reject_lesson_endpoint(
    lesson_id: str,
    req: RejectLessonRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Admin endpoint: rejects lesson."""
    verify_admin_authorization(x_admin_key)

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        try:
            lesson = service.reject_lesson(lesson_id, reviewer="admin_operator", reason=req.reason)
            session.commit()
            return {"status": "SUCCESS", "lesson_id": lesson.id, "lesson_status": lesson.status}
        except LessonWorkflowError as e:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/{lesson_id}/revision")
def create_lesson_revision_endpoint(
    lesson_id: str,
    req: NewRevisionRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Admin endpoint: edits definition/caveats and creates new approved revision."""
    verify_admin_authorization(x_admin_key)

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        try:
            lesson = service.edit_and_approve_revision(
                lesson_id=lesson_id,
                short_definition=req.short_definition,
                caveats=req.caveats,
                reviewer="admin_operator",
                reason=req.reason,
                source_snippet=req.source_snippet,
            )
            session.commit()
            return {"status": "SUCCESS", "lesson_id": lesson.id, "current_revision_id": lesson.current_revision_id}
        except LessonWorkflowError as e:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(e))
