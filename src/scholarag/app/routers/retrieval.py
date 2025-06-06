"""Endpoints for retrieving documents."""

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page, paginate
from httpx import AsyncClient

from scholarag.app.config import Settings
from scholarag.app.dependencies import (
    ErrorCode,
    get_ds_client,
    get_httpx_client,
    get_query_from_params,
    get_reranker,
    get_rts,
    get_settings,
    get_user_id,
)
from scholarag.app.schemas import (
    ArticleCountResponse,
    ArticleMetadata,
    ParagraphMetadata,
    RetrievalRequest,
)
from scholarag.document_stores import AsyncBaseSearch
from scholarag.retrieve_metadata import MetaDataRetriever
from scholarag.services import CohereRerankingService, RetrievalService

router = APIRouter(
    prefix="/retrieval", tags=["Retrieval"], dependencies=[Depends(get_user_id)]
)

logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=list[ParagraphMetadata],
    responses={
        500: {
            "description": (
                f"If code={ErrorCode.NO_DB_ENTRIES.value}, no"
                " relevant context is found in the database."
            ),
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
async def retrieval(
    rts: Annotated[RetrievalService, Depends(get_rts)],
    rs: Annotated[CohereRerankingService | None, Depends(get_reranker)],
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    httpx_client: Annotated[AsyncClient, Depends(get_httpx_client)],
    filter_query: Annotated[dict[str, Any], Depends(get_query_from_params)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: RetrievalRequest = Depends(),  # noqa: B008
) -> list[ParagraphMetadata]:
    """Answer the query with most relevant paragraphs.
    \f

    Parameters
    ----------
    request
        Body of the request sent to the server.
    rts
        Retrieval service.
    rs
        Reranker service.
    ds_client
        Document store client
    httpx_client
        HTTP Client.
    filter_query
        Filtering query for paragraph retrieval.
    settings
        Global settings of the application

    Returns
    -------
        A list of article titles and paragraphs.
    """  # noqa: D301, D400, D205
    if len(request.query) > settings.misc.query_max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Query string has {len(request.query)} characters. Maximum allowed is {settings.misc.query_max_size}.",
        )
    start = time.time()
    logger.info("Finding documents ...")

    contexts = await rts.arun(
        ds_client=ds_client,
        query=request.query,
        retriever_k=request.retriever_k,
        db_filter=filter_query,
        max_length=settings.retrieval.max_length,
    )
    if not contexts:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.NO_DB_ENTRIES.value,
                "detail": (
                    "No document found. Modify the filters or the query and try again."
                ),
            },
        )
    logger.info(f"Semantic search took {time.time() - start}s")

    metadata_retriever = MetaDataRetriever(
        external_apis=settings.metadata.external_apis
    )

    fetched_abstracts = await metadata_retriever.retrieve_metadata(
        contexts=contexts,
        ds_client=ds_client,
        db_index_paragraphs=settings.db.index_paragraphs,
        to_retrieve=["abstracts"],
    )
    abstracts = fetched_abstracts["recreate_abstract"]
    contexts = [
        {**context, "abstract": abstracts[context.get("article_id")]}
        for context in contexts
    ]

    if rs is None or not request.use_reranker:
        indices = tuple(range(len(contexts)))
        scores = None
    else:
        contexts, _, scores, indices = await rs.rerank(
            query=request.query,
            contexts=contexts,
            reranker_k=request.reranker_k,
        )

    fetched_metadata = await metadata_retriever.retrieve_metadata(
        contexts=contexts,
        ds_client=ds_client,
        db_if_articles=settings.db.index_journals,
        httpx_client=httpx_client,
        to_retrieve=["citation_counts", "impact_factors", "journal_names"],
    )

    citedby_counts = fetched_metadata.get("get_citation_count", {})
    journal_names = fetched_metadata.get("get_journal_name", {})
    impact_factors = fetched_metadata["get_impact_factors"]

    responses = []
    for i, context in enumerate(contexts):
        journal_issn = context.get("journal")
        metadata = {
            "article_title": context["title"],
            "section": context["section"],
            "paragraph": context["text"],
            "journal_issn": context.get("journal"),
            "date": context.get("date"),
            "article_id": context["article_id"],
            "ds_document_id": str(context["document_id"]),
            "article_doi": context["doi"],
            "pubmed_id": context["pubmed_id"],
            "article_authors": context["authors"],
            "article_type": context["article_type"],
            "context_id": indices[i],
            "reranking_score": scores[i] if scores is not None else None,
            # on the fly metadata
            "abstract": context.get("abstract"),
            "journal_name": journal_names.get(journal_issn),
            "impact_factor": impact_factors[journal_issn],
            "cited_by": citedby_counts.get(context.get("doi")),
        }

        responses.append(ParagraphMetadata(**metadata))
    return responses


@router.get("/article_count")
async def article_count(
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    filter_query: Annotated[dict[str, Any], Depends(get_query_from_params)],
    settings: Annotated[Settings, Depends(get_settings)],
    topics: Annotated[
        list[str] | None,
        Query(
            description="Keyword to be matched in text. AND matching (e.g. for TOPICS)."
        ),
    ] = None,
    regions: Annotated[
        list[str] | None,
        Query(
            description=(
                "Keyword to be matched in text. OR matching (e.g. for BRAIN_REGIONS)."
            )
        ),
    ] = None,
) -> ArticleCountResponse:
    """Article count based on keyword matching.
    \f

    Parameters
    ----------
    ds_client
        Document store client.
    filter_query
        Filtering query for paragraph retrieval.
    settings
        Global settings of the application.
    topics
        Keywords to be matched in text. AND matches list elements.
    regions
        Keywords to be matched in text. OR matches list elements.

    Returns
    -------
        A list of article titles and paragraphs.
    """  # noqa: D301, D400, D205
    start = time.time()
    logger.info("Finding unique articles matching the query ...")

    if not topics and not regions:
        raise HTTPException(
            status_code=422, detail="Please provide at least one region or topic."
        )

    # Match the keywords on abstract + title.
    topic_query = (
        [
            {
                "multi_match": {
                    "query": topic,
                    "type": "phrase",
                    "fields": ["title", "text"],
                }
            }
            for topic in topics
        ]
        if topics is not None
        else []
    )
    regions_query = (
        [
            {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": region,
                                "type": "phrase",
                                "fields": ["title", "text"],
                            }
                        }
                        for region in regions
                    ]
                }
            }
        ]
        if regions is not None
        else []
    )
    filter_query_list = filter_query["bool"]["must"] if filter_query else []

    query: dict[str, Any] = {
        "query": {
            "bool": {
                "must": [
                    *topic_query,
                    *regions_query,
                    *filter_query_list,
                ]
            }
        }
    }

    # Aggregation query.
    aggs = {
        "article_count": {
            "cardinality": {
                "field": "article_id",
                "precision_threshold": (
                    10000
                ),  # Might be approximative if more documents.
            },
        }
    }

    results = await ds_client.search(
        index=settings.db.index_paragraphs, query=query, size=0, aggs=aggs
    )
    article_count = results["aggregations"]["article_count"]["value"]
    logger.info(f"unique article retrieval took: {time.time() - start}s")
    return ArticleCountResponse(article_count=article_count)


@router.get(
    "/article_listing",
    response_model=Page[ArticleMetadata],
    responses={
        500: {
            "description": (
                "No article corresponding to the filters found. If"
                f" code={ErrorCode.NO_DB_ENTRIES.value}, no article matching filter"
                " found."
            ),
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
async def article_listing(
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    httpx_client: Annotated[AsyncClient, Depends(get_httpx_client)],
    filter_query: Annotated[dict[str, Any], Depends(get_query_from_params)],
    settings: Annotated[Settings, Depends(get_settings)],
    topics: Annotated[
        list[str] | None,
        Query(
            description="Keyword to be matched in text. AND matching (e.g. for TOPICS)."
        ),
    ] = None,
    regions: Annotated[
        list[str] | None,
        Query(
            description=(
                "Keyword to be matched in text. OR matching (e.g. for BRAIN_REGIONS)."
            )
        ),
    ] = None,
    number_results: Annotated[
        int | None,
        Query(description="Number of results to return. Max 10 000.", ge=1, le=10_000),
    ] = 100,
    sort_by_date: Annotated[
        bool | None,
        Query(
            description=(
                "Sort by date True or False. If the latter, we sort by relevance"
            )
        ),
    ] = False,
) -> Page[ArticleMetadata]:
    """Article id listing based on keyword matching.
    \f

    Parameters
    ----------
    request
        Request sent by the user.
    ds_client
        Document store client.
    httpx_client
        HTTP Client.
    filter_query
        Filtering query for paragraph retrieval.
    settings
        Global settings of the application.
    topics
        Keywords to be matched in text. AND matches list elements.
    regions
        Keywords to be matched in text. OR matches list elements.
    number_results
        Number of results to return. Max 10 000.
    sort_by_date
        Sort by date True or False. If the latter, we sort by best match.

    Returns
    -------
        A list of article titles and paragraphs.
    """  # noqa: D301, D400, D205
    start = time.time()
    logger.info("Finding unique articles matching the query ...")

    if not topics and not regions:
        raise HTTPException(
            status_code=422, detail="Please provide at least one region or topic."
        )

    # Match the keywords on abstract + title.
    topic_query = (
        [
            {
                "multi_match": {
                    "query": topic,
                    "type": "phrase",
                    "fields": ["title", "text"],
                }
            }
            for topic in topics
        ]
        if topics is not None
        else []
    )
    regions_query = (
        [
            {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": region,
                                "type": "phrase",
                                "fields": ["title", "text"],
                            }
                        }
                        for region in regions
                    ]
                }
            }
        ]
        if regions is not None
        else []
    )
    filter_query_list = filter_query["bool"]["must"] if filter_query else []

    query: dict[str, Any] = {
        "query": {
            "bool": {
                "must": [
                    *topic_query,
                    *regions_query,
                    *filter_query_list,
                ]
            }
        }
    }

    aggs: dict[str, Any] = {
        "relevant_ids": {
            "terms": {
                "size": number_results,
                "field": "article_id",
                "order": {"score": "desc"},
            },
            "aggs": {
                "score": {"max": {"script": "_score"}},
                "ids_hit": {"top_hits": {"size": 1}},
            },
        }
    }

    if sort_by_date:
        aggs["relevant_ids"]["aggs"]["score"]["max"] = {"field": "date"}

    results = await ds_client.search(
        index=settings.db.index_paragraphs, query=query, size=0, aggs=aggs
    )

    logger.info(f"unique article retrieval took: {time.time() - start}s")

    docs = [
        res["ids_hit"]["hits"]["hits"][0]["_source"]
        for res in results["aggregations"]["relevant_ids"]["buckets"]
    ]

    if len(docs) == 0:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.NO_DB_ENTRIES.value,
                "detail": (
                    "No article found corresponding to the filters. You can use the"
                    " article_count endpoint to check which set of filters actually"
                    " returns documents. If the article_count endpoint returned a non"
                    " zero count with the same filters, report the issue to the"
                    " Machine Learning team on Slack."
                ),
            },
        )

    metadata_retriever = MetaDataRetriever(
        external_apis=settings.metadata.external_apis
    )

    start_2 = time.time()
    fetched_metadata = await metadata_retriever.retrieve_metadata(
        docs,
        ds_client,
        settings.db.index_journals,
        settings.db.index_paragraphs,
        httpx_client,
    )
    logger.info(
        f"Retrieved metadata of {len(docs)} articles in {time.time() - start_2}s."
    )
    citedby_counts = fetched_metadata.get("get_citation_count", {})
    journal_names = fetched_metadata.get("get_journal_name", {})
    impact_factors = fetched_metadata["get_impact_factors"]
    abstracts = fetched_metadata["recreate_abstract"]

    responses = []
    for context in docs:
        journal_issn = context.get("journal")
        metadata = {
            "article_title": context["title"],
            "journal_issn": context.get("journal"),
            "date": context.get("date"),
            "article_id": context["article_id"],
            "article_doi": context["doi"],
            "pubmed_id": context["pubmed_id"],
            "article_authors": context["authors"],
            "article_type": context["article_type"],
            # on the fly metadata
            "abstract": abstracts[context.get("article_id")],
            "journal_name": journal_names.get(journal_issn),
            "impact_factor": impact_factors[journal_issn],
            "cited_by": citedby_counts.get(context.get("doi")),
        }

        responses.append(ArticleMetadata(**metadata))
    return paginate(responses)
