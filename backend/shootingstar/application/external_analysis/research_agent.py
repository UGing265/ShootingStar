"""Research Agent: Orchestrates literature catalogue retrieval, model pattern inspection, and verified candidate submission."""

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
from shootingstar.adapters.storage import StoragePaths
from shootingstar.application.external_analysis.contracts import (
    HypothesisContract,
    ResearchAgentContract,
)
from shootingstar.application.external_analysis.lessons import LessonService, LessonWorkflowError
from shootingstar.application.external_analysis.url_validator import (
    SSRFValidationError,
    validate_public_https_url,
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentMatch:
    """Represents a matching excerpt from literature/textbook documents."""
    document_path: str
    source_name: str
    source_url: str
    pattern_title: str
    excerpt: str


class ResearchAgent:
    """Autonomous research agent coordinating literature retrieval, main model extraction, and verified submission."""

    def __init__(
        self,
        lesson_service: LessonService,
        model_adapter: Optional[GeminiModelAdapter] = None,
        catalogue_dir: Optional[Path] = None,
    ):
        self.lesson_service = lesson_service
        self.model_adapter = model_adapter or GeminiModelAdapter()
        self.catalogue_dir = catalogue_dir or self._resolve_catalogue_dir()

    @staticmethod
    def _resolve_catalogue_dir() -> Path:
        """Resolves literature directory across repo root and backend layout."""
        # 1. Check relative to current working directory
        cwd_dir = Path("data/literature")
        if cwd_dir.exists() and any(cwd_dir.iterdir()):
            return cwd_dir.resolve()

        # 2. Check repo root
        repo_root = Path(__file__).resolve().parents[4]
        root_dir = repo_root / "data" / "literature"
        if root_dir.exists():
            return root_dir.resolve()

        # 3. Check backend directory
        backend_dir = repo_root / "backend" / "data" / "literature"
        if backend_dir.exists():
            return backend_dir.resolve()

        return root_dir

    def count_catalogue_documents(self) -> int:
        """Returns the number of available text/markdown literature files in catalogue_dir."""
        if not self.catalogue_dir.exists():
            return 0
        return sum(
            1
            for f in self.catalogue_dir.glob("*.*")
            if f.is_file() and f.suffix.lower() in (".txt", ".md")
        )

    def search_catalogue(self, pattern_query: str) -> List[DocumentMatch]:
        """Scans literature documents for sections discussing patterns similar to pattern_query."""
        if not self.catalogue_dir.exists():
            logger.warning("Literature catalogue directory does not exist: %s", self.catalogue_dir)
            return []

        query_clean = pattern_query.strip().lower()
        # Tokenize query for word matching
        query_tokens = [t for t in re.split(r"[\s_-]+", query_clean) if len(t) > 2]
        matches: List[DocumentMatch] = []

        for doc_file in sorted(self.catalogue_dir.glob("*.*")):
            if not doc_file.is_file() or doc_file.suffix.lower() not in (".txt", ".md"):
                continue

            content = doc_file.read_text(encoding="utf-8", errors="replace")
            # Parse sections by headings (# or ##)
            sections = re.split(r"\n(?=#{1,3}\s+)", content)
            for sec in sections:
                sec_lower = sec.lower()
                # Check if all or most tokens match the section
                match_score = sum(1 for t in query_tokens if t in sec_lower)
                if match_score > 0:
                    # Source metadata MUST be explicitly provided in document; never use fake fallbacks
                    src_match = re.search(r"Source:\s*([^\n]+)", sec, re.IGNORECASE) or re.search(r"Source:\s*([^\n]+)", content, re.IGNORECASE)
                    url_match = re.search(r"Source URL:\s*(https://[^\s\n]+)", sec, re.IGNORECASE) or re.search(r"Source URL:\s*(https://[^\s\n]+)", content, re.IGNORECASE)

                    if not src_match or not url_match:
                        continue

                    source_name = src_match.group(1).strip()
                    source_url = url_match.group(1).strip()
                    title_match = re.search(r"^#{1,3}\s+([^\n]+)", sec)
                    pattern_title = title_match.group(1).strip() if title_match else pattern_query

                    matches.append(
                        DocumentMatch(
                            document_path=str(doc_file),
                            source_name=source_name,
                            source_url=source_url,
                            pattern_title=pattern_title,
                            excerpt=sec.strip(),
                        )
                    )

        return matches

    def orchestrate_research(
        self,
        pattern_query: str,
        mock_mode: bool = False,
    ) -> Dict[str, Any]:
        """Main coordination workflow:

        Phase 1: Search literature catalogue for matching pattern sections.
        Phase 2: Pass matched excerpts to main model for structured extraction.
        Phase 3: Verify verbatim evidence & schema before submitting to PENDING review.
        """
        # Phase 1: Literature search
        doc_count = self.count_catalogue_documents()
        if doc_count == 0:
            return {
                "pattern_query": pattern_query,
                "status": "EMPTY_CATALOGUE",
                "message": f"Thư viện tài liệu '{self.catalogue_dir}' hiện đang trống (0 tài liệu). Vui lòng thêm tài liệu có đầy đủ metadata.",
                "matches_found": 0,
                "candidates_count": 0,
                "candidates": [],
            }

        matches = self.search_catalogue(pattern_query)
        if not matches:
            return {
                "pattern_query": pattern_query,
                "status": "NO_MATCH",
                "message": f"Không tìm thấy tài liệu nào trong {doc_count} tài liệu thư viện chứa mẫu hình tương tự '{pattern_query}'.",
                "matches_found": 0,
                "candidates_count": 0,
                "candidates": [],
            }
        extracted_candidates: List[Dict[str, Any]] = []
        rejected_candidates: List[Dict[str, Any]] = []

        # Phase 2: Main model inspection on matched excerpts
        for match in matches:
            # Validate source URL against SSRF
            try:
                clean_url = validate_public_https_url(match.source_url)
            except SSRFValidationError as ssrf_err:
                rejected_candidates.append({
                    "pattern": match.pattern_title,
                    "reason": f"SSRF URL Validation failed: {ssrf_err}",
                })
                continue

            raw_items = self.model_adapter.extract_lessons_from_text(
                document_text=match.excerpt,
                source_name=match.source_name,
                source_url=clean_url,
                target_pattern_query=pattern_query,
                mock_mode=mock_mode,
            )

            # Phase 3: Evidence verification & Candidate creation
            for item in raw_items:
                source_snippet = item.get("source_snippet", "").strip()

                # Evidence verification: snippet must be grounded in the text
                # In mock mode, we ensure snippet is either non-empty or grounded
                if not source_snippet:
                    rejected_candidates.append({
                        "lesson_id": item.get("lesson_id"),
                        "reason": "Missing source_snippet: no evidence provided.",
                    })
                    continue

                # Verify verbatim citation (enforced unconditionally in all modes)
                if source_snippet not in match.excerpt:
                    rejected_candidates.append({
                        "lesson_id": item.get("lesson_id"),
                        "reason": "Hallucinated evidence: source_snippet does not appear verbatim in input document.",
                    })
                    continue

                lesson_id = str(item.get("lesson_id", "")).strip().lower().replace(" ", "_")
                if not lesson_id:
                    lesson_id = pattern_query.lower().replace(" ", "_")

                title = item.get("title", match.pattern_title)
                short_definition = item.get("short_definition", "")
                caveats = item.get("caveats", "")

                if not short_definition or not caveats:
                    rejected_candidates.append({
                        "lesson_id": lesson_id,
                        "reason": "Incomplete schema: definition or caveats empty.",
                    })
                    continue

                # Mock mode protection: Never persist mock candidates to real database
                if mock_mode:
                    extracted_candidates.append({
                        "lesson_id": lesson_id,
                        "title": title,
                        "source_name": match.source_name,
                        "source_url": clean_url,
                        "short_definition": short_definition,
                        "caveats": caveats,
                        "source_snippet": source_snippet,
                        "status": "MOCK_VERIFIED",
                        "persisted": False,
                    })
                    continue

                # Persistence: submit as PENDING candidate for human operator review
                try:
                    lesson = self.lesson_service.submit_candidate(
                        lesson_id=lesson_id,
                        title=title,
                        source_name=match.source_name,
                        source_url=clean_url,
                        short_definition=short_definition,
                        caveats=caveats,
                        source_snippet=source_snippet,
                        submitter="research_agent",
                    )
                    extracted_candidates.append({
                        "lesson_id": lesson.id,
                        "title": lesson.title,
                        "status": lesson.status,
                        "current_revision_id": lesson.current_revision_id,
                        "persisted": True,
                    })
                except LessonWorkflowError:
                    # Slug collision: deduplicate with short random suffix
                    fallback_id = f"{lesson_id}_{uuid.uuid4().hex[:6]}"
                    lesson = self.lesson_service.submit_candidate(
                        lesson_id=fallback_id,
                        title=title,
                        source_name=match.source_name,
                        source_url=clean_url,
                        short_definition=short_definition,
                        caveats=caveats,
                        source_snippet=source_snippet,
                        submitter="research_agent",
                    )
                    extracted_candidates.append({
                        "lesson_id": lesson.id,
                        "title": lesson.title,
                        "status": lesson.status,
                        "current_revision_id": lesson.current_revision_id,
                        "persisted": True,
                    })

        return {
            "pattern_query": pattern_query,
            "status": "COMPLETED",
            "matches_found": len(matches),
            "candidates_count": len(extracted_candidates),
            "candidates": extracted_candidates,
            "rejected_count": len(rejected_candidates),
            "rejected": rejected_candidates,
        }

    def conduct_job_research(
        self,
        hypothesis: HypothesisContract,
        job_id: str,
        feed_hash: str,
        mock_mode: bool = False,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> ResearchAgentContract:
        """Executes targeted research for an analysis job using Google Grounding and literature catalogue."""
        candidate_names = [c.pattern_name for c in hypothesis.candidates]
        primary_pattern = candidate_names[0] if candidate_names else "candlestick pattern"
        query = f"{primary_pattern} definition criteria rules Steve Nison"

        hyp_dict = {
            "hypothesis_id": hypothesis.hypothesis_id,
            "candidates": [
                {
                    "pattern_name": c.pattern_name,
                    "candle_ids": c.candle_ids,
                    "rationale": c.rationale,
                    "unresolved_context": c.unresolved_context,
                }
                for c in hypothesis.candidates
            ],
            "questions_for_research": hypothesis.questions_for_research,
        }

        research_contract = self.model_adapter.grounded_research(
            query=query,
            hypothesis_context=hyp_dict,
            feed_hash=feed_hash,
            job_id=job_id,
            mock_mode=mock_mode,
            custom_mock=custom_mock,
        )
        return research_contract


def research_contract_to_dict(contract: ResearchAgentContract) -> Dict[str, Any]:
    """Serializes ResearchAgentContract into JSON-compatible dict."""
    return {
        "research_id": contract.research_id,
        "job_id": contract.job_id,
        "feed_hash": contract.feed_hash,
        "search_provider": contract.search_provider,
        "queries_executed": contract.queries_executed,
        "query_receipts": contract.query_receipts,
        "retrieved_at_iso": contract.retrieved_at_iso,
        "research_status": contract.research_status,
        "contradictory_sources_or_facts": contract.contradictory_sources_or_facts,
        "unresolved_questions": contract.unresolved_questions,
        "sources": [
            {
                "source_id": s.source_id,
                "url": s.url,
                "title": s.title,
                "author_or_publisher": s.author_or_publisher,
                "source_type": s.source_type,
                "publication_date_or_unknown": s.publication_date_or_unknown,
                "access_status": s.access_status,
                "section_locator": s.section_locator,
                "excerpt": s.excerpt,
                "content_hash": s.content_hash,
                "tool_trace_id": s.tool_trace_id,
                "review_status": s.review_status,
            }
            for s in contract.sources
        ],
        "pattern_definitions": [
            {
                "pattern_name": d.pattern_name,
                "criterion_ids": d.criterion_ids,
                "source_ids": d.source_ids,
                "required_context": d.required_context,
                "required_confirmation": d.required_confirmation,
                "scope_and_limitations": d.scope_and_limitations,
            }
            for d in contract.pattern_definitions
        ],
    }
