"""Unit and integration tests for lesson library, SSRF validator, and admin review routes."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from shootingstar.adapters.db.models import (
    LessonModel,
    LessonReviewEventModel,
    LessonRevisionModel,
)
from shootingstar.adapters.db.repository import LessonRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.api.app import app
from shootingstar.application.external_analysis.lessons import LessonService, LessonWorkflowError
from shootingstar.application.external_analysis.url_validator import (
    SSRFValidationError,
    validate_public_https_url,
)


# 1. SSRF Validator Tests
def test_ssrf_validator_blocks_internal_and_insecure_destinations():
    # Valid public HTTPS passes
    assert validate_public_https_url("https://en.wikipedia.org/wiki/Double_top_and_double_bottom")

    # Non-https rejected
    with pytest.raises(SSRFValidationError, match="Only 'https' is permitted"):
        validate_public_https_url("http://example.com")

    # Non-standard port rejected
    with pytest.raises(SSRFValidationError, match="Port 8080 is not allowed"):
        validate_public_https_url("https://example.com:8080/lesson")

    # Loopback IP rejected
    with pytest.raises(SSRFValidationError, match="loopback"):
        validate_public_https_url("https://127.0.0.1/test")

    # Private IP rejected
    with pytest.raises(SSRFValidationError, match="private network"):
        validate_public_https_url("https://192.168.1.10/test")

    # Metadata IP rejected
    with pytest.raises(SSRFValidationError, match="link-local/cloud metadata"):
        validate_public_https_url("https://169.254.169.254/latest/meta-data")

    # Localhost rejected
    with pytest.raises(SSRFValidationError, match="forbidden"):
        validate_public_https_url("https://localhost/admin")


# 2. Lesson Lifecycle and Revisions Tests
def test_lesson_lifecycle_and_revisions(migrated_test_engine):
    test_id = f"test_lesson_{uuid.uuid4().hex[:8]}"

    try:
        with get_db_session() as session:
            repo = LessonRepository(session)
            service = LessonService(repo)

            # 1. Submit candidate
            lesson = service.submit_candidate(
                lesson_id=test_id,
                title="Double Bottom Pattern",
                source_name="Trading Guide",
                source_url="https://en.wikipedia.org/wiki/Double_top_and_double_bottom",
                short_definition="Bullish reversal pattern with two distinct lows.",
                caveats="High false breakout rate in choppy market.",
                source_snippet="A double bottom is a charting pattern...",
            )
            session.commit()

            assert lesson.status == "PENDING"
            assert lesson.current_revision_id is not None

            # Verify revision 1 created
            rev1 = repo.get_revision(lesson.current_revision_id)
            assert rev1.revision_number == 1
            assert rev1.short_definition == "Bullish reversal pattern with two distinct lows."

            # Verify review event
            events = repo.list_review_events(test_id)
            assert len(events) == 1
            assert events[0].action == "SUBMITTED"

            # 2. Approve lesson
            lesson_approved = service.approve_lesson(test_id, reviewer="reviewer_bob")
            session.commit()
            assert lesson_approved.status == "APPROVED"

            events = repo.list_review_events(test_id)
            assert len(events) == 2
            assert events[0].action == "APPROVED"

            # 3. Edit and approve revision 2
            lesson_rev2 = service.edit_and_approve_revision(
                lesson_id=test_id,
                short_definition="Refined: Bullish reversal confirmed on neckline breakout.",
                caveats="Must watch volume expansion on breakout.",
                reviewer="reviewer_alice",
                reason="Improved definition accuracy",
            )
            session.commit()

            rev2 = repo.get_revision(lesson_rev2.current_revision_id)
            assert rev2.revision_number == 2
            assert "Refined" in rev2.short_definition

            # 4. Catalog extraction
            catalog = service.get_approved_catalog()
            matching = [l for l in catalog if l["id"] == test_id]
            assert len(matching) == 1
            assert matching[0]["revision_number"] == 2
            assert matching[0]["source_url"] == "https://en.wikipedia.org/wiki/Double_top_and_double_bottom"

    finally:
        with get_db_session() as s:
            s.execute(delete(LessonReviewEventModel).where(LessonReviewEventModel.lesson_id == test_id))
            s.execute(delete(LessonRevisionModel).where(LessonRevisionModel.lesson_id == test_id))
            s.execute(delete(LessonModel).where(LessonModel.id == test_id))
            s.commit()


# 3. Lesson API Routes Security Tests
def test_lesson_api_routes(monkeypatch):
    client = TestClient(app)

    # 1. Public read /lessons succeeds without any auth
    res_public = client.get("/lessons")
    assert res_public.status_code == 200
    assert isinstance(res_public.json(), list)

    # 2. Admin read /lessons/admin/all without auth or external api flag -> fail closed
    monkeypatch.delenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", raising=False)
    res_unauth = client.get("/lessons/admin/all")
    assert res_unauth.status_code == 503

    # 3. With external enabled but wrong key -> 403 Forbidden
    monkeypatch.setenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "true")
    monkeypatch.setenv("SHOOTINGSTAR_ADMIN_KEY", "admin-secret-test")

    res_wrong_key = client.get("/lessons/admin/all", headers={"X-Admin-Key": "bad-key"})
    assert res_wrong_key.status_code == 403

    # 4. With valid admin key -> 200 OK
    res_auth = client.get("/lessons/admin/all", headers={"X-Admin-Key": "admin-secret-test"})
    assert res_auth.status_code == 200
    assert isinstance(res_auth.json(), list)
