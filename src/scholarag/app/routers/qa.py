"""Endpoints for question answering pipeline."""

import logging
import re
import time
from typing import Annotated, Any

from cohere.errors import TooManyRequestsError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from openai import AsyncOpenAI, BadRequestError

from scholarag.app.config import Settings
from scholarag.app.dependencies import (
    ErrorCode,
    get_ds_client,
    get_generative_qas,
    get_httpx_client,
    get_openai_client,
    get_query_from_params,
    get_reranker,
    get_rts,
    get_settings,
)
from scholarag.app.schemas import (
    GenerativeQARequest,
    GenerativeQAResponse,
    ParagraphMetadata,
    PassthroughRequest,
    PassthroughResponse,
)
from scholarag.app.streaming import stream_response
from scholarag.document_stores import AsyncBaseSearch
from scholarag.generative_question_answering import GenerativeQAWithSources
from scholarag.retrieve_metadata import MetaDataRetriever
from scholarag.services import CohereRerankingService, RetrievalService

router = APIRouter(prefix="/qa", tags=["Question answering"])

logger = logging.getLogger(__name__)


@router.post(
    "/passthrough",
    response_model=PassthroughResponse,
    responses={
        500: {
            "description": (
                f"If code={ErrorCode.INCOMPLETE_ANSWER.value}, max number of token"
                " reached during the answer of generative model."
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
                }
            },
        },
        413: {
            "description": (
                f"If code={ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value}, max number of"
                " token reached for the generative model."
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
                }
            },
        },
    },
)
async def passthrough(
    request: PassthroughRequest,
    qas: Annotated[AsyncOpenAI, Depends(get_openai_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PassthroughResponse:
    """Answer the query given the context with a generative model.
    \f

    Parameters
    ----------
    request
        Body of the request sent to the server.
    qas
        Client to the service processing the query
    settings
        Global settings of the application

    Returns
    -------
        A single answer.
    """  # noqa: D301, D400, D205
    start = time.time()
    logger.info("Finding answers ...")
    try:
        answer = await qas.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": request.query,
                }
            ],
            model=settings.generative.openai.model,
        )
    except BadRequestError as err:
        numbers = re.findall(r"\d+", err.message)[1:]
        if len(numbers) == 2:
            message = (
                f"This model's maximum context length is {numbers[0]} tokens. However, "
                f"your messages resulted in {numbers[1]} tokens. Please reduce"
                " retriever_k."
            )
            raise HTTPException(
                status_code=413,
                detail={
                    "code": ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value,
                    "detail": message,
                },
            )
        else:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value,
                    "detail": "OpenAI error.",
                },
            )

    if answer.choices[0].finish_reason == "length":
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.INCOMPLETE_ANSWER.value,
                "detail": (
                    "The LLM did not have enough completion tokens available to finish"
                    " its answer."
                ),
                "raw_answer": answer.choices[0].message.content,
            },
        )
    logger.info(f"Found answer in {time.time() - start}")
    return PassthroughResponse(answer=answer.choices[0].message.content)


@router.post(
    "/generative",
    response_model=GenerativeQAResponse,
    responses={
        500: {
            "description": (
                f"If code={ErrorCode.NO_DB_ENTRIES.value}, no relevant context is found"
                f" in the database. If code={ErrorCode.NO_ANSWER_FOUND.value}, no"
                " answer is found by the LLM from the extracted contexts. If"
                f" code={ErrorCode.INCOMPLETE_ANSWER.value}, max number of token"
                " reached during the answer of generative model -> Please reduce"
                " retriever_k of 1 or 2 paragraphs. If"
                f" code={ErrorCode.MAX_COHERE_REQUESTS.value}, max number of requests"
                " reached for the reranking model -> Wait a bit or turn it off."
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
                }
            },
        },
        413: {
            "description": (
                f"If code={ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value}, max number of"
                " token reached for the generative model -> Reduce retriever_k."
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
                }
            },
        },
    },
)
async def generative_qa(
    request: GenerativeQARequest,
    rts: Annotated[RetrievalService, Depends(get_rts)],
    qas: Annotated[GenerativeQAWithSources, Depends(get_generative_qas)],
    rs: Annotated[CohereRerankingService | None, Depends(get_reranker)],
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    httpx_client: Annotated[AsyncClient, Depends(get_httpx_client)],
    filter_query: Annotated[dict[str, Any], Depends(get_query_from_params)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GenerativeQAResponse:
    """Answer the query given the context with a generative model.
    \f

    Parameters
    ----------
    request
        Body of the request sent to the server.
    rts
        Retrieval service.
    qas
        Question_answering service to generate the answer based on the retrieved documents.
    rs
        Reranker service.
    ds_client
        Document store client.
    httpx_client
        Httpx async client to send external requests.
    filter_query
        Filtering query for paragraph retrieval.
    settings
        Global settings of the application

    Returns
    -------
        A single answer with metadata of each relevant source.
    """  # noqa: D301, D400, D205
    start = time.time()
    logger.info("Finding answers ...")

    contexts = await rts.arun(
        ds_client=ds_client,
        query=request.query,
        retriever_k=request.retriever_k,
        db_filter=filter_query,
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

    if rs is None or not request.use_reranker:
        contexts_text = [context["text"] for context in contexts]
        indices = tuple(range(len(contexts_text)))
        scores = None

    else:
        try:
            contexts, contexts_text, scores, indices = await rs.rerank(
                query=request.query,
                contexts=contexts,
                reranker_k=request.reranker_k,
            )
        except TooManyRequestsError:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": ErrorCode.MAX_COHERE_REQUESTS.value,
                    "detail": (
                        "Max number of requests reached for Cohere reranker. Wait a"
                        " little bit and try again, or disable the reranker."
                    ),
                },
            )

    metadata_retriever = MetaDataRetriever(
        external_apis=settings.metadata.external_apis
    )
    metadata_retriever.schedule_bulk_request(
        qas.arun,  # type: ignore
        **{
            "query": request.query,
            "contexts": contexts_text,
            "prompt_template": settings.generative.prompt_template.get_secret_value(),
        },
    )
    try:
        fetched_metadata = await metadata_retriever.retrieve_metadata(
            contexts,
            ds_client,
            settings.db.index_journals,
            settings.db.index_paragraphs,
            httpx_client,
        )
    except BadRequestError as err:
        raise HTTPException(
            status_code=413,
            detail={
                "code": ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value,
                "detail": err.body["message"],  # type: ignore
            },
        )

    answer, finish_reason = fetched_metadata["arun"]

    if finish_reason == "length":
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.INCOMPLETE_ANSWER.value,
                "detail": (
                    "The LLM did not have enough completion tokens available to finish"
                    " its answer. Please decrease the reranker_k or retriever_k value"
                    " by 1 or 2 depending of whether you are using the reranker or not."
                ),
                "raw_answer": answer["raw_answer"],
            },
        )

    if answer["paragraphs"] is None or len(answer["paragraphs"]) == 0:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.NO_ANSWER_FOUND.value,
                "detail": "The LLM did not provide any source to answer the question.",
                "raw_answer": answer["raw_answer"],
            },
        )
    else:
        citedby_counts = fetched_metadata.get("get_citation_count", {})
        journal_names = fetched_metadata.get("get_journal_name", {})
        impact_factors = fetched_metadata["get_impact_factors"]
        abstracts = fetched_metadata["recreate_abstract"]

        context_ids: list[int] = answer["paragraphs"]
        logger.info("Adding article metadata to the answers")
        metadata = []
        for context_id in context_ids:
            context = contexts[context_id]

            metadata.append(
                ParagraphMetadata(
                    **{
                        "impact_factor": impact_factors[context.get("journal")],
                        "journal_name": journal_names.get(context.get("journal")),
                        "journal_issn": context.get("journal"),
                        "date": context.get("date"),
                        "cited_by": citedby_counts.get(context.get("doi")),
                        "article_id": context["article_id"],
                        "ds_document_id": str(context["document_id"]),
                        "context_id": indices[context_id],
                        "reranking_score": (
                            scores[context_id] if scores is not None else None
                        ),
                        "article_doi": context["doi"],
                        "article_title": context["title"],
                        "article_authors": context["authors"],
                        "article_type": context["article_type"],
                        "section": context["section"],
                        "paragraph": context["text"],
                        "abstract": abstracts[context.get("article_id")],
                        "pubmed_id": context["pubmed_id"],
                    }
                )
            )
        answer["metadata"] = metadata

    del answer["paragraphs"]
    logger.info(f"Total time to generate a complete answer: {time.time() - start}")
    return GenerativeQAResponse(**answer)


@router.post(
    "/streamed_generative",
    response_model=GenerativeQAResponse,
    responses={
        500: {
            "description": (
                f"If code={ErrorCode.NO_DB_ENTRIES.value}, no relevant context is found"
                f" in the database. If code={ErrorCode.NO_ANSWER_FOUND.value}, no"
                " answer is found by the LLM from the extracted contexts."
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
                }
            },
        },
        413: {
            "description": (
                f"If code={ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value}, max number of"
                " token reached for the generative model -> Reduce retriever_k."
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
                }
            },
        },
    },
)
async def streamed_generative_qa(
    request: GenerativeQARequest,
    rts: Annotated[RetrievalService, Depends(get_rts)],
    qas: Annotated[GenerativeQAWithSources, Depends(get_generative_qas)],
    rs: Annotated[CohereRerankingService | None, Depends(get_reranker)],
    ds_client: Annotated[AsyncBaseSearch, Depends(get_ds_client)],
    filter_query: Annotated[dict[str, Any], Depends(get_query_from_params)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Answer the query given the context with a generative model.
    \f

    Parameters
    ----------
    request
        Body of the request sent to the server.
    rts
        Semantic_search_service for the retrieval.
    qas
        Question_answering service to generate the answer based on the retrieved documents.
    rs
        Reranker service.
    ds_client
        Document store client.
    filter_query
        Filtering query for paragraph retrieval.
    settings
        Global settings of the application

    Returns
    -------
        A single answer with metadata of each relevant source.
    """  # noqa: D301, D400, D205
    start = time.time()
    logger.info("Finding answers ...")

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

    if rs is None or not request.use_reranker:
        contexts_text = [context["text"] for context in contexts]
        indices = tuple(range(len(contexts_text)))
        scores = None
    else:
        contexts, contexts_text, scores, indices = await rs.rerank(
            query=request.query,
            contexts=contexts,
            reranker_k=request.reranker_k,
        )

    metadata_retriever = MetaDataRetriever(
        external_apis=settings.metadata.external_apis
    )

    return StreamingResponse(
        stream_response(
            qas=qas,
            query=request.query,
            contexts_text=contexts_text,
            metadata_retriever=metadata_retriever,
            settings=settings,
            contexts=contexts,
            indices=indices,
            scores=scores,
            ds_client=ds_client,
            index_journals=settings.db.index_journals,
            index_paragraphs=settings.db.index_paragraphs,
        ),
        media_type="text/event-stream",
    )
