from datetime import datetime
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from fastapi import HTTPException
from fastapi.requests import Request
from fastapi.responses import Response
from scholarag.app.config import Settings
from scholarag.app.dependencies import get_settings
from scholarag.app.main import app
from scholarag.app.middleware import (
    custom_key_builder,
    get_and_set_cache,
    get_cache,
    select_relevant_settings,
    strip_path_prefix,
)
from starlette.datastructures import MutableHeaders
from starlette.status import HTTP_401_UNAUTHORIZED
from starlette.types import Message

from app.dependencies_overrides import override_ds_client_with_redis, override_rts


def test_get_cache():
    settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
    )
    r_async = get_cache(settings)
    assert r_async is None


async def set_body(request: Request, body: bytes):
    async def receive() -> Message:
        return {"type": "http.request", "body": body}

    request._receive = receive


@pytest.mark.asyncio
async def test_key_builder():
    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        }
    )
    user = "test"
    app.dependency_overrides[get_settings] = lambda: test_settings
    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "test/",
        }
    )
    await set_body(request, b"Amazing body")
    key_1 = await custom_key_builder(request, test_settings, version="0.8.0", user=user)

    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "test/",
        }
    )

    await set_body(request, b"An even better body")
    key_2 = await custom_key_builder(request, test_settings, version="0.8.0", user=user)

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "test_paragraphs",
            "index_journals": "bazzzz",
            "host": "host.com",
            "port": 1515,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    key_3 = await custom_key_builder(request, test_settings, version="0.8.0", user=user)
    assert key_1 != key_2
    assert key_2 != key_3
    assert key_1 != key_3


@pytest.mark.parametrize("path", ["/suggestions/", "/qa/", "/retrieval/"])
def test_select_relevant_settings(path):
    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        }
    )
    relevant_settings = select_relevant_settings(test_settings, path)
    for s in relevant_settings:
        assert isinstance(s, str)

    if path == "/suggestions/":
        expected_list = ["elasticsearch", "foo", "bar", "None"]
        assert expected_list == relevant_settings

    elif path == "/qa/":
        expected_list = [
            "elasticsearch",
            "foo",
            "bar",
            "None",
            "True",
        ]
        assert expected_list == relevant_settings

    elif path == "/retrieval/":
        expected_list = [
            "elasticsearch",
            "foo",
            "bar",
            "None",
            "True",
        ]
        assert expected_list == relevant_settings

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
        metadata={
            "external_apis": False,
        },
    )
    relevant_settings = select_relevant_settings(test_settings, path)
    for s in relevant_settings:
        assert isinstance(s, str)

    if path in {"/qa/", "/retrieval/"}:
        assert "False" in relevant_settings


@pytest.mark.asyncio
async def test_get_and_set_cache_without_cache():
    # Request GET
    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "test/",
            "method": "GET",
        },
    )

    fake_callable = AsyncMock(return_value="test")

    response = await get_and_set_cache(request, fake_callable)
    assert response == "test"

    # Request POST - no caching
    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "test/",
            "method": "POST",
            "headers": {},
        },
    )

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
    )
    with patch("scholarag.app.middleware.get_settings", lambda: test_settings):
        response = await get_and_set_cache(request, fake_callable)
        assert response == "test"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_body",
    [
        '{"body": "chunk"}',
        'notcached<bbs_json_error>{"body": "chunk"}',
        '<bbs_json_error>{"body": "chunk"}',
        '<bbs_json_data>{"body": "chunk"}',
    ],
)
async def test_get_and_set_cache_with_cache_key_not_in_db(response_body):
    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "/suggestions/journal",
            "method": "POST",
            "headers": {},
        },
    )

    body = """{"param": "This is request param"}""".encode("utf-8")

    async def get_request_body():
        return body

    request.body = get_request_body

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
    )

    redis_mock = AsyncMock()
    redis_mock.exists.return_value = False

    async def get_body_iterator():
        for chunk in response_body:
            yield chunk.encode()

    fake_callable = AsyncMock()
    response_mock = AsyncMock()
    type(response_mock).body_iterator = PropertyMock(return_value=get_body_iterator())
    type(response_mock).status_code = PropertyMock(return_value=200)
    type(response_mock).headers = PropertyMock(return_value=MutableHeaders())
    type(response_mock).media_type = PropertyMock(return_value=None)

    fake_callable.return_value = response_mock

    with (
        patch("scholarag.app.middleware.get_settings", lambda: test_settings),
        patch("scholarag.app.middleware.get_cache", lambda settings: redis_mock),
    ):
        response = await get_and_set_cache(request, fake_callable)

    assert isinstance(response, Response)

    # Test headers
    expected_headers = {
        ("x-fastapi-cache", "Miss"),
        ("content-length", str(len(response_body))),
    }

    response_headers = response.headers.items()
    assert set(response_headers) == expected_headers

    # Test body
    assert response.body.decode() == response_body

    # Test redis
    redis_mock.exists.assert_called_once()
    redis_mock.set.assert_called_once()
    # check function used when key is in db are not called
    redis_mock.get.assert_not_called()
    redis_mock.ttl.assert_not_called()


@pytest.mark.asyncio
async def test_get_and_set_cache_with_cache_key_in_db():
    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "/suggestions/journal",
            "method": "POST",
            "headers": {},
        },
    )

    body = b"""body"""

    async def get_request_body():
        return body

    request.body = get_request_body

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
    )

    redis_mock = AsyncMock()
    redis_mock.exists.return_value = True
    redis_mock.get.return_value = '{"content": "body", "state": "fake", "headers": {}}'
    redis_mock.ttl.return_value = 30
    fake_callable = AsyncMock(return_value="test")

    expected_headers = {
        ("x-fastapi-cache", "Hit"),
        ("cache-control", "max-age=30s"),
        ("content-length", "6"),
    }
    with (
        patch("scholarag.app.middleware.get_settings", lambda: test_settings),
        patch("scholarag.app.middleware.get_cache", lambda settings: redis_mock),
    ):
        response = await get_and_set_cache(request, fake_callable)

    assert isinstance(response, Response)

    # Test headers
    response_headers = response.headers.items()
    assert len(response_headers) == 4

    for header in expected_headers:
        assert header in response_headers

    found = False
    for header in response_headers:
        if header[0] == "expires":
            found = True
            assert isinstance(
                datetime.strptime(header[1], r"%d/%m/%Y, %H:%M:%S"), datetime
            )

    assert found

    # Test redis
    redis_mock.exists.assert_called_once()
    redis_mock.get.assert_called_once()
    redis_mock.ttl.assert_called_once()
    # Test that function when key not in db are not called
    redis_mock.set.assert_not_called()


@pytest.mark.parametrize(
    "path,prefix,trimmed_path",
    [
        ("/suggestions", "", "/suggestions"),
        ("/literature/suggestions", "/literature", "/suggestions"),
    ],
)
@pytest.mark.asyncio
async def test_strip_path_prefix(path, prefix, trimmed_path):
    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
        misc={"application_prefix": prefix},
    )

    scope = {
        "type": "http",
        "path": path,
        "query_string": b"best_query_string_i_have_ever_seen,_woah",
        "method": "POST",
        "headers": [
            (b"host", b"example.com"),
        ],
        "scheme": "http",
        "server": ("example.com", 80),
    }

    request = Request(scope=scope)

    async def async_callable(request):
        return Response(content=request.url.path, media_type="text/plain")

    with patch("scholarag.app.middleware.get_settings", lambda: test_settings):
        response = await strip_path_prefix(request, async_callable)

    assert response.body.decode("utf-8") == trimmed_path


@pytest.mark.asyncio
async def test_get_and_set_cache_chatbot():
    request = Request(
        scope={
            "type": "http",
            "query_string": "Best query string I have ever seen, woah.",
            "path": "/chatbot/chat/1",
            "method": "POST",
            "headers": {},
        },
    )

    body = b"""body"""

    async def get_request_body():
        return body

    request.body = get_request_body

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
    )

    redis_mock = AsyncMock()
    redis_mock.exists.return_value = True
    redis_mock.get.return_value = (
        '{"content": "cached_value", "state": "fake", "headers": {}}'
    )
    redis_mock.ttl.return_value = 30
    fake_response = AsyncMock(body=b'"not_cached_value"')
    fake_callable = AsyncMock(return_value=fake_response)

    with (
        patch("scholarag.app.middleware.get_settings", lambda: test_settings),
        patch("scholarag.app.middleware.get_cache", lambda settings: redis_mock),
    ):
        response = await get_and_set_cache(request, fake_callable)

    assert response.body != b'"cached_value"'


@pytest.mark.asyncio
async def test_caching_retrieval(app_client, redis_fixture, mock_http_calls):
    """Test caching is working for retrieval."""

    with patch("scholarag.app.middleware.get_cache", redis_fixture):
        override_ds_client_with_redis()
        override_rts()
        # First time to put in the cache
        response = app_client.get(
            "/retrieval/",
            params={"query": "aaa", "retriever_k": 4},
        )
        assert response.status_code == 200
        assert response.headers["X-fastapi-cache"] == "Miss"

        # Second time to read in the cache
        response2 = app_client.get(
            "/retrieval/",
            params={"query": "aaa", "retriever_k": 4},
        )
        assert response2.status_code == 200
        assert response2.headers["X-fastapi-cache"] == "Hit"
        assert response.json() == response2.json()


def test_caching_article_count(app_client, redis_fixture):
    """Test caching is working for article count."""
    fake_client = override_ds_client_with_redis()
    fake_client.search.side_effect = lambda **kwargs: {
        "aggregations": {"article_count": {"value": 10}}
    }

    with patch("scholarag.app.middleware.get_cache", redis_fixture):
        # First time to put in the cache
        response = app_client.get(
            "/retrieval/article_count",
        )

        assert response.json() == {"article_count": 10}
        assert response.headers["X-fastapi-cache"] == "Miss"

        # Second time to read in the cache
        response = app_client.get(
            "/retrieval/article_count",
        )
        assert response.json() == {"article_count": 10}
        assert response.headers["X-fastapi-cache"] == "Hit"


def test_caching_article_listing(app_client, redis_fixture, mock_http_calls):
    """Test caching is working for article listing."""
    fake_client = override_ds_client_with_redis()
    doc = {
        "title": "fake_title",
        "article_id": "12345",
        "doi": "ID12345",
        "pubmed_id": None,
        "authors": ["A", "B"],
        "article_type": "research",
        "journal": "1234-5678",
        "text": "This is a beautiful text",
    }
    fake_client.search.side_effect = lambda **kwargs: {
        "aggregations": {
            "relevant_ids": {
                "buckets": [{"ids_hit": {"hits": {"hits": [{"_source": doc}]}}}]
            }
        }
    }

    expected = {
        "items": [
            {
                "article_title": "fake_title",
                "article_authors": ["A", "B"],
                "article_id": "12345",
                "article_doi": "ID12345",
                "pubmed_id": None,
                "date": None,
                "article_type": "research",
                "journal_issn": "1234-5678",
                "journal_name": None,
                "cited_by": 2,
                "impact_factor": 5.6,
                "abstract": "Great abstract",
            }
        ],
        "total": 1,
        "page": 1,
        "size": 50,
        "pages": 1,
    }

    with patch("scholarag.app.middleware.get_cache", redis_fixture):
        # First time to put in the cache
        response = app_client.get(
            "/retrieval/article_listing",
        )

        assert response.json() == expected
        assert response.headers["X-fastapi-cache"] == "Miss"

        # Second time to read in the cache
        response = app_client.get(
            "/retrieval/article_listing",
        )
        assert response.json() == expected
        assert response.headers["X-fastapi-cache"] == "Hit"


def test_request_id(app_client):
    """Test that response contains request id in the headers."""
    override_ds_client_with_redis()
    response = app_client.get("/retrieval/article_listing")
    assert isinstance(response.headers["x-request-id"], str)
    assert len(response.headers["x-request-id"]) == 32


@pytest.mark.parametrize(
    "path",
    [
        "/qa/generative",
        "/qa/passthrough",
        "/qa/streamed_generative",
        "/suggestions/journal",
        "/suggestions/author",
        "/suggestions/article_types",
        "/retrieval/",
        "/retrieval/article_count",
        "/retrieval/article_listing",
    ],
)
@pytest.mark.asyncio
async def test_user_verification(monkeypatch, httpx_mock, path):
    monkeypatch.setenv("SCHOLARAG__KEYCLOAK__VALIDATE_TOKEN", "True")
    monkeypatch.setenv("SCHOLARAG__KEYCLOAK__ISSUER", "http://fake_issuer")
    httpx_mock.add_exception(
        exception=HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
        ),
        url="http://fake_issuer/protocol/openid-connect/userinfo",
    )

    request = Request(
        scope={
            "type": "http",
            "query_string": "Amazing question",
            "path": path,
            "method": "POST",
            "headers": {},
        },
    )

    fake_response = {"sub": "12345"}

    async def get_request_body():
        return b"""body"""

    request.body = get_request_body

    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
    )

    fake_callable = AsyncMock(return_value="test")

    with (
        patch("scholarag.app.middleware.get_settings", lambda: test_settings),
    ):
        # Test when the token is wrong.
        response = await get_and_set_cache(request, fake_callable)

        assert response.body == b'"Invalid token."'

        # Test when the token is valid.
        httpx_mock.add_response(
            json=fake_response,
            url="http://fake_issuer/protocol/openid-connect/userinfo",
        )
        response = await get_and_set_cache(request, fake_callable)

        assert response == "test"
