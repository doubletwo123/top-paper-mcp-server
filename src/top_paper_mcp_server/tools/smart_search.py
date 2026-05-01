"""Smart search with query expansion and lightweight RL.

This module implements:
- Query expansion: rule-based fallback + LLM pre-expanded queries
- Parallel execution of multiple query variants
- Reciprocal Rank Fusion (RRF) for result merging
- Preference-based term selection with a Contextual Bandit approach
- Feedback recording for continuous improvement
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.types import ToolAnnotations

from .conference_search import (
    CONFERENCE_ARXIV_CATEGORIES,
    CONFERENCE_PRIORITY,
    _get_conference_priority,
    _merge_results,
    _search_arxiv_for_conference,
    _search_openreview_for_conference,
)
from .conferences.openreview import VENUE_IDS
from .preference import PreferenceStore, compute_reward
from .query_expansion import (
    _extract_keywords_from_results,
    _generate_candidates,
    _rrf_fuse,
)
from .search import _raw_arxiv_search

logger = logging.getLogger("top-paper-mcp-server")

# Session log: maps paper_id -> list of expansion terms that found it
# Reset on server restart (in-memory only)
_search_session_log: Dict[str, List[str]] = {}

# Maximum number of expanded queries to run in parallel
_MAX_EXPANDED_QUERIES = 5

OPENREVIEW_CONFERENCES = {conf.upper() for conf, _year in VENUE_IDS.keys()}


def _log_search_results(papers: List[Dict[str, Any]], terms_used: List[str]) -> None:
    """Record which expansion terms found which papers (for feedback)."""
    for paper in papers:
        paper_id = paper.get("id", "")
        if paper_id:
            existing = _search_session_log.get(paper_id, [])
            # Merge without duplicates
            combined = list(set(existing + terms_used))
            _search_session_log[paper_id] = combined


async def _run_arxiv_queries(
    queries: List[str],
    max_results: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    categories: Optional[List[str]] = None,
) -> List[List[Dict[str, Any]]]:
    """Run multiple arXiv queries concurrently."""
    tasks = [
        _raw_arxiv_search(q, max_results=max_results, date_from=date_from, date_to=date_to, categories=categories)
        for q in queries
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if isinstance(r, list) else [] for r in results]


async def _run_conference_queries(
    queries: List[str],
    conference: str,
    year: int,
    max_results: int,
) -> List[List[Dict[str, Any]]]:
    """Run multiple dual-path (arXiv + OpenReview) queries for a conference concurrently."""

    async def _single_query_dual(query: str) -> List[Dict[str, Any]]:
        categories = CONFERENCE_ARXIV_CATEGORIES.get(conference, [])
        date_from = f"{year}-01-01"
        date_to = f"{year}-12-31"

        arxiv_task = _search_arxiv_for_conference(query, conference, year, max_results)
        openreview_task = _search_openreview_for_conference(query, conference, year, max_results)

        arxiv_results, openreview_papers = await asyncio.gather(
            arxiv_task, openreview_task, return_exceptions=True
        )

        arxiv_list = arxiv_results if isinstance(arxiv_results, list) else []
        or_list = openreview_papers if isinstance(openreview_papers, list) else []

        return _merge_results(arxiv_list, or_list, conference, year)

    tasks = [_single_query_dual(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if isinstance(r, list) else [] for r in results]


async def handle_smart_search(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle the smart_search MCP tool call.

    Supports two modes:
    1. LLM-expanded: pass `queries` (list of strings) for the LLM to pre-expand
    2. Auto-expand: pass `query` (single string) for server-side rule-based expansion

    Preference-based term selection is applied when auto-expanding.
    """
    # Parse inputs
    query = arguments.get("query", "").strip()
    queries_raw = arguments.get("queries", [])
    conference = arguments.get("conference", "").strip().upper()
    year = arguments.get("year")
    max_results = min(max(1, int(arguments.get("max_results", 10))), 50)
    expand = arguments.get("expand", True)

    if not query and not queries_raw:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"status": "error", "message": "Query is required"}),
            )
        ]

    # Build the list of queries to execute
    if queries_raw and isinstance(queries_raw, list):
        # Mode 1: LLM pre-expanded queries
        all_queries = [str(q).strip() for q in queries_raw if q][:_MAX_EXPANDED_QUERIES]
        terms_used = all_queries
    elif expand and query:
        # Mode 2: server-side expansion with preference weighting
        candidates = _generate_candidates(query)

        # Apply preference-based selection
        store = PreferenceStore()
        store.load()
        selected = store.select_terms(candidates, original_query=query, top_k=min(3, _MAX_EXPANDED_QUERIES))

        all_queries = selected
        terms_used = selected
    else:
        # No expansion
        all_queries = [query]
        terms_used = [query]

    # Execute queries
    if conference and conference in OPENREVIEW_CONFERENCES and year:
        result_lists = await _run_conference_queries(
            all_queries, conference, int(year), max_results
        )
    else:
        # arXiv-only path
        date_from = None
        date_to = None
        categories = arguments.get("categories", [])
        if year:
            date_from = f"{year}-01-01"
            date_to = f"{year}-12-31"
        result_lists = await _run_arxiv_queries(
            all_queries,
            max_results=max_results,
            date_from=date_from,
            date_to=date_to,
            categories=categories if categories else None,
        )

    # Merge with RRF
    fused = _rrf_fuse(result_lists)

    # Log for feedback
    _log_search_results(fused, terms_used)

    # Extract keywords from results (for future expansion learning)
    extracted_keywords = _extract_keywords_from_results(fused, top_k=10)

    # Cap results
    papers = fused[:max_results]

    result = {
        "status": "success",
        "query": query or " | ".join(queries_raw),
        "expanded_queries": all_queries,
        "total_results": len(papers),
        "papers": papers,
        "extracted_keywords": extracted_keywords,
    }

    if conference:
        result["conference"] = conference
    if year:
        result["year"] = year

    return [types.TextContent(type="text", text=json.dumps(result))]


async def handle_record_feedback(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle the record_feedback MCP tool call.

    Records a reward signal for a paper, updating preference weights
    for the expansion terms that found it.
    """
    paper_id = arguments.get("paper_id", "").strip()
    action = arguments.get("action", "").strip()

    if not paper_id:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"status": "error", "message": "paper_id is required"}),
            )
        ]

    if action not in ("download", "read"):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"status": "error", "message": "action must be 'download' or 'read'"}),
            )
        ]

    # Look up which terms found this paper
    terms = _search_session_log.get(paper_id, [])
    if not terms:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"No search session found for {paper_id}. Feedback not recorded.",
                    "terms_found": False,
                }),
            )
        ]

    # Compute reward
    reward = compute_reward({}, action)

    # Update preferences
    store = PreferenceStore()
    store.load()
    categories = arguments.get("categories", [])
    store.record_reward(terms, reward, categories=categories if categories else None)

    return [
        types.TextContent(
            type="text",
            text=json.dumps({
                "status": "success",
                "paper_id": paper_id,
                "action": action,
                "reward": reward,
                "terms_reinforced": terms,
                "interaction_count": store.interaction_count,
            }),
        )
    ]


# ---------------------------------------------------------------------------
# MCP tool definitions
# ---------------------------------------------------------------------------

smart_search_tool = types.Tool(
    name="smart_search",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description=(
        "Smart search with query expansion and preference learning. "
        "Automatically expands queries into multiple variants, runs them in parallel, "
        "and merges results using Reciprocal Rank Fusion (RRF). "
        "Supports both auto-expansion (pass 'query') and LLM pre-expansion (pass 'queries'). "
        "Learns from user interactions to improve future search quality."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for auto-expansion (single string)",
            },
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Pre-expanded queries from LLM (list of strings). Takes priority over 'query' for expansion.",
            },
            "conference": {
                "type": "string",
                "description": "Conference name (e.g., CVPR, NeurIPS, ICLR). Optional.",
                "enum": [
                    "CVPR", "ICCV", "WACV", "ECCV", "ICLR", "NeurIPS",
                    "ICML", "AAAI", "IJCAI", "ACL", "EMNLP", "NAACL",
                    "COLM", "CoRL", "MLSYS", "MICCAI", "IWSLT", "INTERSPEECH",
                ],
            },
            "year": {
                "type": "integer",
                "description": "Conference year or publication year filter (e.g., 2024, 2025)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 50)",
                "default": 10,
            },
            "expand": {
                "type": "boolean",
                "description": "Enable query expansion (default: true). Set false for exact-match search.",
                "default": True,
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "arXiv categories to filter by (e.g., ['cs.CV', 'cs.AI']). Only used without conference.",
            },
        },
        "required": [],
    },
)

record_feedback_tool = types.Tool(
    name="record_feedback",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    description=(
        "Record user feedback on a search result to improve future searches. "
        "This feeds into a lightweight reinforcement learning system that learns "
        "which query expansion terms are most effective."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "paper_id": {
                "type": "string",
                "description": "The arXiv ID or OpenReview ID of the paper",
            },
            "action": {
                "type": "string",
                "description": "User action: 'download' or 'read'",
                "enum": ["download", "read"],
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "arXiv categories of the paper (optional, for category preference learning)",
            },
        },
        "required": ["paper_id", "action"],
    },
)
