"""Conference paper search tools."""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from enum import IntEnum
import mcp.types as types
from mcp.types import ToolAnnotations

MAX_CONCURRENT_SEARCHES = 10
SEARCH_TIMEOUT = 30.0
MAX_RETRIES = 2
from .conferences import (
    CVFSource,
    OpenReviewSource,
    NeurIPSSource,
    ICMLSource,
    AAAISource,
    IJCaiSource,
    ECCVSource,
    ACMSource,
    MLAnthologySource,
)

logger = logging.getLogger("top-paper-mcp-server")

cvf_source = CVFSource()
openreview_source = OpenReviewSource()
neurips_source = NeurIPSSource()
icml_source = ICMLSource()
aaai_source = AAAISource()
ijcai_source = IJCaiSource()
eccv_source = ECCVSource()
acm_source = ACMSource()
mlanthology_source = MLAnthologySource()


class ConferencePriority(IntEnum):
    """Conference priority levels for unified search."""

    CVPR = 100
    ICCV = 95
    NeurIPS = 90
    ICLR = 85
    ICML = 80
    ECCV = 75
    WACV = 70
    ACL = 65
    EMNLP = 60
    NAACL = 55
    COLM = 50
    CoRL = 45
    AAAI = 40
    IJCAI = 35
    MLSYS = 30
    MICCAI = 25
    IWSLT = 20
    INTERSPEECH = 15
    COLT = 10
    UAI = 5
    ACM = 1


CONFERENCE_PRIORITY = {
    conf.upper(): priority.value
    for conf, priority in ConferencePriority.__members__.items()
}

CONFERENCE_CATEGORIES = {
    "computer_vision": ["CVPR", "ICCV", "WACV", "ECCV"],
    "machine_learning": ["NEURIPS", "ICML", "ICLR", "COLM", "CORL", "MLSYS"],
    "nlp": ["ACL", "EMNLP", "NAACL"],
    "speech": ["INTERSPEECH", "IWSLT"],
    "medical": ["MICCAI"],
    "ai": ["AAAI", "IJCAI"],
    "theory": ["COLT", "UAI"],
}

CATEGORY_PRIORITY = {
    "computer_vision": 1,
    "machine_learning": 2,
    "nlp": 3,
    "ai": 4,
    "speech": 5,
    "medical": 6,
    "theory": 7,
}

AVAILABLE_CONFERENCES = {
    "CVF": ["CVPR", "ICCV", "WACV"],
    "ECVA": ["ECCV"],
    "OpenReview": [
        "ICLR",
        "ACL",
        "EMNLP",
        "NAACL",
        "COLM",
        "CoRL",
        "MLSYS",
        "MICCAI",
        "IWSLT",
        "INTERSPEECH",
    ],
    "NeurIPS": ["NeurIPS"],
    "ICML": ["ICML"],
    "AAAI": ["AAAI"],
    "IJCAI": ["IJCAI"],
    "MLAnthology": ["COLT", "UAI"],
    "ACM": ["ACM"],
}

CONFERENCE_SOURCE_MAP = {
    "CVPR": "cvf",
    "ICCV": "cvf",
    "WACV": "cvf",
    "ECCV": "eccv",
    "ICLR": "openreview",
    "NEURIPS": "neurips",
    "ICML": "icml",
    "AAAI": "aaai",
    "IJCAI": "ijcai",
    "ACL": "openreview",
    "EMNLP": "openreview",
    "NAACL": "openreview",
    "COLM": "openreview",
    "CORL": "openreview",
    "MLSYS": "openreview",
    "MICCAI": "openreview",
    "IWSLT": "openreview",
    "INTERSPEECH": "openreview",
    "COLT": "mlanthology",
    "UAI": "mlanthology",
    "ACM": "acm",
}


def _get_source(conference: str):
    """Get the appropriate source for a conference."""
    source_type = CONFERENCE_SOURCE_MAP.get(conference.upper())
    if source_type == "cvf":
        return cvf_source
    elif source_type == "openreview":
        return openreview_source
    elif source_type == "neurips":
        return neurips_source
    elif source_type == "icml":
        return icml_source
    elif source_type == "aaai":
        return aaai_source
    elif source_type == "ijcai":
        return ijcai_source
    elif source_type == "eccv":
        return eccv_source
    elif source_type == "acm":
        return acm_source
    elif source_type == "mlanthology":
        return mlanthology_source
    else:
        raise ValueError(f"Unknown conference: {conference}")


def _build_tool_description() -> str:
    """Build dynamic tool description with available conferences."""
    conf_list = []
    for source, confs in AVAILABLE_CONFERENCES.items():
        conf_list.append(f"- **{source}**: {', '.join(confs)}")
    return f"""Search for papers in top AI/ML/CV conferences.

AVAILABLE CONFERENCES:
{chr(10).join(conf_list)}

YEAR RANGE: 2000-present for most conferences

EXAMPLES:
- Search CVPR 2024 papers about "object detection"
- Search ICLR 2025 papers about "transformer"
- Search NeurIPS papers about "reinforcement learning"

Note: Conference must be active on OpenReview/CVF for the specified year to return results."""


conference_search_tool = types.Tool(
    name="conference_search",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description=_build_tool_description(),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for paper titles and abstracts",
            },
            "conference": {
                "type": "string",
                "description": "Conference name (e.g., CVPR, ICCV, WACV, ECCV, ICLR, NeurIPS, ICML, AAAI, IJCAI, ACL, EMNLP, NAACL, COLM, CoRL, MLSYS, MICCAI, IWSLT, INTERSPEECH)",
                "enum": [
                    "CVPR",
                    "ICCV",
                    "WACV",
                    "ECCV",
                    "ICLR",
                    "NeurIPS",
                    "ICML",
                    "AAAI",
                    "IJCAI",
                    "ACL",
                    "EMNLP",
                    "NAACL",
                    "COLM",
                    "CoRL",
                    "MLSYS",
                    "MICCAI",
                    "IWSLT",
                    "INTERSPEECH",
                    "ACM",
                ],
            },
            "year": {
                "type": "integer",
                "description": "Conference year (e.g., 2024, 2025)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 50)",
                "default": 10,
            },
            "search_all": {
                "type": "boolean",
                "description": "Search across ALL conferences concurrently with multi-threading (default: false)",
                "default": False,
            },
            "conferences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "When search_all is true: specify conferences to search (optional, searches all if empty)",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": list(CONFERENCE_CATEGORIES.keys())},
                "description": "When search_all is true: filter by conference categories",
            },
        },
        "required": ["query", "conference", "year"],
    },
)


async def handle_conference_search(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle conference paper search with optional multi-conference concurrent search."""
    try:
        query = arguments.get("query", "")
        conference = arguments.get("conference", "").upper()
        year = arguments.get("year", 2025)
        max_results = min(int(arguments.get("max_results", 10)), 50)
        search_all = arguments.get("search_all", False)

        if search_all:
            conferences = arguments.get("conferences", [])
            categories = arguments.get("categories", [])

            target_conferences = []

            if conferences:
                target_conferences = [c.upper() for c in conferences]
            elif categories:
                for category in categories:
                    if category in CONFERENCE_CATEGORIES:
                        target_conferences.extend(CONFERENCE_CATEGORIES[category])
            else:
                target_conferences = list(CONFERENCE_PRIORITY.keys())

            target_conferences = [
                c for c in target_conferences if c in CONFERENCE_SOURCE_MAP
            ]

            if not target_conferences:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": "No valid conferences to search"}),
                    )
                ]

            search_tasks = []
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
            for conf in target_conferences:
                source = _get_source(conf)
                task = _search_with_semaphore(
                    source, query, conf, year, max_results, semaphore
                )
                search_tasks.append(task)

            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            all_papers = []
            conference_results = {}

            for result in results:
                if isinstance(result, Exception):
                    continue
                conf_name, papers = result
                if papers:
                    priority = _get_conference_priority(conf_name)
                    category = _get_category(conf_name) or "other"
                    for paper in papers:
                        paper_dict = paper.to_dict()
                        paper_dict["_search_priority"] = priority
                        paper_dict["_search_category"] = category
                        all_papers.append(paper_dict)
                    conference_results[conf_name] = len(papers)

            all_papers.sort(key=lambda x: (-x["_search_priority"], x.get("title", "")))

            final_papers = all_papers[: max_results * 3]
            for paper in final_papers:
                paper.pop("_search_priority", None)
                paper.pop("_search_category", None)

            response = {
                "query": query,
                "year": year,
                "total_results": len(final_papers),
                "conferences_searched": target_conferences,
                "conference_results": conference_results,
                "papers": final_papers,
            }

            return [types.TextContent(type="text", text=json.dumps(response, indent=2))]

        if not conference or not year:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": "conference and year are required"}),
                )
            ]

        source = _get_source(conference)
        papers = await source.search(query, conference, year, max_results)

        if not papers:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "total_results": 0,
                            "message": f"No papers found for {conference} {year} with query '{query}'",
                            "papers": [],
                        },
                        indent=2,
                    ),
                )
            ]

        results = {
            "total_results": len(papers),
            "conference": conference,
            "year": year,
            "papers": [p.to_dict() for p in papers],
        }

        return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

    except ValueError as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        logger.exception(f"Conference search error: {e}")
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


def _get_conference_priority(conference: str) -> int:
    """Get priority score for a conference."""
    return CONFERENCE_PRIORITY.get(conference.upper(), 0)


def _get_category(conference: str) -> Optional[str]:
    """Get category for a conference."""
    for category, conferences in CONFERENCE_CATEGORIES.items():
        if conference.upper() in conferences:
            return category
    return None


unified_search_tool = types.Tool(
    name="unified_search",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description="""Unified search across multiple conferences with concurrent execution.

FEATURES:
- Concurrent search across multiple conferences in parallel threads
- Priority-based ordering (CVPR > NeurIPS > ICLR > ICML > ...)
- Category-based filtering (computer_vision, machine_learning, nlp, ai, speech, medical, theory)
- Results sorted by conference priority and relevance

INPUT:
- query: Search keywords
- year: Conference year to search
- conferences: List of specific conferences (optional, searches all if empty)
- categories: Filter by categories (optional)
- max_results_per_conference: Results per conference (default: 5)
- total_results: Total results to return (default: 20)

EXAMPLES:
- Search all conferences for "transformer" in 2024
- Search computer_vision category for "object detection"
- Search specific conferences: ["CVPR", "NeurIPS", "ICLR"]""",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for paper titles and abstracts",
            },
            "year": {
                "type": "integer",
                "description": "Conference year to search (e.g., 2024, 2025)",
            },
            "conferences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific conferences to search (empty = search all)",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": list(CONFERENCE_CATEGORIES.keys())},
                "description": "Filter by conference categories",
            },
            "max_results_per_conference": {
                "type": "integer",
                "description": "Maximum results per conference (default: 5)",
                "default": 5,
            },
            "total_results": {
                "type": "integer",
                "description": "Total results to return (default: 20, max: 100)",
                "default": 20,
            },
        },
        "required": ["query", "year"],
    },
)


async def _search_single_conference(
    source,
    query: str,
    conference: str,
    year: int,
    max_results: int,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> tuple[str, List]:
    """Search a single conference with timeout and optional semaphore限流."""

    async def _search_with_timeout():
        for attempt in range(MAX_RETRIES):
            try:
                papers = await asyncio.wait_for(
                    source.search(query, conference, year, max_results),
                    timeout=SEARCH_TIMEOUT,
                )
                return papers
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout for {conference} (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                if attempt == MAX_RETRIES - 1:
                    return []
            except Exception as e:
                logger.warning(f"Search error for {conference}: {e}")
                if attempt == MAX_RETRIES - 1:
                    return []
                await asyncio.sleep(0.5 * (attempt + 1))
        return []

    if semaphore:
        async with semaphore:
            papers = await _search_with_timeout()
    else:
        papers = await _search_with_timeout()

    return conference, papers


async def _search_with_semaphore(
    source,
    query: str,
    conference: str,
    year: int,
    max_results: int,
    semaphore: asyncio.Semaphore,
) -> tuple[str, List]:
    """Wrapper for concurrent search with semaphore限流."""
    return await _search_single_conference(
        source, query, conference, year, max_results, semaphore
    )


async def handle_unified_search(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle unified multi-conference search with concurrent execution."""
    try:
        query = arguments.get("query", "")
        year = arguments.get("year", 2025)
        specified_conferences = arguments.get("conferences", [])
        categories = arguments.get("categories", [])
        max_per_conference = min(
            int(arguments.get("max_results_per_conference", 5)), 20
        )
        total_results = min(int(arguments.get("total_results", 20)), 100)

        if not query:
            return [
                types.TextContent(
                    type="text", text=json.dumps({"error": "query is required"})
                )
            ]

        target_conferences = []

        if specified_conferences:
            target_conferences = [c.upper() for c in specified_conferences]
        elif categories:
            for category in categories:
                if category in CONFERENCE_CATEGORIES:
                    target_conferences.extend(CONFERENCE_CATEGORIES[category])
        else:
            target_conferences = list(CONFERENCE_PRIORITY.keys())

        target_conferences = [
            c for c in target_conferences if c in CONFERENCE_SOURCE_MAP
        ]

        if not target_conferences:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": "No valid conferences to search"}),
                )
            ]

        search_tasks = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
        for conf in target_conferences:
            source = _get_source(conf)
            task = _search_with_semaphore(
                source, query, conf, year, max_per_conference, semaphore
            )
            search_tasks.append(task)

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_papers = []
        conference_results = {}

        for result in results:
            if isinstance(result, Exception):
                continue
            conference, papers = result
            if papers:
                priority = _get_conference_priority(conference)
                category = _get_category(conference) or "other"
                for paper in papers:
                    paper_dict = paper.to_dict()
                    paper_dict["_search_priority"] = priority
                    paper_dict["_search_category"] = category
                    all_papers.append(paper_dict)
                conference_results[conference] = len(papers)

        all_papers.sort(key=lambda x: (-x["_search_priority"], x.get("title", "")))

        final_papers = all_papers[:total_results]
        for paper in final_papers:
            paper.pop("_search_priority", None)
            paper.pop("_search_category", None)

        response = {
            "query": query,
            "year": year,
            "total_results": len(final_papers),
            "conferences_searched": target_conferences,
            "conference_results": conference_results,
            "papers": final_papers,
        }

        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]

    except Exception as e:
        logger.exception(f"Unified search error: {e}")
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
