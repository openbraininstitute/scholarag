"""Custom middleware implementation."""

import datetime
import hashlib
import json
import logging
import time
from functools import cache
from typing import Any, Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from scholarag import __version__
from scholarag.app.config import Settings
from scholarag.app.dependencies import get_httpx_client, get_settings, get_user_id

logger = logging.getLogger(__name__)


@cache
def get_cache(settings: Settings) -> "AsyncRedis[Any] | None":
    """Load the cache client to cache requests."""
    if not settings.redis.host or not settings.redis.port:
        logger.warning("Redis url or port not set.")
        return None
    host = settings.redis.host
    if host.startswith("http://"):
        host = host[7:]
    r = Redis(host=host, port=settings.redis.port, decode_responses=True)
    r_async = AsyncRedis(host=host, port=settings.redis.port, decode_responses=True)
    try:
        # The connection goes through regardless, and an error is raised only after the first redis call.
        r.ping()
        logger.info("The caching service is enabled.")
    except RedisConnectionError:
        logger.info("The caching service is disabled.")
        r_async = None  # type: ignore
    return r_async


def select_relevant_settings(settings: Settings, path: str) -> list[str]:
    """Return relevant setting for hashing depending on endpoint selected."""
    # No need to deep copy it, since only one of the if/elif will be accessed.
    db_settings = [
        settings.db.db_type,
        settings.db.index_paragraphs,
        str(settings.db.index_journals),
        str(settings.db.user),
    ]
    if "/suggestions/" in path:
        # Take all db settings.
        relevant_settings_suggestions = db_settings
        return relevant_settings_suggestions

    elif "/qa/" in path:
        # Start with the DB settings.
        relevant_settings_qa = db_settings
        # Add retrieval settings.
        if "generative" in path:
            relevant_settings_qa.extend(
                [
                    str(settings.generative.openai.model),
                    str(settings.generative.openai.temperature),
                ]
            )
        relevant_settings_qa.append(str(settings.metadata.external_apis))

        return relevant_settings_qa

    elif "/retrieval/" in path:
        # Relevant for all retrieval endpoints.
        relevant_settings_retrieval = db_settings
        if path == "/retrieval/":
            # Add raw retrieval endpoint.
            relevant_settings_retrieval.append(str(settings.metadata.external_apis))
        return relevant_settings_retrieval

    else:
        # Ideally should never happen. Please append this function whenever a new enpoint is created.
        logger.warning(
            "Endpoint not recognized to generate the hash. Consider adding it to the"
            " function 'select_relevant_settings'."
        )
        return [settings.model_dump_json()]


async def custom_key_builder(
    request: Request, settings: Settings, version: str, user: str
) -> str:
    """Build the unique caching key based on the request and the settings.

    Parameters
    ----------
    request
        Request sent by the user.
    settings
        Settings of the app at the moment of sending the request.
    version
        Version of the API.

    Returns
    -------
    key: Unique key used for caching.
    """
    relevant_settings = select_relevant_settings(settings, request.scope["path"])
    request_body = await request.body()
    cache_key = hashlib.md5(
        f"{version}:{request.query_params}:{request_body.decode('utf-8')}:{':'.join(relevant_settings)}:{user}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    return f"{request.scope['path']}:{cache_key}"


async def strip_path_prefix(
    request: Request, call_next: Callable[[Any], Any]
) -> Response:
    """Optionally strip a prefix from a request path.

    Parameters
    ----------
    request
        Request sent by the user.
    call_next
        Function executed to get the output of the endpoint.

    Returns
    -------
    response: Response of the request after potentially stripping prefix from path and applying other middlewares
    """
    if request.base_url in (
        "http://testserver/",
        "http://test/",
    ) and "healthz" not in str(request.url):
        settings = request.app.dependency_overrides[get_settings]()
    else:
        settings = get_settings()
    prefix = settings.misc.application_prefix
    if prefix is not None and len(prefix) > 0 and request.url.path.startswith(prefix):
        new_path = request.url.path[len(prefix) :]
        scope = request.scope
        scope["path"] = new_path
        request = Request(scope, request.receive)
    return await call_next(request)


async def get_and_set_cache(
    request: Request, call_next: Callable[[Any], Any]
) -> Response:
    """Use caching for the requests.

    Parameters
    ----------
    request
        Request sent by the user.
    call_next
        Function executed to get the output of the endpoint.

    Returns
    -------
    response: Response of the request, potentially from the cache and with added headers.
    """
    # Specify here which endpoints should be cached.
    to_cache = [
        "/qa/generative",
        "/qa/streamed_generative",
        "/retrieval/article_count",
        "/retrieval/article_listing",
        "/retrieval/",
        "/suggestions/journal",
        "/suggestions/author",
    ]
    to_secure = [
        *to_cache,
        "/qa/passthrough",
        "/suggestions/article_types",
    ]
    if request.scope["path"] not in to_secure:
        response = await call_next(request)
        return response

    if request.base_url in ("http://testserver/", "http://test/"):
        settings = request.app.dependency_overrides[get_settings]()
    else:
        settings = get_settings()

    token = request.headers.get("Authorization")
    if token:
        token = token.rpartition(" ")[-1]
    httpx_client = await anext(get_httpx_client(settings))
    # If raises HTTPException return error as json.
    try:
        user = await get_user_id(
            token=token, settings=settings, httpx_client=httpx_client
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=e.detail)

    if request.scope["path"] not in to_cache:
        response = await call_next(request)
        return response

    start = time.time()

    redis = get_cache(settings)

    # If no caching, run as usual.
    if not redis:
        response = await call_next(request)
        return response

    request_key = await custom_key_builder(
        request=request, settings=settings, version=__version__, user=user
    )

    # If the key exists in the db, return its result.
    if await redis.exists(request_key) and request.headers.get("cache-control") not in (
        "no-cache",
        "no-store",
    ):
        response = await redis.get(request_key)
        ttl = await redis.ttl(request_key)
        mapping = json.loads(response)
        mapping["content"] = json.dumps(mapping["content"])
        mapping.pop("state")
        mapping["headers"]["X-fastapi-cache"] = "Hit"
        mapping["headers"]["cache-control"] = f"max-age={ttl}s"
        mapping["headers"]["expires"] = (
            datetime.datetime.now() + datetime.timedelta(seconds=ttl)
        ).strftime(r"%d/%m/%Y, %H:%M:%S")
        mapping["headers"]["content-length"] = str(len(mapping["content"]))
        logger.info(
            f"Found cached request. cached request took {time.time() - start}s to"
            " complete."
        )
        return Response(**mapping)

    else:
        response = await call_next(request)
        if request.headers.get("cache-control") not in ("no-cache", "no-store"):
            # One cannot directly get the body, it is an async iterator.
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Prepare the response and add the headers.
            response = {
                "content": body.decode("utf-8"),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
            }
            response["headers"]["X-fastapi-cache"] = "Miss"

            request_body = await request.body()
            cached = {
                **response,
                "state": {
                    "request_body": (
                        json.loads(request_body.decode("utf-8")) if request_body else ""
                    ),
                    "settings": json.loads(
                        settings.model_dump_json()
                    ),  # To avoid secrets being 'unjsonable'
                    "version": __version__,
                    "path": request.scope["path"],
                    "user_sub": user,
                },
            }
            cached["content"] = cached["content"].split("<bbs_json_error>")[-1]
            cached["content"] = cached["content"].split("<bbs_json_data>")[-1]

            cached["content"] = json.loads(cached["content"])

            sec_time = datetime.timedelta(days=settings.redis.expiry)

            # Cache the response unless specified otherwise.
            await redis.set(request_key, json.dumps(cached), ex=sec_time)
            logger.info(f"Stored request in cache with key {request_key}")

            return Response(**response)
        else:
            return response
