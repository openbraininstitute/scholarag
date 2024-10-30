from datetime import datetime
from itertools import product

import pytest
from httpx import ASGITransport, AsyncClient
from scholarag.app.config import Settings
from scholarag.app.dependencies import get_ds_client, get_settings
from scholarag.app.main import app
from scholarag.app.schemas import ArticleMetadata, ParagraphMetadata

from app.dependencies_overrides import (
    override_ds_client,
    override_reranker,
    override_rts,
)


@pytest.mark.parametrize("retriever_k", [1, 2, 3])
def test_retrieval(app_client, retriever_k, mock_http_calls):
    """Test the retrieval endpoint."""
    override_ds_client()
    fake_rts, _ = override_rts(has_context=True)

    params = {
        "regions": ["thalamus", "Giant Hippopotamidae"],
        "journals": ["1234-5678"],
        "date_to": "2022-12-31",
        "query": "aaa",
        "retriever_k": retriever_k,
    }
    expected_query = {
        "bool": {
            "must": [
                {
                    "query_string": {
                        "default_field": "text",
                        "query": "(thalamus OR (Giant AND Hippopotamidae))",
                    }
                },
                {"terms": {"journal": params["journals"]}},
                {"range": {"date": {"lte": params["date_to"]}}},
            ]
        }
    }

    response = app_client.get(
        "/retrieval",
        params=params,
    )
    assert response.status_code == 200
    used_query = fake_rts.arun.await_args.kwargs["db_filter"]
    assert used_query == expected_query

    response_body = response.json()
    assert len(response_body) == retriever_k
    expected_keys = set(ParagraphMetadata.model_json_schema()["properties"].keys())

    for d in response_body:
        assert set(d.keys()) == expected_keys


@pytest.mark.parametrize("reranker_k", [1, 2, 3])
def test_retrieval_reranker(app_client, reranker_k, mock_http_calls):
    """Test the retrieval endpoint."""
    override_ds_client()
    _ = override_rts(has_context=True)
    _, sorted_scores_index = override_reranker(reranker_k=reranker_k)

    response = app_client.get(
        "/retrieval",
        params={
            "query": "aaa",
            "retriever_k": 10,
            "use_reranker": True,
            "reranker_k": reranker_k,
        },
    )

    assert response.status_code == 200

    response_body = response.json()
    assert len(response_body) == reranker_k
    expected_keys = set(ParagraphMetadata.model_json_schema()["properties"].keys())

    for d in response_body:
        assert set(d.keys()) == expected_keys

    for resp, expected in zip(response.json(), sorted_scores_index):
        assert resp["reranking_score"] == expected[0]
        assert int(resp["context_id"]) == expected[-1]


def test_retrieval_no_answer_code_1(app_client):
    """Test the retrieval endpoint when there is no context retrieved (code 1)."""
    override_ds_client()
    override_rts(has_context=False)

    response = app_client.get(
        "/retrieval",
        params={"query": "aaa", "retriever_k": 5},
    )

    response_body = response.json()

    assert response.status_code == 500
    assert response_body["detail"].keys() == {"code", "detail"}
    assert response_body["detail"]["code"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topics,regions,date_from,date_to,result",
    [
        (["1"], ["2"], None, None, 1),
        (["1"], ["1"], None, None, 10),
        (["1", "2"], ["3"], None, None, 0),
        (["1"], ["3", "4"], None, None, 2),
        (["1", "2"], ["3", "4"], None, None, 0),
        (None, ["3", "4"], None, None, 11),
        (["3", "4"], None, None, None, 1),
        (None, ["3 4"], None, None, 1),
        (None, None, None, None, 19),
        (None, None, "2022-12-01", None, 5),
        (None, None, None, "2022-01-01", 6),
        (None, None, "2022-03-01", "2022-06-01", 17),
    ],
)
async def test_article_count(
    get_testing_async_ds_client, topics, regions, date_from, date_to, result
):
    ds_client, parameters = get_testing_async_ds_client
    test_settings = Settings(
        db={
            "db_type": (
                "elasticsearch"
                if "ElasticSearch" in ds_client.__class__.__name__
                else "opensearch"
            ),
            "index_paragraphs": "test_paragraphs",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )
    doc_bulk = [
        {
            "_index": index_doc,
            "_id": i,
            "_source": {
                "text": f"Numbers used to test filtered article count: {n1} {n2}",
                "title": "test_article",
                "paragraph_id": str(i),
                "article_id": n1 + n2,  # 19 unique articles.
                "journal": "8765-4321",
                "date": datetime(2022, i % 12 + 1, 1).strftime("%Y-%m-%d"),
            },
        }
        for i, (n1, n2) in enumerate(product(range(10), range(10)))
    ]  # size 100
    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()
    app.dependency_overrides[get_ds_client] = lambda: ds_client

    params = {}
    if topics:
        params["topics"] = topics
    if regions:
        params["regions"] = regions
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get(
            "/retrieval/article_count",
            params=params,
        )
    response = response.json()
    assert response["article_count"] == result


@pytest.mark.asyncio
@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
async def test_article_listing(get_testing_async_ds_client, mock_http_calls):
    ds_client, parameters = get_testing_async_ds_client

    test_settings = Settings(
        db={
            "db_type": (
                "elasticsearch"
                if "ElasticSearch" in ds_client.__class__.__name__
                else "opensearch"
            ),
            "index_paragraphs": "test_paragraphs",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )
    doc_bulk = [
        {
            "_index": index_doc,
            "_id": i,
            "_source": {
                "text": (
                    f"Great paragraph, it is paragraph number {' '.join(list(str(i)))}"
                ),
                "title": "test_article",
                "paragraph_id": str(i),
                "article_id": str(i % 60),  # 60 unique articles to test duplicates.
                "journal": "1234-5678",
                "doi": "ID12345",
                "pubmed_id": "PM1234",
                "authors": ["Nikemicsjanba"],
                "article_type": "code",
                "section": "abstract",
                "date": datetime(2022, i % 12 + 1, 1).strftime("%Y-%m-%d"),
            },
        }
        for i in range(100)
    ]
    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()
    app.dependency_overrides[get_ds_client] = lambda: ds_client

    # Test the keyword search.
    params = {
        "number_results": 10,
        "topics": ["6 1"],
    }  # Should return article 16 and 1 (61 in text).

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get("/retrieval/article_listing", params=params)

    assert response.status_code == 200
    response = response.json()

    assert sorted([resp["article_id"] for resp in response["items"]]) == ["1", "16"]
    expected_keys = set(ArticleMetadata.model_json_schema()["properties"].keys())
    for d in response["items"]:
        assert set(d.keys()) == expected_keys

    # Test the matching by score
    params = {
        "number_results": 20,
        "topics": ["6"],
        "regions": ["1", "5"],
    }  # Article 16 and 1 should score higher. still includes 56 and 65.

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get("/retrieval/article_listing", params=params)

    assert response.status_code == 200
    response = response.json()

    assert len(response["items"]) == 4
    assert sorted([resp["article_id"] for resp in response["items"][:2]]) == [
        "1",
        "16",
    ]  # They contain 1 and 6 in the text, they should score higher.
    for d in response["items"]:
        assert set(d.keys()) == expected_keys

    # Test limiting results
    params = {"number_results": 10, "regions": ["6", "1"]}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get("/retrieval/article_listing", params=params)

    assert response.status_code == 200
    response = response.json()

    assert len(response["items"]) == 10
    for d in response["items"]:
        assert set(d.keys()) == expected_keys

    params = {
        "number_results": 10,
        "topics": ["7 1"],
        "date_from": "2022-07-01",
    }  # Should return article 11.

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get("/retrieval/article_listing", params=params)

    assert response.status_code == 200
    response = response.json()

    assert sorted([resp["article_id"] for resp in response["items"]]) == ["11"]
    expected_keys = set(ArticleMetadata.model_json_schema()["properties"].keys())
    for d in response["items"]:
        assert set(d.keys()) == expected_keys

    params = {
        "number_results": 10,
        "topics": ["7 1"],
        "date_to": "2022-07-01",
    }  # Should return article 17.

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get("/retrieval/article_listing", params=params)

    assert response.status_code == 200
    response = response.json()

    assert sorted([resp["article_id"] for resp in response["items"]]) == ["17"]
    expected_keys = set(ArticleMetadata.model_json_schema()["properties"].keys())
    for d in response["items"]:
        assert set(d.keys()) == expected_keys


@pytest.mark.asyncio
async def test_article_listing_by_date(get_testing_async_ds_client, request):
    ds_client, parameters = get_testing_async_ds_client

    request.getfixturevalue("mock_http_calls")
    test_settings = Settings(
        db={
            "db_type": (
                "elasticsearch"
                if "ElasticSearch" in ds_client.__class__.__name__
                else "opensearch"
            ),
            "index_paragraphs": "test_paragraphs",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )
    doc_bulk = [
        {
            "_index": index_doc,
            "_id": i,
            "_source": {
                "text": (
                    f"Great paragraph, it is paragraph number {' '.join(list(str(i)))}"
                ),
                "title": "test_article",
                "paragraph_id": str(i),
                "article_id": str(i % 60),  # 60 unique articles to test duplicates.
                "journal": "1234-5678",
                "doi": "ID12345",
                "pubmed_id": "PM1234",
                "authors": ["Nikemicsjanba"],
                "article_type": "code",
                "section": "abstract",
                "date": datetime(2022, i % 12 + 1, 1).strftime("%Y-%m-%d"),
            },
        }
        for i in range(12)
    ]
    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()
    app.dependency_overrides[get_ds_client] = lambda: ds_client

    params = {"number_results": 50, "sort_by_date": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get("/retrieval/article_listing", params=params)
    response = response.json()
    expected_dates = sorted(
        [datetime.strptime(doc["_source"]["date"], "%Y-%m-%d") for doc in doc_bulk],
        reverse=True,
    )
    dates = [datetime.strptime(doc["date"], "%Y-%m-%d") for doc in response["items"]]
    assert dates == expected_dates
