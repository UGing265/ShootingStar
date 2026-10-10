"""Tests for Research Agent: literature catalogue search, model pattern inspection, and evidence verification."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from shootingstar.adapters.db.repository import LessonRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
from shootingstar.api.app import app
from shootingstar.application.external_analysis.lessons import LessonService
from shootingstar.application.external_analysis.research_agent import DocumentMatch, ResearchAgent


def test_catalogue_search_with_authentic_provenance(tmp_path: Path):
    """Verifies that catalogue search extracts sections with explicit authentic provenance and skips unverified files."""
    cat_dir = tmp_path / "literature"
    cat_dir.mkdir()

    # 1. File with explicit authentic provenance (arXiv academic research paper)
    doc1 = cat_dir / "patterns.md"
    doc1.write_text(
        "# Empirical Market Microstructure Formations\n\n"
        "## Double Bottom Reversal\n"
        "Source: Empirical Market Dynamics Research Paper\n"
        "Source URL: https://arxiv.org/abs/cond-mat/0202388\n\n"
        "A double bottom is a reversal chart pattern with two distinct troughs at similar support.\n"
        "Caveats: Volume must expand on the neckline breakout to avoid bull traps.\n",
        encoding="utf-8",
    )

    # 2. File without explicit Source URL (must be skipped, no fake fallbacks)
    doc2 = cat_dir / "unverified.md"
    doc2.write_text(
        "# Random Notes\n\n"
        "## Double Bottom Rumor\n"
        "Just some informal trading notes without URL.\n",
        encoding="utf-8",
    )

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        agent = ResearchAgent(service, catalogue_dir=cat_dir)

        # Search for Double Bottom
        matches = agent.search_catalogue("Double Bottom")
        assert len(matches) == 1
        assert matches[0].source_name == "Empirical Market Dynamics Research Paper"
        assert matches[0].source_url == "https://arxiv.org/abs/cond-mat/0202388"
        assert "distinct troughs" in matches[0].excerpt

        # Search for non-existent pattern in non-empty catalogue -> returns empty matches list
        no_matches = agent.search_catalogue("Fibonacci Crab")
        assert len(no_matches) == 0


def test_orchestrate_research_empty_catalogue(tmp_path: Path):
    """Verifies that an empty catalogue returns status EMPTY_CATALOGUE, distinct from NO_MATCH."""
    empty_dir = tmp_path / "empty_lit"
    empty_dir.mkdir()

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        agent = ResearchAgent(service, catalogue_dir=empty_dir)

        result = agent.orchestrate_research(pattern_query="Double Bottom", mock_mode=True)
        assert result["status"] == "EMPTY_CATALOGUE"
        assert result["matches_found"] == 0
        assert "0 tài liệu" in result["message"]


def test_orchestrate_research_mock_mode_no_database_persistence(tmp_path: Path):
    """Verifies that in mock_mode, extracted candidate preview is returned without writing to DB."""
    cat_dir = tmp_path / "literature"
    cat_dir.mkdir()

    doc = cat_dir / "patterns.md"
    doc.write_text(
        "## Bullish Engulfing Pattern\n"
        "Source: Quantitative Candlestick Studies\n"
        "Source URL: https://arxiv.org/abs/2004.09507\n\n"
        "A bullish engulfing pattern occurs when a large green candle body completely covers the previous red candle body.\n",
        encoding="utf-8",
    )

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        agent = ResearchAgent(service, catalogue_dir=cat_dir)

        result = agent.orchestrate_research(pattern_query="Bullish Engulfing", mock_mode=True)
        assert result["status"] == "COMPLETED"
        assert result["matches_found"] == 1
        assert result["candidates_count"] == 1
        candidate = result["candidates"][0]
        assert candidate["status"] == "MOCK_VERIFIED"
        assert candidate["persisted"] is False
        assert candidate["lesson_id"] == "bullish_engulfing"
        # Invariant: source_snippet must be a literal substring of the source excerpt
        assert candidate["source_snippet"] in doc.read_text(encoding="utf-8")

        # Invariant: DB must NOT contain this mock candidate
        db_lesson = repo.get_lesson("bullish_engulfing")
        assert db_lesson is None


def test_evidence_verification_rejects_hallucinated_snippets_live_mode(tmp_path: Path):
    """Verifies fail-closed gating: rejects candidates whose source_snippet is not in the source document in live mode."""
    cat_dir = tmp_path / "literature"
    cat_dir.mkdir()

    doc = cat_dir / "patterns.md"
    doc.write_text(
        "## Hammer Pattern\n"
        "Source: Technical Pattern Analysis on High Frequency Data\n"
        "Source URL: https://arxiv.org/abs/1904.05312\n\n"
        "A hammer candle shows buyers rejecting lower prices with a long lower shadow.\n",
        encoding="utf-8",
    )

    class MockHallucinatingAdapter(GeminiModelAdapter):
        def extract_lessons_from_text(self, **kwargs):
            return [
                {
                    "lesson_id": "hammer",
                    "title": "Hammer Pattern",
                    "short_definition": "Định nghĩa nến búa.",
                    "caveats": "Cần nến xác nhận.",
                    "source_snippet": "This exact sentence was never written in the input document!",
                }
            ]

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        agent = ResearchAgent(service, model_adapter=MockHallucinatingAdapter(), catalogue_dir=cat_dir)

        result = agent.orchestrate_research(pattern_query="Hammer", mock_mode=False)
        assert result["candidates_count"] == 0
        assert result["rejected_count"] == 1
        assert "Hallucinated evidence" in result["rejected"][0]["reason"]


def test_evidence_verification_rejects_hallucinated_snippets_in_mock_mode(tmp_path: Path):
    """Verifies that mock mode also strictly rejects candidates whose source_snippet is hallucinated."""
    cat_dir = tmp_path / "literature"
    cat_dir.mkdir()

    doc = cat_dir / "patterns.md"
    doc.write_text(
        "## Shooting Star Pattern\n"
        "Source: Statistical Properties of Reversal Signals\n"
        "Source URL: https://arxiv.org/abs/1806.01347\n\n"
        "A shooting star is a bearish candlestick with a long upper shadow and little or no lower shadow.\n",
        encoding="utf-8",
    )

    class MockHallucinatingAdapter(GeminiModelAdapter):
        def extract_lessons_from_text(self, **kwargs):
            return [
                {
                    "lesson_id": "shooting_star",
                    "title": "Shooting Star Pattern",
                    "short_definition": "Định nghĩa nến bắn sao.",
                    "caveats": "Cần nến xác nhận hôm sau.",
                    "source_snippet": "This sentence was hallucinated and never appears in the literature file.",
                }
            ]

    with get_db_session() as session:
        repo = LessonRepository(session)
        service = LessonService(repo)
        agent = ResearchAgent(service, model_adapter=MockHallucinatingAdapter(), catalogue_dir=cat_dir)

        result = agent.orchestrate_research(pattern_query="Shooting Star", mock_mode=True)
        assert result["candidates_count"] == 0
        assert result["rejected_count"] == 1
        assert "Hallucinated evidence" in result["rejected"][0]["reason"]


def test_research_admin_api_endpoint(db_session, monkeypatch):
    """Verifies POST /lessons/admin/research endpoint requires admin key, and mock requests rollback without persisting."""
    monkeypatch.setenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "true")
    monkeypatch.setenv("SHOOTINGSTAR_ADMIN_KEY", "test-admin-secret")
    client = TestClient(app)

    # 1. Unauthenticated request blocked with 403
    res_unauth = client.post("/lessons/admin/research", json={"pattern_query": "Double Bottom"})
    assert res_unauth.status_code == 403

    # 2. Authenticated request succeeds in mock mode
    res_auth = client.post(
        "/lessons/admin/research",
        headers={"X-Admin-Key": "test-admin-secret"},
        json={"pattern_query": "Double Bottom", "mock_mode": True},
    )
    assert res_auth.status_code == 200
    data = res_auth.json()
    assert "status" in data

    # 3. Invariant: DB contains 0 candidate lessons from mock request
    repo = LessonRepository(db_session)
    assert repo.get_lesson("double_bottom") is None


def test_cli_research_pattern_mock(tmp_path: Path, capsys, db_session):
    """Verifies shootingstar research-pattern CLI runs cleanly in safe default mock mode without writing to DB."""
    from shootingstar.cli.main import main

    cat_dir = tmp_path / "literature"
    cat_dir.mkdir()
    doc = cat_dir / "patterns.md"
    doc.write_text(
        "## Head and Shoulders\n"
        "Source: Empirical Econometrics of Price Formations\n"
        "Source URL: https://arxiv.org/abs/cond-mat/0002447\n\n"
        "A head and shoulders reversal pattern consists of three peaks with the central peak being the highest.\n",
        encoding="utf-8",
    )

    # CLI defaults to safe mock mode (no --live flag needed)
    exit_code = main(["research-pattern", "--query", "Head and Shoulders", "--catalogue-dir", str(cat_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[MOCK RUN] Safe mode enabled" in captured.out
    assert "Status: COMPLETED" in captured.out
    assert "Matches found in catalogue: 1" in captured.out

    # Invariant: DB remains unwritten in mock run
    repo = LessonRepository(db_session)
    assert repo.get_lesson("head_and_shoulders") is None
