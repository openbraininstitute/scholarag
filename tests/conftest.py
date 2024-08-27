"""Pytest configuration file."""

import asyncio
import functools
import logging
import os
import random
import socket
import string
import threading
import time
from itertools import chain
from unittest.mock import patch

import aiobotocore
import aiohttp
import moto.server
import pytest
import pytest_asyncio
import sentry_sdk
import werkzeug.serving
from aiobotocore.config import AioConfig
from fastapi.testclient import TestClient
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError as RedisConnectionError
from scholarag.app.config import Settings
from scholarag.app.dependencies import get_settings
from scholarag.app.main import app
from scholarag.document_stores import (
    AsyncElasticSearch,
    AsyncOpenSearch,
    ElasticSearch,
    OpenSearch,
)
from scholarag.document_stores.elastic import (
    MAPPINGS_PARAGRAPHS as ELASTICSEARCH_MAPPINGS_PARAGRAPHS,
)
from scholarag.document_stores.elastic import SETTINGS as ELASTICSEARCH_SETTINGS
from scholarag.document_stores.open import (
    MAPPINGS_PARAGRAPHS as OPENSEARCH_MAPPINGS_PARAGRAPHS,
)
from scholarag.document_stores.open import SETTINGS as OPENSEARCH_SETTINGS


@pytest.fixture(params=["elasticsearch", "opensearch"])
def get_testing_ds_client(request):
    """Fixture to get a client."""
    # docker run -e discovery.type=single-node -e xpack.security.enabled=false
    # -p 9201:9200 -p 9300:9300 -it
    # docker.elastic.co/elasticsearch/elasticsearch:8.7.1

    # docker run -p 9200:9200 -it  opensearchproject/opensearch:2.5.0
    # -Ediscovery.type=single-node -Eplugins.security.disabled=true
    doc_store = request.param
    host = "http://localhost" if doc_store == "elasticsearch" else "localhost"
    port = 9201 if doc_store == "elasticsearch" else 9200
    kwargs = {"host": host, "port": port, "use_ssl_and_verify_certs": False}

    try:
        ds_client = (
            ElasticSearch(**kwargs)
            if doc_store == "elasticsearch"
            else OpenSearch(**kwargs)
        )
        if not ds_client.client.ping():
            raise RuntimeError("Could not connect to the document store.")
    except (RuntimeError, AttributeError):
        ds_client = None

    if doc_store == "elasticsearch":
        parameters = (
            ELASTICSEARCH_MAPPINGS_PARAGRAPHS,
            ELASTICSEARCH_SETTINGS,
        )
    elif doc_store == "opensearch":
        parameters = (
            OPENSEARCH_MAPPINGS_PARAGRAPHS,
            OPENSEARCH_SETTINGS,
        )

    if ds_client is None:
        pytest.skip("Document store is not available")

    yield ds_client, parameters

    if ds_client is not None:
        for index in ds_client.get_available_indexes():
            if index in [
                "test_pu_consumer",
                "test_articles",
                "test_paragraphs",
                "test_index",
                "test_impact_factors",
                "test_impact_factor1",
                "articles_parse_script_pytest",
                "paragraphs_parse_script_pytest",
                "check_docs_in_db",
            ]:
                ds_client.remove_index(index)
                ds_client.client.indices.refresh()
        ds_client.client.close()


@pytest_asyncio.fixture(params=["elasticsearch", "opensearch"])
async def get_testing_async_ds_client(request):
    """Fixture to get an async document store."""
    doc_store = request.param
    host = "http://localhost" if doc_store == "elasticsearch" else "localhost"
    port = 9201 if doc_store == "elasticsearch" else 9200
    kwargs = {"host": host, "port": port, "use_ssl_and_verify_certs": False}

    try:
        ds_client = (
            AsyncElasticSearch(**kwargs)
            if doc_store == "elasticsearch"
            else AsyncOpenSearch(**kwargs)
        )
        ping = await ds_client.client.ping()
        if not ping:
            raise RuntimeError("Could not connect to the document store.")
    except (RuntimeError, AttributeError):
        ds_client = None

    if doc_store == "elasticsearch":
        parameters = (
            ELASTICSEARCH_MAPPINGS_PARAGRAPHS,
            ELASTICSEARCH_SETTINGS,
        )
    elif doc_store == "opensearch":
        parameters = (
            OPENSEARCH_MAPPINGS_PARAGRAPHS,
            OPENSEARCH_SETTINGS,
        )

    if ds_client is None:
        pytest.skip("Document store is not available")

    yield ds_client, parameters

    if ds_client is not None:
        for index in await ds_client.get_available_indexes():
            if index in [
                "test_articles",
                "test_paragraphs",
                "test_index",
                "articles_parse_script_pytest",
                "paragraphs_parse_script_pytest",
                "paragraphs_ds_upload",
                "check_docs_in_db",
            ]:
                await ds_client.remove_index(index)
                await ds_client.client.indices.refresh()
        await ds_client.close()


@pytest.fixture(name="app_client")
def client_fixture():
    """Get client and clear app dependency_overrides."""
    app_client = TestClient(app)
    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
        generative={"openai": {"token": "asas"}},
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield app_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True, scope="session")
def dont_look_at_env_file():
    """Never look inside of the .env when running unit tests."""
    Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True, scope="function")
def disable_sentry(monkeypatch):
    """Disable sentry for all tests."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    sentry_sdk.init()  # https://github.com/getsentry/sentry-python/issues/660


@pytest.fixture()
def mock_http_calls(httpx_mock, non_mocked_hosts):
    httpx_mock.add_response(
        url="https://portal.issn.org/resource/ISSN/1234-5678",
        method="GET",
        text="great journal",  # Won't actually get returned because the 'get_journal_name' function
        # has a complex parsing logic. See test_retrieve_metadata.py.
    )
    httpx_mock.add_response(
        url="https://api.semanticscholar.org/graph/v1/paper/ID12345?fields=citationCount",
        method="GET",
        json={"citationCount": 2},
    )
    non_mocked_hosts.append("testserver")
    non_mocked_hosts.append("test")
    with (
        patch("scholarag.retrieve_metadata.recreate_abstract") as abstract,
        patch("scholarag.retrieve_metadata.get_impact_factors") as impact,
    ):
        abstract.__name__ = "recreate_abstract"
        abstract.return_value = "Great abstract"
        impact.__name__ = "get_impact_factors"
        impact.return_value = {"1234-5678": 5.6}
        yield


@pytest.fixture()
def redis_fixture():
    """Get redis getter function.

    For some reason, one needs to have a different redis client for each
    request (not just for each test).

    """
    r = Redis(host="localhost", port=6380, decode_responses=True)

    try:
        r.ping()
    except RedisConnectionError:
        pytest.skip("Redis is not running")

    r.flushall()

    def get_redis(*args, **kwargs):
        return AsyncRedis(host="localhost", port=6380, decode_responses=True)

    yield get_redis

    r.flushall()


# Related to AWS
# Most code taken from aiobotocore tests.
host = "127.0.0.1"

_PYCHARM_HOSTED = os.environ.get("PYCHARM_HOSTED") == "1"
_CONNECT_TIMEOUT = 90 if _PYCHARM_HOSTED else 10


def moto_config(endpoint_url):
    kw = {
        "endpoint_url": endpoint_url,
        "aws_secret_access_key": "xxx",
        "aws_access_key_id": "xxx",
    }

    return kw


class DomainDispatcherApplication(moto.server.DomainDispatcherApplication):
    def __init__(self, create_app, service):
        super().__init__(create_app)
        self.service = service

    def get_backend_for_host(self, host):
        if self.service:
            return self.service

        return super().get_backend_for_host(host)


def get_free_tcp_port(release_socket: bool = False):
    sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sckt.bind((host, 0))
    addr, port = sckt.getsockname()
    if release_socket:
        sckt.close()
        return port

    return sckt, port


class MotoService:
    """Will Create MotoService.
    Service is ref-counted so there will only be one per process. Real Service will
    be returned by `__aenter__`."""

    _services = {}  # {name: instance}

    def __init__(self, service_name: str, port: int = None, ssl: bool = False):
        self._service_name = service_name

        if port:
            self._socket = None
            self._port = port
        else:
            self._socket, self._port = get_free_tcp_port()

        self._thread = None
        self._logger = logging.getLogger("MotoService")
        self._refcount = None
        self._ip_address = host
        self._server = None
        self._ssl_ctx = werkzeug.serving.generate_adhoc_ssl_context() if ssl else None
        self._schema = "http" if not self._ssl_ctx else "https"

    @property
    def endpoint_url(self):
        return f"{self._schema}://{self._ip_address}:{self._port}"

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            await self._start()
            try:
                result = await func(*args, **kwargs)
            finally:
                await self._stop()
            return result

        functools.update_wrapper(wrapper, func)
        wrapper.__wrapped__ = func
        return wrapper

    async def __aenter__(self):
        svc = self._services.get(self._service_name)
        if svc is None:
            self._services[self._service_name] = self
            self._refcount = 1
            await self._start()
            return self
        else:
            svc._refcount += 1
            return svc

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._refcount -= 1

        if self._socket:
            self._socket.close()
            self._socket = None

        if self._refcount == 0:
            del self._services[self._service_name]
            await self._stop()

    def _server_entry(self):
        self._main_app = DomainDispatcherApplication(
            moto.server.create_backend_app, service=self._service_name
        )
        self._main_app.debug = True

        if self._socket:
            self._socket.close()  # release right before we use it
            self._socket = None

        self._server = werkzeug.serving.make_server(
            self._ip_address,
            self._port,
            self._main_app,
            True,
            ssl_context=self._ssl_ctx,
        )
        self._server.serve_forever()

    async def _start(self):
        self._thread = threading.Thread(target=self._server_entry, daemon=True)
        self._thread.start()

        async with aiohttp.ClientSession() as session:
            start = time.time()

            while time.time() - start < 20:
                if not self._thread.is_alive():
                    break

                try:
                    # we need to bypass the proxies due to monkeypatches
                    async with session.get(
                        self.endpoint_url + "/static",
                        timeout=_CONNECT_TIMEOUT,
                        ssl=False,
                    ):
                        pass
                    break
                except (asyncio.TimeoutError, aiohttp.ClientConnectionError):
                    await asyncio.sleep(0.5)
            else:
                await self._stop()  # pytest.fail doesn't call stop_process
                raise Exception(f"Can not start service: {self._service_name}")

    async def _stop(self):
        if self._server:
            self._server.shutdown()

        self._thread.join()


@pytest.fixture
def server_scheme():
    return "http"


@pytest.fixture
def region():
    return "us-east-1"


@pytest.fixture
async def s3_server(server_scheme):
    async with MotoService("s3", ssl=server_scheme == "https") as svc:
        yield svc.endpoint_url


@pytest.fixture
async def sqs_server(server_scheme):
    async with MotoService("sqs", ssl=server_scheme == "https") as svc:
        yield svc.endpoint_url


@pytest.fixture
def s3_verify():
    return None


@pytest.fixture
def signature_version():
    return "s3"


@pytest.fixture
def mocking_test():
    # change this flag for test with real aws
    # TODO: this should be merged with pytest.mark.moto
    return True


@pytest.fixture
def config(request, region, signature_version):
    config_kwargs = request.node.get_closest_marker("config_kwargs") or {}
    connect_timeout = read_timout = 5
    if _PYCHARM_HOSTED:
        connect_timeout = read_timout = 180

    return AioConfig(
        region_name=region,
        signature_version=signature_version,
        read_timeout=read_timout,
        connect_timeout=connect_timeout,
        **config_kwargs,
    )


@pytest.fixture
def session():
    session = aiobotocore.session.AioSession()
    return session


@pytest.fixture
async def sqs_client(session, region, config, sqs_server, mocking_test):
    kw = moto_config(sqs_server) if mocking_test else {}
    async with session.create_client(
        "sqs", region_name=region, config=config, **kw
    ) as client:
        yield client


@pytest.fixture
async def s3_client(
    session,
    region,
    config,
    s3_server,
    mocking_test,
    s3_verify,
):
    # This depends on mock_attributes because we may want to test event listeners.
    # See the documentation of `mock_attributes` for details.
    kw = moto_config(s3_server) if mocking_test else {}

    async with session.create_client(
        "s3", region_name=region, config=config, verify=s3_verify, **kw
    ) as client:
        yield client


def assert_status_code(response, status_code):
    assert response["ResponseMetadata"]["HTTPStatusCode"] == status_code


async def recursive_delete(s3_client, bucket_name):
    # Recursively deletes a bucket and all of its contents.
    paginator = s3_client.get_paginator("list_object_versions")
    async for n in paginator.paginate(Bucket=bucket_name, Prefix=""):
        for obj in chain(
            n.get("Versions", []),
            n.get("DeleteMarkers", []),
            n.get("Contents", []),
            n.get("CommonPrefixes", []),
        ):
            kwargs = {"Bucket": bucket_name, "Key": obj["Key"]}
            if "VersionId" in obj:
                kwargs["VersionId"] = obj["VersionId"]
            resp = await s3_client.delete_object(**kwargs)
            assert_status_code(resp, 204)

    resp = await s3_client.delete_bucket(Bucket=bucket_name)
    assert_status_code(resp, 204)


@pytest.fixture
async def create_bucket(s3_client):
    _bucket_name = None

    async def _f(bucket_name=None):
        nonlocal _bucket_name
        if bucket_name is None:
            bucket_name = "".join(random.sample(string.ascii_lowercase, k=26))
        _bucket_name = bucket_name
        response = await s3_client.create_bucket(Bucket=bucket_name)
        assert_status_code(response, 200)
        return bucket_name

    try:
        yield _f
    finally:
        await recursive_delete(s3_client, _bucket_name)


@pytest.fixture
async def bucket_name(region, create_bucket):
    name = await create_bucket()
    yield name


@pytest.fixture
def create_object(s3_client, bucket_name):
    async def _f(key_name, body="foo"):
        r = await s3_client.put_object(Bucket=bucket_name, Key=key_name, Body=body)
        assert_status_code(r, 200)
        return r

    return _f


@pytest.fixture
async def sqs_queue_url(sqs_client):
    response = await sqs_client.create_queue(
        QueueName="".join(random.sample(string.ascii_lowercase, k=26))
    )
    queue_url = response["QueueUrl"]
    assert_status_code(response, 200)

    try:
        yield queue_url
    finally:
        response = await sqs_client.delete_queue(QueueUrl=queue_url)
        assert_status_code(response, 200)
