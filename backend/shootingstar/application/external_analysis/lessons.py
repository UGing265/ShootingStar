"""Lesson management, review workflows, immutable revision history, and approved catalog."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shootingstar.adapters.db.models import (
    LessonModel,
    LessonReviewEventModel,
    LessonRevisionModel,
)
from shootingstar.adapters.db.repository import LessonRepository
from shootingstar.application.external_analysis.url_validator import (
    SSRFValidationError,
    validate_public_https_url,
)

logger = logging.getLogger(__name__)


class LessonWorkflowError(Exception):
    """Raised on invalid review actions or state transitions."""
    pass


class LessonService:
    """Orchestrates candidate submission, review approval/rejection, and revision immutability."""

    def __init__(self, repository: LessonRepository):
        self.repo = repository

    def submit_candidate(
        self,
        lesson_id: str,
        title: str,
        source_name: str,
        source_url: str,
        short_definition: str,
        caveats: str,
        source_snippet: Optional[str] = None,
        submitter: str = "research_agent",
    ) -> LessonModel:
        """Submits an unverified candidate lesson for human review.

        INVARIANTS:
        1. source_url MUST pass validate_public_https_url (strict SSRF prevention).
        2. Status is initialized to 'PENDING'.
        3. Revision 1 is created.
        4. Review event 'SUBMITTED' is recorded.
        """
        clean_url = validate_public_https_url(source_url)
        clean_id = lesson_id.strip()

        existing = self.repo.get_lesson(clean_id)
        if existing:
            raise LessonWorkflowError(f"Lesson with ID '{clean_id}' already exists.")

        now_dt = datetime.now(timezone.utc)
        rev_id = str(uuid.uuid4())

        lesson = LessonModel(
            id=clean_id,
            title=title.strip(),
            source_name=source_name.strip(),
            source_url=clean_url,
            status="PENDING",
            current_revision_id=rev_id,
            created_at=now_dt,
            updated_at=now_dt,
        )
        self.repo.save_lesson(lesson)

        revision = LessonRevisionModel(
            id=rev_id,
            lesson_id=clean_id,
            revision_number=1,
            short_definition=short_definition.strip(),
            caveats=caveats.strip(),
            source_snippet=source_snippet.strip() if source_snippet else None,
            reviewer=None,
            created_at=now_dt,
        )
        self.repo.save_revision(revision)

        event = LessonReviewEventModel(
            id=str(uuid.uuid4()),
            lesson_id=clean_id,
            revision_id=rev_id,
            action="SUBMITTED",
            reviewer=submitter,
            reason="Automated discovery submitted for operator verification",
            created_at=now_dt,
        )
        self.repo.save_review_event(event)

        return lesson

    def approve_lesson(self, lesson_id: str, reviewer: str, reason: Optional[str] = None) -> LessonModel:
        """Approves a pending lesson, making its current revision available for context injection."""
        lesson = self.repo.get_lesson(lesson_id)
        if not lesson:
            raise LessonWorkflowError(f"Lesson '{lesson_id}' not found.")

        now_dt = datetime.now(timezone.utc)
        lesson.status = "APPROVED"
        lesson.updated_at = now_dt
        self.repo.save_lesson(lesson)

        event = LessonReviewEventModel(
            id=str(uuid.uuid4()),
            lesson_id=lesson.id,
            revision_id=lesson.current_revision_id,
            action="APPROVED",
            reviewer=reviewer,
            reason=reason or "Operator approved lesson definition and caveats",
            created_at=now_dt,
        )
        self.repo.save_review_event(event)
        return lesson

    def reject_lesson(self, lesson_id: str, reviewer: str, reason: str) -> LessonModel:
        """Rejects a lesson."""
        if not reason or not reason.strip():
            raise LessonWorkflowError("Rejection requires an explicit reason.")

        lesson = self.repo.get_lesson(lesson_id)
        if not lesson:
            raise LessonWorkflowError(f"Lesson '{lesson_id}' not found.")

        now_dt = datetime.now(timezone.utc)
        lesson.status = "REJECTED"
        lesson.updated_at = now_dt
        self.repo.save_lesson(lesson)

        event = LessonReviewEventModel(
            id=str(uuid.uuid4()),
            lesson_id=lesson.id,
            revision_id=lesson.current_revision_id,
            action="REJECTED",
            reviewer=reviewer,
            reason=reason.strip(),
            created_at=now_dt,
        )
        self.repo.save_review_event(event)
        return lesson

    def edit_and_approve_revision(
        self,
        lesson_id: str,
        short_definition: str,
        caveats: str,
        reviewer: str,
        reason: Optional[str] = None,
        source_snippet: Optional[str] = None,
    ) -> LessonModel:
        """Creates an updated immutable revision and sets status to APPROVED."""
        lesson = self.repo.get_lesson(lesson_id)
        if not lesson:
            raise LessonWorkflowError(f"Lesson '{lesson_id}' not found.")

        revisions = self.repo.list_revisions_for_lesson(lesson_id)
        next_rev_num = (revisions[0].revision_number + 1) if revisions else 1

        now_dt = datetime.now(timezone.utc)
        new_rev_id = str(uuid.uuid4())

        new_revision = LessonRevisionModel(
            id=new_rev_id,
            lesson_id=lesson_id,
            revision_number=next_rev_num,
            short_definition=short_definition.strip(),
            caveats=caveats.strip(),
            source_snippet=source_snippet.strip() if source_snippet else None,
            reviewer=reviewer,
            created_at=now_dt,
        )
        self.repo.save_revision(new_revision)

        lesson.current_revision_id = new_rev_id
        lesson.status = "APPROVED"
        lesson.updated_at = now_dt
        self.repo.save_lesson(lesson)

        event = LessonReviewEventModel(
            id=str(uuid.uuid4()),
            lesson_id=lesson_id,
            revision_id=new_rev_id,
            action="EDITED",
            reviewer=reviewer,
            reason=reason or "Operator edited definitions/caveats and approved revision",
            created_at=now_dt,
        )
        self.repo.save_review_event(event)
        return lesson

    def get_approved_catalog(self) -> List[Dict[str, Any]]:
        """Extracts all APPROVED lessons with their current immutable revision for model context."""
        approved_lessons = self.repo.list_lessons_by_status("APPROVED")
        catalog: List[Dict[str, Any]] = []

        for l in approved_lessons:
            if not l.current_revision_id:
                continue
            rev = self.repo.get_revision(l.current_revision_id)
            if not rev:
                continue

            catalog.append({
                "id": l.id,
                "title": l.title,
                "source_name": l.source_name,
                "source_url": l.source_url,
                "revision_id": rev.id,
                "revision_number": rev.revision_number,
                "short_definition": rev.short_definition,
                "caveats": rev.caveats,
            })

        return catalog
