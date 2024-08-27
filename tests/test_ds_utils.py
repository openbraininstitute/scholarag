import random
from pathlib import Path

import pytest
from scholarag.ds_utils import check_docs_exists_in_db, ds_upload, setup_parsing_ds
from scholarag.services import ParsingService


@pytest.mark.asyncio
async def test_setup_parsing_ds(get_testing_async_ds_client):
    ds_client, _ = get_testing_async_ds_client
    db_url, db_type = (
        ("http://localhost:9201", "elasticsearch")
        if "ElasticSearch" in ds_client.__class__.__name__
        else ("localhost:9200", "opensearch")
    )
    ds_client, parsing_client = await setup_parsing_ds(
        db_url=db_url,
        db_type=db_type,
    )
    assert await ds_client.client.ping()
    assert isinstance(parsing_client, ParsingService)


@pytest.mark.asyncio
async def test_ds_upload_and_check_in_db(get_testing_async_ds_client):
    ds_client, parameters = get_testing_async_ds_client
    filenames = [Path("file1.xml"), Path("file2.xml"), Path("file3.xml")]
    index = "paragraphs_ds_upload"
    results = [
        {
            "uid": "uid1",
            "abstract": ["This is a first paragraph", "This is a second"],
            "authors": ["author a", "author b"],
            "title": "This is a fake title",
            "pubmed_id": "12345",
            "pmc_id": "PMC123456",
            "arxiv_id": "arxiv_id1",
            "doi": "DOI12345",
            "date": "2020-12-21",
            "journal": "Journal name",
            "article_type": "research_article",
            "section_paragraphs": [
                ("Introduction", "This is the introduction"),
                ("Conclusion", "This is the conclusion"),
            ],
        },
        None,
        {
            "uid": "uid1",
            "abstract": ["This is a first great paragraph", "This is a bad second"],
            "authors": ["author a", "author b"],
            "title": "This is a fake title",
            "pubmed_id": "12345",
            "pmc_id": "PMC654321",
            "arxiv_id": "arxiv_id1",
            "doi": "DOI12345",
            "date": "2020-12-21",
            "journal": "Journal name",
            "article_type": "research_article",
            "section_paragraphs": [
                ("Introduction", "This is the second introduction"),
                ("Conclusion", "This is the second conclusion"),
            ],
        },
    ]

    await ds_client.create_index(
        index=index,
        mappings=parameters[0],
        settings=parameters[1],
    )

    files_failing = await ds_upload(
        filenames=filenames,
        results=results,
        indices=[index for _ in range(len(filenames))],
        ds_client=ds_client,
    )

    await ds_client.client.indices.refresh()
    assert await ds_client.count_documents(index) == 8

    assert files_failing[0] == Path("file2.xml")

    # Upload five more paragraphs using length lower bound
    results[0]["uid"] = str(random.random())
    results[2]["uid"] = str(random.random())
    await ds_upload(
        filenames=filenames,
        results=results,
        indices=[index for _ in range(len(filenames))],
        ds_client=ds_client,
        min_paragraphs_length=23,
    )

    await ds_client.client.indices.refresh()
    assert await ds_client.count_documents(index) == 13

    # Upload three more paragraphs using length upper bound
    results[0]["uid"] = str(random.random())
    results[2]["uid"] = str(random.random())
    await ds_upload(
        filenames=filenames,
        results=results,
        indices=[index for _ in range(len(filenames))],
        ds_client=ds_client,
        max_paragraphs_length=23,
    )

    await ds_client.client.indices.refresh()
    assert await ds_client.count_documents(index) == 16

    # Try to upload similar paragraphs within the same article
    results[0]["uid"] = str(random.random())
    results[2] = results[0]
    await ds_upload(
        filenames=filenames,
        results=results,
        indices=[index for _ in range(len(filenames))],
        ds_client=ds_client,
    )

    await ds_client.client.indices.refresh()
    assert await ds_client.count_documents(index) == 20


@pytest.mark.parametrize(
    "pmc_ids, expected_existing_ids",
    [
        (
            ["PMC123456", "PMC654321", "PMC135246"],
            ["PMC123456", "PMC654321", "PMC135246"],
        ),
        (
            ["PMC123456", "PMC654321", "PMC678438"],
            [
                "PMC123456",
                "PMC654321",
            ],
        ),
        (
            [
                "PMC349827",
                "PMC049123",
            ],
            [],
        ),
    ],
)
@pytest.mark.asyncio
async def test_check_docs_exists_in_db(
    pmc_ids, expected_existing_ids, get_testing_async_ds_client
):
    ds_client, parameters = get_testing_async_ds_client
    index = "check_docs_in_db"

    await ds_client.create_index(
        index=index,
        mappings=parameters[0],
        settings=parameters[1],
    )

    doc_1 = {
        "_index": index,
        "_id": 1,
        "_source": {
            "text": "test of an amazing function",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "8765-4321",
            "pmc_id": "PMC123456",
        },
    }

    doc_2 = {
        "_index": index,
        "_id": 2,
        "_source": {
            "text": "The bird sings very loudly",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": None,
            "pmc_id": "PMC654321",
        },
    }

    doc_3 = {
        "_index": index,
        "_id": 3,
        "_source": {
            "text": "This document is a bad test, I don't want to retrieve it",
            "title": "test_article",
            "paragraph_id": "1",
            "article_id": "article_id",
            "journal": "1234-5678",
            "pmc_id": "PMC135246",
        },
    }
    doc_bulk = [doc_1, doc_2, doc_3]

    await ds_client.bulk(doc_bulk)
    await ds_client.client.indices.refresh()

    docs = await ds_client.search(index, query={"match_all": {}})
    assert len(docs["hits"]["hits"]) == 3

    existings_ids = await check_docs_exists_in_db(ds_client, index, pmc_ids)
    assert set(existings_ids) == set(expected_existing_ids)
