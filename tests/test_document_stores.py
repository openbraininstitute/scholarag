"""Tests for the document stores."""

import pytest
from scholarag.document_stores.elastic import postprocess_query


# Sync functions
def test_create_and_remove_index(get_testing_ds_client):
    """Test the creation and removal of an index."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert index in ds_client.get_available_indexes()

    ds_client.remove_index(index)

    assert index not in ds_client.get_available_indexes()

    # Errors
    with pytest.raises(RuntimeError):
        ds_client.remove_index("does-not-exists")


def test_create_index_already_exists(get_testing_ds_client):
    """Test create index that already exists."""
    ds_client, parameters = get_testing_ds_client
    index = "test_index"
    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    with pytest.raises(RuntimeError):
        ds_client.create_index(
            "test_index", settings=parameters[-1], mappings=parameters[0]
        )


def test_remove_index_error(get_testing_ds_client):
    """Test that we have runtime error when index does not exist."""
    ds_client, _ = get_testing_ds_client
    with pytest.raises(RuntimeError):
        ds_client.remove_index("does-not-exist")


def test_get_available_indexes(get_testing_ds_client):
    """Test the retrieval of available indexes."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert "test_index" in ds_client.get_available_indexes()


def test_get_index_mappings(get_testing_ds_client):
    """Test the retrieval of the mapping of an index."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert ds_client.get_index_mappings(index) == parameters[0]


def test_add_fields(get_testing_ds_client):
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    doc = {"title": "test", "text": "test"}
    ds_client.add_document(index, doc)
    ds_client.client.indices.refresh()
    properties = {"test_field": {"type": "keyword"}}
    ds_client.add_fields(index=index, mapping=properties)
    mappings = ds_client.get_index_mappings(index)
    expected_mapping = parameters[0]
    expected_mapping["properties"]["test_field"] = {"type": "keyword"}
    assert mappings == expected_mapping

    # Error
    ds_client, _ = get_testing_ds_client
    with pytest.raises(RuntimeError):
        ds_client.add_fields("does-not-exist")


def test_count_documents(get_testing_ds_client):
    """Test the retrieval of the number of documents in an index."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert ds_client.count_documents(index) == 0

    doc = {"title": "test", "text": "test"}
    ds_client.add_document(index, doc)
    ds_client.client.indices.refresh()

    assert ds_client.count_documents(index) == 1

    # Error
    ds_client, _ = get_testing_ds_client
    with pytest.raises(RuntimeError):
        ds_client.count_documents("does-not-exist")


def test_iter_document(get_testing_ds_client):
    """Test the retrieval of the number of documents in an index."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert ds_client.count_documents(index) == 0

    doc = {"title": "test", "text": "test"}
    ds_client.add_document(index, doc, doc_id="doc_id1")
    ds_client.client.indices.refresh()

    gen = ds_client.iter_document(index=index)

    assert len(list(gen)) == 1

    # Errors
    with pytest.raises(RuntimeError):
        # Index does not exist
        ds_client.add_document("does-not-exist", doc, doc_id="doc_id1")

    with pytest.raises(RuntimeError):
        # Doc already exists
        ds_client.add_document(index, doc, doc_id="doc_id1")


def test_exists(get_testing_ds_client):
    """Test the retrieval of the number of documents in an index."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    doc_id = 1
    doc = {"title": "test", "text": "test"}

    assert not ds_client.exists(index, doc_id)

    ds_client.add_document(index, doc, doc_id)
    ds_client.client.indices.refresh()

    assert ds_client.exists(index, doc_id)


def test_get_document(get_testing_ds_client):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    doc = {"title": "test", "text": "test"}

    ds_client.add_document(index, doc, doc_id="test_id")
    ds_client.client.indices.refresh()

    assert ds_client.get_document(index, "test_id") == doc


def test_get_document_errors(get_testing_ds_client):
    """Test the errors when retrieval of a document."""
    ds_client, parameters = get_testing_ds_client
    with pytest.raises(RuntimeError):
        ds_client.get_document("does-not-exists", "doc-id-1")

    ds_client.create_index(
        "test_index", settings=parameters[-1], mappings=parameters[0]
    )
    with pytest.raises(RuntimeError):
        ds_client.get_document("test_index", "does-not-exist")


def test_get_documents(get_testing_ds_client):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    doc_1 = {"title": "test_1", "text": "text_1"}
    doc_2 = {"title": "test_2", "text": "text_2"}

    ds_client.add_document(index, doc_1, doc_id="1")
    ds_client.add_document(index, doc_2, doc_id="2")
    ds_client.client.indices.refresh()

    expected = [{"document_id": "1", **doc_1}, {"document_id": "2", **doc_2}]
    assert ds_client.get_documents(index, ["1", "2"]) == expected
    assert ds_client.get_documents(index, ["1", "3"]) == [expected[0]]


def test_get_documents_errors(get_testing_ds_client):
    ds_client, _ = get_testing_ds_client
    with pytest.raises(RuntimeError):
        ds_client.get_documents("does-not-exist", ["doc-id1", "doc-id2"])


def test_bulk(get_testing_ds_client):
    ds_client, parameters = get_testing_ds_client

    index = "test_index"

    ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    doc = [
        {
            "_index": index,
            "_id": i,
            "_source": {
                "article_id": i,
                "text": f"Amazing text {i}",
                "paragraph_id": i,
            },
        }
        for i in range(10)
    ]

    ds_client.bulk(doc)
    ds_client.client.indices.refresh()
    n_doc = ds_client.count_documents(index=index)
    assert n_doc == 10
    retrieved_doc = ds_client.get_document(index=index, doc_id=3)["text"]
    assert retrieved_doc == "Amazing text 3"


@pytest.mark.parametrize("query", [{"match_all": {}}, {"match": {"text": "retrieve"}}])
def test_search(get_testing_ds_client, query):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_ds_client

    index_doc = "test_paragraphs"
    aggs = {"unique_ids": {"terms": {"field": "paragraph_id", "size": 10}}}
    ds_client.create_index(index_doc, settings=parameters[-1], mappings=parameters[0])

    doc_1 = {
        "_index": index_doc,
        "_id": 1,
        "_source": {
            "text": "test of an amazing function",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "8765-4321",
        },
    }

    doc_2 = {
        "_index": index_doc,
        "_id": 2,
        "_source": {
            "text": "The bird sings very loudly",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": None,
        },
    }

    doc_3 = {
        "_index": index_doc,
        "_id": 3,
        "_source": {
            "text": "This document is a bad test, I don't want to retrieve it",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "1234-5678",
        },
    }
    doc_bulk = [doc_1, doc_2, doc_3]

    ds_client.bulk(doc_bulk)

    ds_client.client.indices.refresh()

    results = ds_client.search(index_doc, query)
    res_hits = results["hits"]["hits"]
    assert res_hits[0]["_source"]["article_id"] == "article_id"
    assert res_hits[0]["_source"]["title"] == "test_article"
    if "match_all" in query.keys():
        assert len(res_hits) == 3
        assert res_hits[0]["_source"]["text"] == "test of an amazing function"
        assert res_hits[0]["_score"] == 1.0

        # test query + aggs.
        results = ds_client.search(index_doc, query, aggs=aggs)
        assert results["aggregations"]["unique_ids"]["buckets"][0]["doc_count"] == 3
    else:
        assert len(res_hits) == 1
        assert (
            res_hits[0]["_source"]["text"]
            == "This document is a bad test, I don't want to retrieve it"
        )
        assert res_hits[0]["_score"] == pytest.approx(0.7782316)
        # test query + aggs.
        results = ds_client.search(index_doc, query, aggs=aggs)
        assert results["aggregations"]["unique_ids"]["buckets"][0]["doc_count"] == 1

    # test aggs alone.
    results = ds_client.search(index_doc, aggs=aggs)
    assert results["aggregations"]["unique_ids"]["buckets"][0]["doc_count"] == 3

    # test without anything.
    results = ds_client.search(index_doc)
    assert "aggregations" not in results.keys()
    assert len(results["hits"]["hits"]) == 3


@pytest.mark.parametrize("filter_db", [None, {"match": {"text": "retrieve"}}])
def test_bm25_search(get_testing_ds_client, filter_db):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_ds_client

    query = "test"
    index_doc = "test_paragraphs"

    ds_client.create_index(index_doc, settings=parameters[-1], mappings=parameters[0])

    doc_1 = {
        "_index": index_doc,
        "_id": 1,
        "_source": {
            "text": "test of an amazing function",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "8765-4321",
        },
    }

    doc_2 = {
        "_index": index_doc,
        "_id": 2,
        "_source": {
            "text": "The bird sings very loudly",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": None,
        },
    }

    doc_3 = {
        "_index": index_doc,
        "_id": 3,
        "_source": {
            "text": "This document is a bad test, I don't want to retrieve it",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "1234-5678",
        },
    }
    doc_bulk = [doc_1, doc_2, doc_3]

    ds_client.bulk(doc_bulk)
    ds_client.client.indices.refresh()

    res = ds_client.bm25_search(index_doc, query, filter_db, 2)
    assert res[0]["article_id"] == "article_id"
    assert res[0]["title"] == "test_article"
    if filter_db is None:
        assert len(res) == 2
        assert res[0]["text"] == "test of an amazing function"
        assert res[0]["score"] == pytest.approx(0.5403367)
    else:
        assert len(res) == 1
        assert (
            res[0]["text"] == "This document is a bad test, I don't want to retrieve it"
        )
        assert res[0]["score"] == pytest.approx(0.37292093)

    # Errors
    with pytest.raises(RuntimeError):
        ds_client.bm25_search("does-not-exists", query, filter_db, 2)


# Async functions
@pytest.mark.asyncio
async def test_acreate_and_remove_index(get_testing_async_ds_client):
    """Test the creation and removal of an index."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert index in await ds_client.get_available_indexes()

    await ds_client.remove_index(index)

    assert index not in await ds_client.get_available_indexes()


@pytest.mark.asyncio
async def test_aget_available_indexes(get_testing_async_ds_client):
    """Test the retrieval of available indexes."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert "test_index" in await ds_client.get_available_indexes()


@pytest.mark.asyncio
async def test_aget_index_mappings(get_testing_async_ds_client):
    """Test the retrieval of the mapping of an index."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert await ds_client.get_index_mappings(index) == parameters[0]


@pytest.mark.asyncio
async def test_aadd_fields(get_testing_async_ds_client):
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    doc = {"title": "test", "text": "test"}
    await ds_client.add_document(index, doc)
    await ds_client.client.indices.refresh()
    properties = {"test_field": {"type": "keyword"}}
    await ds_client.add_fields(index=index, mapping=properties)
    mappings = await ds_client.get_index_mappings(index)
    expected_mapping = parameters[0]
    expected_mapping["properties"]["test_field"] = {"type": "keyword"}
    assert mappings == expected_mapping


@pytest.mark.asyncio
async def test_acount_documents(get_testing_async_ds_client):
    """Test the retrieval of the number of documents in an index."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert await ds_client.count_documents(index) == 0

    doc = {"title": "test", "text": "test"}
    await ds_client.add_document(index, doc)
    await ds_client.client.indices.refresh()

    assert await ds_client.count_documents(index) == 1


@pytest.mark.asyncio
async def test_aexists(get_testing_async_ds_client):
    """Test the retrieval of the number of documents in an index."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    doc_id = 1
    doc = {"title": "test", "text": "test"}

    assert not await ds_client.exists(index, doc_id)

    await ds_client.add_document(index, doc, doc_id)
    await ds_client.client.indices.refresh()

    assert await ds_client.exists(index, doc_id)


@pytest.mark.asyncio
async def test_aiter_document(get_testing_async_ds_client):
    """Test the retrieval of the number of documents in an index."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    assert await ds_client.count_documents(index) == 0

    doc = {"title": "test", "text": "test"}
    await ds_client.add_document(index, doc)
    await ds_client.client.indices.refresh()

    gen = ds_client.iter_document(index=index)
    gen = [item async for item in gen]

    assert len(list(gen)) == 1


@pytest.mark.asyncio
async def test_aget_document(get_testing_async_ds_client):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    doc = {"title": "test", "text": "test"}

    await ds_client.add_document(index, doc, doc_id="test_id")
    await ds_client.client.indices.refresh()

    assert await ds_client.get_document(index, "test_id") == doc

    with pytest.raises(RuntimeError):
        await ds_client.get_document(index, "does-not-exists")


@pytest.mark.asyncio
async def test_aget_documents(get_testing_async_ds_client):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])

    doc_1 = {"title": "test_1", "text": "text_1"}
    doc_2 = {"title": "test_2", "text": "text_2"}

    await ds_client.add_document(index, doc_1, doc_id="1")
    await ds_client.add_document(index, doc_2, doc_id="2")
    await ds_client.client.indices.refresh()

    expected = [{"document_id": "1", **doc_1}, {"document_id": "2", **doc_2}]
    assert await ds_client.get_documents(index, ["1", "2"]) == expected
    assert await ds_client.get_documents(index, ["1", "3"]) == [expected[0]]


@pytest.mark.asyncio
async def test_abulk(get_testing_async_ds_client):
    ds_client, parameters = get_testing_async_ds_client

    index = "test_index"

    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    doc = [
        {
            "_index": index,
            "_id": i,
            "_source": {
                "article_id": i,
                "text": f"Amazing text {i}",
                "paragraph_id": i,
            },
        }
        for i in range(10)
    ]

    await ds_client.bulk(doc)
    await ds_client.client.indices.refresh()
    n_doc = await ds_client.count_documents(index=index)
    assert n_doc == 10
    retrieved_doc = await ds_client.get_document(index=index, doc_id=3)
    assert retrieved_doc["text"] == "Amazing text 3"


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [{"match_all": {}}, {"match": {"text": "retrieve"}}])
async def test_asearch(get_testing_async_ds_client, query):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_async_ds_client

    aggs = {"unique_ids": {"terms": {"field": "paragraph_id"}}}
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )

    doc_1 = {
        "_index": index_doc,
        "_id": 1,
        "_source": {
            "text": "test of an amazing function",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "8765-4321",
        },
    }

    doc_2 = {
        "_index": index_doc,
        "_id": 2,
        "_source": {
            "text": "The bird sings very loudly",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": None,
        },
    }

    doc_3 = {
        "_index": index_doc,
        "_id": 3,
        "_source": {
            "text": "This document is a bad test, I don't want to retrieve it",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "1234-5678",
        },
    }
    doc_bulk = [doc_1, doc_2, doc_3]

    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()

    results = await ds_client.search(index_doc, query, aggs=aggs)
    res_hits = results["hits"]["hits"]
    assert res_hits[0]["_source"]["article_id"] == "article_id"
    assert res_hits[0]["_source"]["title"] == "test_article"
    if "match_all" in query.keys():
        assert len(res_hits) == 3
        assert res_hits[0]["_source"]["text"] == "test of an amazing function"
        assert res_hits[0]["_score"] == 1.0

        # test query + aggs.
        results = await ds_client.search(index_doc, query, aggs=aggs)
        assert results["aggregations"]["unique_ids"]["buckets"][0]["doc_count"] == 3
    else:
        assert len(res_hits) == 1
        assert (
            res_hits[0]["_source"]["text"]
            == "This document is a bad test, I don't want to retrieve it"
        )
        assert res_hits[0]["_score"] == pytest.approx(0.7782316)
        # test query + aggs.
        results = await ds_client.search(index_doc, query, aggs=aggs)
        assert results["aggregations"]["unique_ids"]["buckets"][0]["doc_count"] == 1

    # test aggs alone.
    results = await ds_client.search(index_doc, aggs=aggs)
    assert results["aggregations"]["unique_ids"]["buckets"][0]["doc_count"] == 3

    # test without anything.
    results = await ds_client.search(index_doc)
    assert "aggregations" not in results.keys()
    assert len(results["hits"]["hits"]) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("filter_db", [None, {"match": {"text": "retrieve"}}])
async def test_abm25_search(get_testing_async_ds_client, filter_db):
    """Test the retrieval of a document."""
    ds_client, parameters = get_testing_async_ds_client

    query = "test"
    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )

    doc_1 = {
        "_index": index_doc,
        "_id": 1,
        "_source": {
            "text": "test of an amazing function",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "8765-4321",
        },
    }

    doc_2 = {
        "_index": index_doc,
        "_id": 2,
        "_source": {
            "text": "The bird sings very loudly",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": None,
        },
    }

    doc_3 = {
        "_index": index_doc,
        "_id": 3,
        "_source": {
            "text": "This document is a bad test, I don't want to retrieve it",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "1234-5678",
        },
    }
    doc_bulk = [doc_1, doc_2, doc_3]

    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()

    res = await ds_client.bm25_search(index_doc, query, filter_db, 2)
    assert res[0]["article_id"] == "article_id"
    assert res[0]["title"] == "test_article"
    if filter_db is None:
        assert len(res) == 2
        assert res[0]["text"] == "test of an amazing function"
        assert res[0]["score"] == pytest.approx(0.5403367)
    else:
        assert len(res) == 1
        assert (
            res[0]["text"] == "This document is a bad test, I don't want to retrieve it"
        )
        assert res[0]["score"] == pytest.approx(0.37292093)


@pytest.mark.parametrize(
    "query, expected_query",
    [
        ({"regex": {"query": "test:test"}}, {"regex": {"query": "test:test"}}),
        (
            {"query_string": {"query": "test:test"}},
            {"query_string": {"query": r"test\:test"}},
        ),
        (
            {"query_string": {"query": "test^test"}},
            {"query_string": {"query": r"test\^test"}},
        ),
        (
            {"query_string": {"query": "test>test"}},
            {"query_string": {"query": r"testtest"}},
        ),
        (
            {"query_string": {"query": "test<test"}},
            {"query_string": {"query": r"testtest"}},
        ),
        (None, None),
    ],
)
def test_postprocess_query(query, expected_query):
    postprocessed_query = postprocess_query(query)
    assert postprocessed_query == expected_query
