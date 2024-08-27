"""FastAPI for the Scholarag SDK."""

import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig
from typing import Annotated, Any, AsyncContextManager
from uuid import uuid4

import sentry_sdk
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from fastapi_pagination.utils import disable_installed_extensions_check
from starlette.middleware.base import BaseHTTPMiddleware

from scholarag import __version__
from scholarag.app.config import Settings
from scholarag.app.dependencies import get_settings
from scholarag.app.middleware import get_and_set_cache, get_cache, strip_path_prefix
from scholarag.app.routers import qa, retrieval, suggestions

stry = sentry_sdk.init(
    release=__version__,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": "asgi_correlation_id.CorrelationIdFilter",
            "uuid_length": 32,
            "default_value": "-",
        },
    },
    "formatters": {
        "request_id": {
            "class": "logging.Formatter",
            "format": (
                "[%(levelname)s] %(asctime)s (%(correlation_id)s) %(name)s %(message)s"
            ),
        },
    },
    "handlers": {
        "request_id": {
            "class": "logging.StreamHandler",
            "filters": ["correlation_id"],
            "formatter": "request_id",
        },
    },
    "loggers": {
        "": {
            "handlers": ["request_id"],
            "level": "INFO",
            "propagate": True,
        },
    },
}
dictConfig(LOGGING)

logger = logging.getLogger(__name__)


@asynccontextmanager  # type: ignore
async def lifespan(fastapi_app: FastAPI) -> AsyncContextManager[None]:  # type: ignore
    """Read environment (settings of the application)."""
    # hacky but works: https://github.com/tiangolo/fastapi/issues/425
    app_settings = fastapi_app.dependency_overrides.get(get_settings, get_settings)()

    prefix = app_settings.misc.application_prefix
    fastapi_app.openapi_url = f"{prefix}/openapi.json"
    fastapi_app.servers = [{"url": prefix}]
    # Do not rely on the middleware order in the list "fastapi_app.user_middleware" since this is subject to changes.
    try:
        cors_middleware = filter(
            lambda x: x.__dict__["cls"] == CORSMiddleware, fastapi_app.user_middleware
        ).__next__()
        cors_middleware.kwargs["allow_origins"] = (
            app_settings.misc.cors_origins.replace(" ", "").split(",")
        )
    except StopIteration:
        pass

    get_cache(app_settings)

    logging.getLogger().setLevel(app_settings.logging.external_packages.upper())
    logging.getLogger("scholarag").setLevel(app_settings.logging.level.upper())
    logging.getLogger("app").setLevel(app_settings.logging.level.upper())

    yield


app = FastAPI(
    title="Literature search",
    summary="API for answering scientific questions",
    version=__version__,
    swagger_ui_parameters={"tryItOutEnabled": True},
    lifespan=lifespan,
)

app.include_router(suggestions.router)
app.include_router(qa.router)
app.include_router(retrieval.router)
app.add_middleware(BaseHTTPMiddleware, dispatch=get_and_set_cache)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http:\/\/localhost:(\d+)\/?.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Request-ID",
    update_request_header=True,
    generator=lambda: uuid4().hex,
    transformer=lambda a: a,
)
app.add_middleware(BaseHTTPMiddleware, dispatch=strip_path_prefix)

# fastapi_pagination settings
disable_installed_extensions_check()
add_pagination(app)


@app.get("/healthz")
def healthz() -> str:
    """Check the health of the API."""
    return "200"


@app.get("/")
def readyz() -> dict[str, str]:
    """Check if the API is ready to accept traffic."""
    return {"status": "ok"}


@app.get("/settings")
def settings(settings: Annotated[Settings, Depends(get_settings)]) -> Any:
    """Show complete settings of the backend.

    Did not add return model since it pollutes the Swagger UI.
    """
    return settings
