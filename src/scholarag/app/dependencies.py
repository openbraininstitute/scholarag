"""Injectable dependencies for endpoints."""

import json
import logging
from enum import Enum
from functools import cache
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPBearer
from httpx import AsyncClient, HTTPStatusError
from openai import AsyncOpenAI
from pydantic import constr
from starlette.status import HTTP_401_UNAUTHORIZED

from scholarag.app.config import Settings
from scholarag.document_stores import (
    AsyncBaseSearch,
    AsyncElasticSearch,
    AsyncOpenSearch,
)
from scholarag.generative_question_answering import GenerativeQAWithSources
from scholarag.services import CohereRerankingService, RetrievalService

logger = logging.getLogger(__name__)

journal_constraints = constr(pattern=r"^\d{4}-\d{3}[0-9X]$")


class HTTPBearerDirect(HTTPBearer):
    """HTTPBearer class that returns directly the token in the call."""

    async def __call__(self, request: Request) -> str | None:  # type: ignore
        """Intercept the bearer token in the headers."""
        auth_credentials = await super().__call__(request)
        return auth_credentials.credentials if auth_credentials else None


auth = HTTPBearerDirect(auto_error=False)


@cache
def get_settings() -> Settings:
    """Load all parameters.

    Note that this function is cached and environment will be read just once.
    """
    logger.info("Reading the environment and instantiating settings")
    return Settings()


async def get_httpx_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncClient]:
    """Manage the httpx client for the request."""
    client = AsyncClient(timeout=settings.metadata.timeout, verify=False)
    try:
        yield client
    finally:
        await client.aclose()


async def get_user_id(
    request: Request,
    token: Annotated[str, Depends(auth)],
    settings: Annotated[Settings, Depends(get_settings)],
    httpx_client: Annotated[AsyncClient, Depends(get_httpx_client)],
) -> str:
    """Validate JWT token and returns user ID."""
    if hasattr(request.state, "sub"):
        return request.state.sub
    if settings.keycloak.validate_token:
        if settings.keycloak.user_info_endpoint:
            try:
                response = await httpx_client.get(
                    settings.keycloak.user_info_endpoint,
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                user_info = response.json()
                return user_info["sub"]
            except HTTPStatusError:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
                )
        else:
            raise HTTPException(status_code=404, detail="user info url not provided.")
    else:
        return "dev"


def get_rts(settings: Annotated[Settings, Depends(get_settings)]) -> RetrievalService:
    """Get the retrieval service."""
    return RetrievalService(db_index_paragraphs=settings.db.index_paragraphs)


async def get_ds_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncBaseSearch]:
    """Get the Elasticsearch client."""
    try:
        if settings.db.password is None:
            password = None
        else:
            password = settings.db.password.get_secret_value()

        if settings.db.db_type == "elasticsearch":
            ds_client = AsyncElasticSearch(  # type: ignore
                host=settings.db.host,
                port=settings.db.port,
                user=settings.db.user,
                password=password,
            )
            yield ds_client
        else:
            ds_client = AsyncOpenSearch(  # type: ignore
                host=settings.db.host,
                port=settings.db.port,
                user=settings.db.user,
                password=password,
                use_ssl_and_verify_certs=False,
            )
            yield ds_client
    finally:
        await ds_client.close()


async def get_openai_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncOpenAI]:
    """Get async openai client for passthrough endpoint."""
    if settings.generative.openai.token:
        openai_client = AsyncOpenAI(
            api_key=settings.generative.openai.token.get_secret_value()
        )
    else:
        raise HTTPException(
            status_code=500,
            detail={
                "code": ErrorCode.ENDPOINT_INACTIVE.value,
                "detail": "Couldn't connect to openai.",
            },
        )
    yield openai_client
    await openai_client.close()


def get_generative_qas(
    settings: Annotated[Settings, Depends(get_settings)],
    openai_client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
) -> GenerativeQAWithSources:
    """Get the generative question answering service."""
    return GenerativeQAWithSources(
        client=openai_client,
        model=settings.generative.openai.model,
        temperature=settings.generative.openai.temperature,
        max_tokens=settings.generative.openai.max_tokens,
    )


async def get_reranker(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[CohereRerankingService | None]:
    """Get the reranking service."""
    if settings.reranking.cohere_token:
        reranker = CohereRerankingService(  # type: ignore
            api_key=settings.reranking.cohere_token.get_secret_value()
        )
    else:
        logger.warning(
            "The reranker is requested but the Cohere API key is not specified."
        )
        reranker = None
    yield reranker


def get_query_from_params(
    article_types: Annotated[
        list[str] | None, Query(description="Article types allowed. OR matching")
    ] = None,
    authors: Annotated[
        list[str] | None, Query(description="List of authors. OR matching.")
    ] = None,
    journals: Annotated[  # type: ignore
        list[journal_constraints] | None,
        Query(
            description="List of journal issn. OR matching. Format: XXXX-XXXX",
        ),
    ] = None,
    date_from: Annotated[
        str | None,
        Query(
            description="Date lowerbound. Includes specified date. Format: YYYY-MM-DD",
            pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        ),
    ] = None,
    date_to: Annotated[
        str | None,
        Query(
            description="Date upperbound. Includes specified date. Format: YYYY-MM-DD",
            pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        ),
    ] = None,
) -> dict[str, dict[str, list[dict[str, Any]]]] | None:
    """Get the query parameters and generate an ES query for filtering."""
    query: dict[str, dict[str, list[dict[str, Any]]]] = {"bool": {"must": []}}
    if article_types:
        query["bool"]["must"].append({"terms": {"article_type": article_types}})
    if authors:
        query["bool"]["must"].append({"terms": {"authors.keyword": authors}})
    if journals:
        query["bool"]["must"].append({"terms": {"journal": journals}})
    if date_from:
        query["bool"]["must"].append({"range": {"date": {"gte": date_from}}})
    if date_to:
        query["bool"]["must"].append({"range": {"date": {"lte": date_to}}})

    logger.info(f"Searching the database with the query {json.dumps(query)}.")
    return None if not query["bool"]["must"] else query


class ErrorCode(Enum):
    """ErrorCode class to be used when an error code has to be raised.

    Append new entries everytime a new error code is created.
    """

    NO_DB_ENTRIES = 1  # Has an HTTPS status code 500, since it is related to a problem in the backend.
    NO_ANSWER_FOUND = 2  # Has an HTTPS status code 500, since it is related to a problem in the backend.
    ENDPOINT_INACTIVE = 3  # Has an HTTPS status code 500, since it is related to a problem in the backend.
    INPUT_EXCEEDED_MAX_TOKENS = 4  # Has an HTTPS status code 413, since it happens when the inputs are too large.
    MAX_COHERE_REQUESTS = 5  # Has an HTTPS status code 500, since it is related to a problem in the backend.
    INCOMPLETE_ANSWER = 6  # Has an HTTPS status code 500, since it is related to a problem in the backend.
    ALREADY_EXISTS_IN_DB = 7
