import pytest
from scholarag.scripts.manage_index import get_parser, manage_index


def test_get_parser():
    parser = get_parser()
    args = parser.parse_args(["create", "index-name", "db_url:1111"])

    assert args.task == "create"
    assert args.index == "index-name"
    assert args.db_url == "db_url:1111"
    # default values
    assert args.db_type == "opensearch"
    assert args.user is None
    assert args.n_shards == 2
    assert args.n_replicas == 1
    assert args.verbose is False

    # errors
    with pytest.raises(SystemExit):
        _ = parser.parse_args(["wrong-task", "index-name", "db_url:1111"])

    with pytest.raises(SystemExit):
        _ = parser.parse_args(
            ["delete", "index-name", "db_url:1111", "--db-type", "wrong-type"]
        )


def test_manage_index(get_testing_ds_client):
    ds_client, parameters = get_testing_ds_client

    # Test create.
    manage_index("create", ds_client, "test_index", parameters[0], parameters[-1])
    assert set(ds_client.get_available_indexes()) == {"test_index"}

    # Test delete.
    ds_client.create_index(
        "test_paragraphs", settings=parameters[-1], mappings=parameters[0]
    )
    assert set(ds_client.get_available_indexes()) == {
        "test_index",
        "test_paragraphs",
    }
    manage_index("delete", ds_client, "test_index")
    assert set(ds_client.get_available_indexes()) == {"test_paragraphs"}

    # Test reset.
    doc_1 = {
        "_index": "test_paragraphs",
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
        "_index": "test_paragraphs",
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
        "_index": "test_paragraphs",
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
    assert ds_client.count_documents("test_paragraphs") == 3
    manage_index("reset", ds_client, "test_paragraphs", parameters[0], parameters[-1])
    assert set(ds_client.get_available_indexes()) == {"test_paragraphs"}
    assert ds_client.count_documents("test_paragraphs") == 0
