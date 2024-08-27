"""Tests for the suggestions endpoints.""" ""
import pytest
from httpx import ASGITransport, AsyncClient
from scholarag.app.config import Settings
from scholarag.app.dependencies import ErrorCode, get_ds_client, get_settings
from scholarag.app.main import app

from app.dependencies_overrides import override_ds_client


def test_article_type(app_client):
    """Test the author suggestion endpoint."""
    fake_client = override_ds_client()
    fake_client.search.side_effect = lambda **kwargs: {
        "aggregations": {
            "article_types": {
                "doc_count_error_upper_bound": 0,
                "sum_other_doc_count": 0,
                "buckets": [
                    {"key": "Journal Article", "doc_count": 2696605},
                    {"key": "Case Reports", "doc_count": 88556},
                    {"key": "Systematic Review", "doc_count": 19163},
                    {"key": "Randomized Controlled Trial", "doc_count": 14225},
                    {"key": "English Abstract", "doc_count": 12426},
                    {"key": "Meta-Analysis", "doc_count": 11736},
                    {"key": "Review", "doc_count": 9192},
                    {"key": "Clinical Trial Protocol", "doc_count": 9132},
                    {"key": "Observational Study", "doc_count": 8658},
                    {"key": "Clinical Trial", "doc_count": 7431},
                    {"key": " Clinical Trial", "doc_count": 13},
                    {"key": "Journal Article ", "doc_count": 23},
                    {"key": " Case Reports ", "doc_count": 55},
                ],
            }
        }
    }

    response = app_client.get(
        "/suggestions/article_types",
    )
    expected = [
        {"article_type": "Journal Article", "docs_in_db": 2696628},
        {"article_type": "Case Reports", "docs_in_db": 88611},
        {"article_type": "Systematic Review", "docs_in_db": 19163},
        {"article_type": "Randomized Controlled Trial", "docs_in_db": 14225},
        {"article_type": "English Abstract", "docs_in_db": 12426},
        {"article_type": "Meta-Analysis", "docs_in_db": 11736},
        {"article_type": "Review", "docs_in_db": 9192},
        {"article_type": "Clinical Trial Protocol", "docs_in_db": 9132},
        {"article_type": "Observational Study", "docs_in_db": 8658},
        {"article_type": "Clinical Trial", "docs_in_db": 7444},
    ]
    assert response.status_code == 200

    response_body = response.json()
    assert len(response_body) == 10

    expected_keys = {"article_type", "docs_in_db"}
    for response, expect in zip(response_body, expected):
        assert set(response.keys()) == expected_keys
        assert response["article_type"] == expect["article_type"]
        assert response["docs_in_db"] == expect["docs_in_db"]


def test_author_suggestion(app_client):
    """Test the author suggestion endpoint."""
    fake_client = override_ds_client()
    fake_client.search.side_effect = lambda **kwargs: {
        "took": 2206,
        "timed_out": False,
        "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 10000, "relation": "gte"},
            "max_score": 1.0,
            "hits": [
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "f9c06ecaadd026799f6251d46201ed11",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Ming-Jun Zhang",
                            "Li-Zi Yin",
                            "Da-Cheng Wang",
                            "Xu-Ming Deng",
                            "Jing-Bo Liu",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "bc056b1e142f6294c526c69d026fafac",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Ming-Jun Zhang",
                            "Li-Zi Yin",
                            "Da-Cheng Wang",
                            "Xu-Ming Deng",
                            "Jing-Bo Liu",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "6e1dcef007e6e47a5f958d1c7a805a76",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Ming-Jun Zhang",
                            "Li-Zi Yin",
                            "Da-Cheng Wang",
                            "Xu-Ming Deng",
                            "Jing-Bo Liu",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "3fa1fc25decaaea40d9cbe792efb0e4b",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Latha Kumari",
                            "WZ Li",
                            "Shrinivas Kulkarni",
                            "KH Wu",
                            "Wei Chen",
                            "Chunlei Wang",
                            "Charles H Vannoy",
                            "Roger M Leblanc",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "5817cd6f1c1ab1b69248a48a43ba3b82",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Latha Kumari",
                            "WZ Li",
                            "Shrinivas Kulkarni",
                            "KH Wu",
                            "Wei Chen",
                            "Chunlei Wang",
                            "Charles H Vannoy",
                            "Roger M Leblanc",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "b7503a446b1469ed2ca50f0c2d8ec8c1",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Latha Kumari",
                            "WZ Li",
                            "Shrinivas Kulkarni",
                            "KH Wu",
                            "Wei Chen",
                            "Chunlei Wang",
                            "Charles H Vannoy",
                            "Roger M Leblanc",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "e664892645785632138e16f3378c52a3",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Christin Bexelius",
                            "Johan Lundberg",
                            "Xuan Wang",
                            "Jenny Berg",
                            "Hans Hjelm",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "7092191ad76ce4eef8a3f9f2c5f6bdcb",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Christin Bexelius",
                            "Johan Lundberg",
                            "Xuan Wang",
                            "Jenny Berg",
                            "Hans Hjelm",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "6dc8d3a0b4158715c5ca7676a9fc5d76",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Christin Bexelius",
                            "Johan Lundberg",
                            "Xuan Wang",
                            "Jenny Berg",
                            "Hans Hjelm",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "732a1d7d7aead59080ad3809e44a6211",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Christin Bexelius",
                            "Johan Lundberg",
                            "Xuan Wang",
                            "Jenny Berg",
                            "Hans Hjelm",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "2432a21426fdea20e0660df9dca89555",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Jingliang Su",
                            "Shuang Li",
                            "Xudong Hu",
                            "Xiuling Yu",
                            "Yongyue Wang",
                            "Peipei Liu",
                            "Xishan Lu",
                            "Guozhong Zhang",
                            "Xueying Hu",
                            "Di Liu",
                            "Xiaoxia Li",
                            "Wenliang Su",
                            "Hao Lu",
                            "Ngai Shing Mok",
                            "Peiyi Wang",
                            "Ming Wang",
                            "Kegong Tian",
                            "George F. Gao",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "4b50a2b4330979d964b27acbb0740dab",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Mitsuru Sato",
                            "Takeya Sato",
                            "Naosuke Kojima",
                            "Katsuyuki Imai",
                            "Nobuyo Higashi",
                            "Da-Ren Wang",
                            "Haruki Senoo",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "a4e583e86ab521410bd1ae68312c2c25",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Jingliang Su",
                            "Shuang Li",
                            "Xudong Hu",
                            "Xiuling Yu",
                            "Yongyue Wang",
                            "Peipei Liu",
                            "Xishan Lu",
                            "Guozhong Zhang",
                            "Xueying Hu",
                            "Di Liu",
                            "Xiaoxia Li",
                            "Wenliang Su",
                            "Hao Lu",
                            "Ngai Shing Mok",
                            "Peiyi Wang",
                            "Ming Wang",
                            "Kegong Tian",
                            "George F. Gao",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "5931437612b534ef42347ec4c7eb099f",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Jingliang Su",
                            "Shuang Li",
                            "Xudong Hu",
                            "Xiuling Yu",
                            "Yongyue Wang",
                            "Peipei Liu",
                            "Xishan Lu",
                            "Guozhong Zhang",
                            "Xueying Hu",
                            "Di Liu",
                            "Xiaoxia Li",
                            "Wenliang Su",
                            "Hao Lu",
                            "Ngai Shing Mok",
                            "Peiyi Wang",
                            "Ming Wang",
                            "Kegong Tian",
                            "George F. Gao",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "da2473dad8990ba4df829d7a2e573064",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Youxin Zhou",
                            "Fang Liu",
                            "Qinian Xu",
                            "Xiuyun Wang",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "f112f36ece4e8ecacca038f405cdc98a",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "Youxin Zhou",
                            "Fang Liu",
                            "Qinian Xu",
                            "Xiuyun Wang",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "37d9b17668ba6a700c804514bc5b509d",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "X.F. Wang",
                            "Qi Yang",
                            "Zhaozhi Fan",
                            "Chang-Kai Sun",
                            "Guang H. Yue",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "1bd9d41f59a205f08572fb4a435c8045",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "X.F. Wang",
                            "Qi Yang",
                            "Zhaozhi Fan",
                            "Chang-Kai Sun",
                            "Guang H. Yue",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "199b2f2c1b32a8258adeb694ffe5dc7e",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "X.F. Wang",
                            "Qi Yang",
                            "Zhaozhi Fan",
                            "Chang-Kai Sun",
                            "Guang H. Yue",
                        ]
                    },
                },
                {
                    "_index": "pmc_paragraphs2",
                    "_id": "d7640bc6958b60b2833fd03278f62988",
                    "_score": 1.0,
                    "_source": {
                        "authors": [
                            "X.F. Wang",
                            "Qi Yang",
                            "Zhaozhi Fan",
                            "Chang-Kai Sun",
                            "Guang H. Yue",
                        ]
                    },
                },
            ],
        },
    }

    response = app_client.get(
        "/suggestions/author",
        params={"name": "wang", "limit": 2},
    )

    expected = [{"name": "Da-Cheng Wang"}, {"name": "Chunlei Wang"}]
    assert response.status_code == 200

    response_body = response.json()
    assert len(response_body) == 2

    for response, expect in zip(response_body, expected):
        assert response["name"] == expect["name"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keywords,expected_results",
    [
        ("aaa bbb", [{"eissn": "9101-1121", "print_issn": None}]),
        (
            "aa",
            [
                {"eissn": "1234-5679 1234-5679", "print_issn": "0234-5679 0234-5679"},
                {"eissn": "1234-5678", "print_issn": "1234-5678"},
                {"eissn": "9101-1121", "print_issn": None},
                {"eissn": "1234-5679", "print_issn": "0234-5679"},
            ],
        ),
    ],
)
async def test_journal_suggestion(
    get_testing_async_ds_client, keywords, expected_results
):
    """Test the journal suggestion endpoint."""
    ds_client, parameters = get_testing_async_ds_client

    test_settings = Settings(
        db={
            "db_type": (
                "elasticsearch"
                if "ElasticSearch" in ds_client.__class__.__name__
                else "opensearch"
            ),
            "index_paragraphs": "bar",
            "index_journals": "test_paragraphs",
            "host": "host.com",
            "port": 1515,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc,
        settings=parameters[-1],
        mappings={
            "properties": {
                "CiteScore": {"type": "float"},
                "E-ISSN": {"type": "keyword"},
                "Print ISSN": {"type": "keyword"},
                "SJR": {"type": "float"},
                "SNIP": {"type": "float"},
                "Title": {"type": "text"},
            }
        },
    )
    doc_bulk = [
        {
            "_index": index_doc,
            "_id": 1,
            "_source": {
                "Title": "aaa bbb",
                "CiteScore": 2.0,
                "E-ISSN": "91011121",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": None,
            },
        },
        {
            "_index": index_doc,
            "_id": 2,
            "_source": {
                "Title": "aaa",
                "CiteScore": 3.0,
                "E-ISSN": "12345678",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": "12345678",
            },
        },
        {
            "_index": index_doc,
            "_id": 3,
            "_source": {
                "Title": "aaa b",
                "CiteScore": 1.0,
                "E-ISSN": "12345679",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": "2345679",
            },
        },
        {
            "_index": index_doc,
            "_id": 4,
            "_source": {
                "Title": "aaa ccc",
                "CiteScore": 4.0,
                "E-ISSN": "12345679 12345679",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": "2345679 2345679",
            },
        },
    ]
    await ds_client.bulk(doc_bulk)
    await ds_client.client.indices.refresh()
    app.dependency_overrides[get_ds_client] = lambda: ds_client

    limit = 1 if keywords == "aaa bbb" else 4
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get(
            "/suggestions/journal",
            params={"keywords": keywords, "limit": limit},
        )

    assert response.status_code == 200

    response_body = response.json()
    assert len(response_body) == len(expected_results)

    expected_keys = {"title", "citescore", "eissn", "snip", "sjr", "print_issn"}

    for d, expected_result in zip(response_body, expected_results):
        assert set(d.keys()) == expected_keys
        assert d["eissn"] == expected_result["eissn"]
        assert d["print_issn"] == expected_result["print_issn"]


def test_journal_suggestion_without_index(app_client):
    override_ds_client()

    # create settings and do not provide index_journals
    fake_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "host": "http://host.com",
            "port": 1515,
        },
    )
    app.dependency_overrides[get_settings] = lambda: fake_settings

    response = app_client.get(
        "/suggestions/journal",
        params={"keywords": "blabla"},
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == ErrorCode.ENDPOINT_INACTIVE.value


@pytest.mark.asyncio
async def test_journal_duplicates(get_testing_async_ds_client):
    """Test the journal suggestion endpoint."""
    ds_client, parameters = get_testing_async_ds_client

    test_settings = Settings(
        db={
            "db_type": (
                "elasticsearch"
                if "ElasticSearch" in ds_client.__class__.__name__
                else "opensearch"
            ),
            "index_paragraphs": "bar",
            "index_journals": "test_paragraphs",
            "host": "host.com",
            "port": 1515,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc,
        settings=parameters[-1],
        mappings={
            "properties": {
                "CiteScore": {"type": "float"},
                "E-ISSN": {"type": "keyword"},
                "Print ISSN": {"type": "keyword"},
                "SJR": {"type": "float"},
                "SNIP": {"type": "float"},
                "Title": {"type": "text"},
            }
        },
    )
    doc_bulk = [
        {
            "_index": index_doc,
            "_id": 1,
            "_source": {
                "Title": "aaa",
                "CiteScore": 4.0,
                "E-ISSN": "91011121",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": None,
            },
        },
        {
            "_index": index_doc,
            "_id": 2,
            "_source": {
                "Title": "aaa",
                "CiteScore": 3.0,
                "E-ISSN": "12345678",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": "12345678",
            },
        },
        {
            "_index": index_doc,
            "_id": 3,
            "_source": {
                "Title": "aaa b",
                "CiteScore": 2.0,
                "E-ISSN": "12345679",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": "2345679",
            },
        },
        {
            "_index": index_doc,
            "_id": 4,
            "_source": {
                "Title": "aaa ccc",
                "CiteScore": 1.0,
                "E-ISSN": "12345679 12345679",
                "SNIP": None,
                "SJR": None,
                "Print ISSN": "2345679 2345679",
            },
        },
    ]
    await ds_client.bulk(doc_bulk)
    await ds_client.client.indices.refresh()
    app.dependency_overrides[get_ds_client] = lambda: ds_client

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        response = await http_client.get(
            "/suggestions/journal",
            params={"keywords": "aaa", "limit": 2},
        )

    assert response.status_code == 200

    response_body = response.json()
    assert len(response_body) == 2

    expected_results = [
        {"eissn": "9101-1121", "print_issn": None},
        {"eissn": "1234-5679", "print_issn": "0234-5679"},
    ]
    expected_keys = {"title", "citescore", "eissn", "snip", "sjr", "print_issn"}

    for d, expected_result in zip(response_body, expected_results):
        assert set(d.keys()) == expected_keys
        assert d["eissn"] == expected_result["eissn"]
        assert d["print_issn"] == expected_result["print_issn"]
