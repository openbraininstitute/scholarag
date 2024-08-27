import pytest
from fastapi.exceptions import HTTPException
from httpx import AsyncClient
from openai import AsyncOpenAI
from scholarag.app.dependencies import (
    Settings,
    get_ds_client,
    get_generative_qas,
    get_query_from_params,
    get_reranker,
    get_rts,
    get_user_id,
)
from scholarag.document_stores import AsyncElasticSearch, AsyncOpenSearch
from scholarag.generative_question_answering import GenerativeQAWithSources
from scholarag.services import CohereRerankingService


@pytest.mark.parametrize(
    "db_type,db_class",
    [("elasticsearch", AsyncElasticSearch), ("opensearch", AsyncOpenSearch)],
)
@pytest.mark.asyncio
async def test_get_ds_client(db_type, db_class, monkeypatch):
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", db_type)
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "dummy")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://localhost")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9200")
    monkeypatch.setenv("SCHOLARAG__DB__USER", "user")
    monkeypatch.setenv("SCHOLARAG__DB__PASSWORD", "password")

    settings = Settings()

    async for ds_client in get_ds_client(settings):
        assert isinstance(ds_client, db_class)
        assert (
            ds_client.host == "http://localhost"
            if db_type == "elasticsearch"
            else "localhost"
        )
        assert ds_client.port == 9200
        assert ds_client.user == "user"


@pytest.mark.asyncio
async def test_get_user_id(httpx_mock, monkeypatch):
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "elasticsearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "dummy")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://localhost")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9200")
    monkeypatch.setenv("SCHOLARAG__KEYCLOAK__ISSUER", "https://great_issuer.com")
    monkeypatch.setenv("SCHOLARAG__KEYCLOAK__VALIDATE_TOKEN", "True")

    fake_response = {
        "sub": "12345",
        "email_verified": False,
        "name": "Machine Learning Test User",
        "groups": [],
        "preferred_username": "sbo-ml",
        "given_name": "Machine Learning",
        "family_name": "Test User",
        "email": "email@epfl.ch",
    }
    httpx_mock.add_response(
        url="https://great_issuer.com/protocol/openid-connect/userinfo",
        json=fake_response,
    )

    settings = Settings()
    client = AsyncClient()
    token = "eyJgreattoken"
    user = await get_user_id(token=token, settings=settings, httpx_client=client)

    assert user == "12345"


@pytest.mark.asyncio
async def test_get_user_id_error(httpx_mock, monkeypatch):
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "elasticsearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "dummy")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://localhost")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9200")
    monkeypatch.setenv("SCHOLARAG__KEYCLOAK__ISSUER", "https://great_issuer.com")
    monkeypatch.setenv("SCHOLARAG__KEYCLOAK__VALIDATE_TOKEN", "True")

    httpx_mock.add_response(
        url="https://great_issuer.com/protocol/openid-connect/userinfo",
        status_code=401,
    )

    settings = Settings()
    client = AsyncClient()
    token = "eyJgreattoken"

    with pytest.raises(HTTPException) as err:
        await get_user_id(token=token, settings=settings, httpx_client=client)

    assert err.value.status_code == 401
    assert err.value.detail == "Invalid token."


def test_get_rts(monkeypatch):
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "elasticsearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "dummy")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://localhost")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9200")

    settings = Settings()

    rts = get_rts(settings)
    assert rts.db_index_paragraphs == "dummy"


def test_get_generative_qas_openai(monkeypatch):
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "elasticsearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "dummy")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://localhost")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9200")
    monkeypatch.setenv("SCHOLARAG__GENERATIVE__OPENAI__TOKEN", "dummy")
    monkeypatch.setenv("SCHOLARAG__GENERATIVE__OPENAI__MODEL", "dummy")
    monkeypatch.setenv("SCHOLARAG__GENERATIVE__OPENAI__TEMPERATURE", "99")
    monkeypatch.setenv("SCHOLARAG__GENERATIVE__OPENAI__MAX_TOKENS", "99")

    settings = Settings()
    openai_client = AsyncOpenAI(api_key="aasas")

    qas = get_generative_qas(settings, openai_client)

    assert isinstance(qas, GenerativeQAWithSources)
    assert qas.model == "dummy"
    assert qas.temperature == 99
    assert qas.max_tokens == 99


@pytest.mark.asyncio
async def test_get_reranker_cohere(monkeypatch):
    monkeypatch.setenv("SCHOLARAG__DB__DB_TYPE", "elasticsearch")
    monkeypatch.setenv("SCHOLARAG__DB__INDEX_PARAGRAPHS", "dummy")
    monkeypatch.setenv("SCHOLARAG__DB__HOST", "http://localhost")
    monkeypatch.setenv("SCHOLARAG__DB__PORT", "9200")
    monkeypatch.setenv("SCHOLARAG__RERANKING__COHERE_TOKEN", "blabla")

    settings = Settings()

    reranker = await anext(get_reranker(settings=settings))
    assert isinstance(reranker, CohereRerankingService)
    assert reranker.api_key == "blabla"

    monkeypatch.delenv("SCHOLARAG__RERANKING__COHERE_TOKEN")

    settings = Settings()

    reranker = await anext(get_reranker(settings=settings))
    assert not reranker


def test_get_query_from_params():
    topics = ["pyramidal cells", "retina"]
    regions = ["brain region", "thalamus"]
    article_types = ["publication", "review"]
    authors = ["Guy Manderson", "Joe Guy"]
    journals = ["1111-1111"]
    date_from = "2020-01-01"
    date_to = "2020-01-02"

    expected = {
        "bool": {
            "must": [
                {
                    "query_string": {
                        "default_field": "text",
                        "query": (
                            "((pyramidal AND cells) AND retina) AND ((brain AND region)"
                            " OR thalamus)"
                        ),
                    }
                },
                {"terms": {"article_type": ["publication", "review"]}},
                {"terms": {"authors": ["Guy Manderson", "Joe Guy"]}},
                {"terms": {"journal": ["1111-1111"]}},
                {"range": {"date": {"gte": "2020-01-01"}}},
                {"range": {"date": {"lte": "2020-01-02"}}},
            ]
        }
    }

    query = get_query_from_params(
        topics=topics,
        regions=regions,
        article_types=article_types,
        authors=authors,
        journals=journals,
        date_from=date_from,
        date_to=date_to,
    )

    assert query == expected
