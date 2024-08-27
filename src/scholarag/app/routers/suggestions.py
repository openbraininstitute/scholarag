"""Endpoints for suggestions."""

import logging
import re
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from scholarag.app.config import Settings
from scholarag.app.dependencies import ErrorCode, get_ds_client, get_settings
from scholarag.app.schemas import (
    ArticleTypeSuggestionResponse,
    AuthorSuggestionRequest,
    AuthorSuggestionResponse,
    JournalSuggestionRequest,
    JournalSuggestionResponse,
)
from scholarag.document_stores import AsyncBaseSearch
from scholarag.utils import format_issn

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])

logger = logging.getLogger(__name__)


@router.get(
    "/journal",
    response_model=list[JournalSuggestionResponse],
    responses={
        500: {
            "description": f"code={ErrorCode.NO_DB_ENTRIES.value} No journal found.",
            "content": {
                "application/json": {
                    "schema": {
                        "example": {
                            "detail": {
                                "code": 1,
                                "detail": "Message",
                            }
                        }
                    }
                },
            },
        }
    },
)
async def journal_suggestion(
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: JournalSuggestionRequest = Depends(),  # noqa: B008
) -> list[JournalSuggestionResponse]:
    """Suggest journals with metadata based on keywords.
    \f

    Parameters
    ----------
    request
        Body of the request sent to the server.
    ds_client
        Document store client
    settings
        Global settings of the application

    Returns
    -------
        A list of answers with journal metadata added.
    """  # noqa: D301, D400, D205
    if settings.db.index_journals is None:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.ENDPOINT_INACTIVE.value,
                "detail": (
                    "This endpoint is inactive. Please provide the "
                    "SCHOLARAG__DB__INDEX_JOURNALS environment variable."
                ),
            },
        )
    start = time.time()
    logger.info("Finding journals ...")

    keywords = request.keywords.split()

    match_queries = [
        {"regexp": {"Title": {"value": f".*{keyword}.*", "case_insensitive": True}}}
        for keyword in keywords
    ]
    bool_query = {"query": {"bool": {"must": match_queries}}}
    kwargs = {"sort": ["CiteScore:desc"]}
    results = await ds_client.search(
        settings.db.index_journals,
        bool_query,
        size=min(request.limit * 2, 10000),
        **kwargs,  # type: ignore
    )
    journals: list[JournalSuggestionResponse] = []

    unique_titles: set[str] = set()

    for result in results["hits"]["hits"]:
        source = result["_source"]
        if len(unique_titles) == request.limit:
            break
        if source["Title"] not in unique_titles:
            unique_titles.add(source["Title"])

            issn_types = ["E-ISSN", "Print ISSN"]
            issn_dict: dict[str, str | None] = {}
            for issn_type in issn_types:
                issn_dict[issn_type] = format_issn(source[issn_type])

            journals.append(
                JournalSuggestionResponse(
                    title=source["Title"],
                    citescore=source["CiteScore"],
                    eissn=issn_dict["E-ISSN"],
                    snip=source["SNIP"],
                    sjr=source["SJR"],
                    print_issn=issn_dict["Print ISSN"],
                )
            )

    if not journals:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.NO_DB_ENTRIES.value,
                "detail": "No journal found.",
            },
        )
    logger.info(f"Found journals in {time.time() - start}s.")
    return journals


@router.get(
    "/author",
    response_model=list[AuthorSuggestionResponse],
    responses={
        500: {
            "description": f"code={ErrorCode.NO_DB_ENTRIES.value} No author found.",
            "content": {
                "application/json": {
                    "schema": {
                        "example": {
                            "detail": {
                                "code": 1,
                                "detail": "Message",
                            }
                        }
                    }
                },
            },
        }
    },
)
async def author_suggestion(
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: AuthorSuggestionRequest = Depends(),  # noqa: B008
) -> list[AuthorSuggestionResponse]:
    """Suggest authors based on a name or part of a name.
    \f

    Parameters
    ----------
    request
        Body of the request sent to the server.
    ds_client
        Document store client
    settings
        Global settings of the application

    Returns
    -------
        A list of author names.
    """  # noqa: D301, D400, D205
    # Match case insensitive. Sadly aggregate queries don't support the CASE_INSENSITIVE flag
    # The /i flag is not supported either in regex queries.
    start = time.time()
    regex_pattern = "".join(
        [f"[{char.lower()}{char.upper()}]" for char in request.name]
    )

    pattern = re.compile(re.escape(request.name), re.IGNORECASE)

    # Regex query to partially match author name with a keyword field.
    query = {"regexp": {"authors": f".*{regex_pattern}.*"}}
    kwargs = {"_source": ["authors"]}
    # The size here is a bit arbitrary, but in theory it should ensure that
    # There is enough authors to fill the user's request. If not, people should
    # tell us right away.
    results = await ds_client.search(
        index=settings.db.index_paragraphs,
        query=query,
        size=request.limit * 10,
        aggs=None,
        timeout=60,
        **kwargs,
    )
    authors = []
    for res in results["hits"]["hits"]:
        for author in res["_source"]["authors"]:
            if author not in authors and pattern.search(author):
                authors.append(author)
                if len(authors) == request.limit:
                    break
        if len(authors) == request.limit:
            break

    authors = [AuthorSuggestionResponse(name=author) for author in authors]
    logger.info(f"Author suggestion took {time.time() - start}s")

    if not authors:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.NO_DB_ENTRIES.value,
                "detail": "No author found.",
            },
        )
    return authors


@router.get("/article_types", response_model=list[ArticleTypeSuggestionResponse])
async def article_types(
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ArticleTypeSuggestionResponse]:
    """List all available article_types in the db
    \f

    Parameters
    ----------
    ds_client
        Document store client
    settings
        Global settings of the application

    Returns
    -------
        A list of article types.
    """  # noqa: D301, D400, D205
    aggs = {"article_types": {"terms": {"field": "article_type", "size": 10000}}}
    results = await ds_client.search(
        index=settings.db.index_paragraphs, query=None, size=0, aggs=aggs
    )
    aggregation = results["aggregations"]["article_types"]["buckets"]
    unique_stripped_types = []
    unique_ids = []
    for i, article_type in enumerate(aggregation):
        stripped_type = article_type["key"].strip()
        if stripped_type not in unique_stripped_types:
            unique_stripped_types.append(stripped_type)
            unique_ids.append(i)
        else:
            agg_id = unique_ids[unique_stripped_types.index(stripped_type)]
            aggregation[agg_id]["doc_count"] += article_type["doc_count"]
    aggregation = [aggregation[i] for i in unique_ids]

    article_types = [
        ArticleTypeSuggestionResponse(
            article_type=article["key"], docs_in_db=article["doc_count"]
        )
        for article in aggregation
    ]
    logger.info(f"Found {len(article_types)} article types in the db.")
    return article_types
