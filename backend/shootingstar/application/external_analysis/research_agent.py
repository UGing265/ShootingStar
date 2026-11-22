"""Grounded research for external analysis reports."""

from typing import Any, Dict, Optional

from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
from shootingstar.application.external_analysis.contracts import (
    HypothesisContract,
    ResearchAgentContract,
)


class ResearchAgent:
    """Coordinates grounded research for analysis jobs."""

    def __init__(self, model_adapter: Optional[GeminiModelAdapter] = None):
        self.model_adapter = model_adapter or GeminiModelAdapter()

    def conduct_job_research(
        self,
        hypothesis: HypothesisContract,
        job_id: str,
        feed_hash: str,
        mock_mode: bool = False,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> ResearchAgentContract:
        """Executes targeted research for an analysis job using Google Grounding."""
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
