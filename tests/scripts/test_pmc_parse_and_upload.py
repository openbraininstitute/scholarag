from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiobotocore.client import AioBaseClient
from aiobotocore.session import ClientCreatorContext, get_session
from dateutil.tz import tzutc
from scholarag.scripts.pmc_parse_and_upload import run
from scholarag.services import ParsingService


@pytest.mark.asyncio
async def test_pmc_parse_and_upload(httpx_mock, get_testing_async_ds_client):
    ds_client, parameters = get_testing_async_ds_client
    index = "paragraphs_parse_script_pytest"
    await ds_client.create_index(
        index=index,
        mappings=parameters[0],
        settings=parameters[1],
    )

    async def get_body():
        return b"great xml"

    session = get_session()
    mocked_session = AsyncMock(spec=session.__class__)
    mocked_client = AsyncMock(spec=ClientCreatorContext)
    mocked_session.create_client.return_value = mocked_client

    mocked_base_client = Mock(spec=AioBaseClient)
    mocked_response = MagicMock()
    mocked_get_object = AsyncMock(return_value=mocked_response)

    mocked_get_item = AsyncMock()
    mocked_response.__getitem__.return_value = mocked_get_item
    mocked_get_item.read = get_body

    mocked_base_client.get_object = mocked_get_object

    mocked_client.__aenter__.return_value = mocked_base_client

    batch_size = 9

    async def get_filter_async(batch_size):
        for i in range(batch_size):
            yield {
                "Key": f"oa_comm/xml/all/PMC1000000{i}.xml",
                "LastModified": datetime(2023, 8, 16, 6, 51, 23, tzinfo=tzutc()),
                "ETag": '"32d23b6070945e062e5918d2364a8824"',
                "Size": 2999,
                "StorageClass": "STANDARD",
            }

    mocked_base_client.get_paginator.return_value.paginate.return_value.search.return_value = get_filter_async(
        batch_size
    )
    content = {
        "uid": "article_uid",
        "authors": "fake_authors",
        "title": "fake_title",
        "abstract": [
            "fake_abstract",
        ],
        "pubmed_id": "fake_pubmed_id",
        "pmc_id": "PMC123456",
        "arxiv_id": "fake_arxiv_id",
        "doi": "fake_doi",
        "date": datetime(2020, 1, 1).strftime("%Y-%m-%d"),
        "section_paragraphs": [("Section 1", "Paragraph 1")],
        "journal": "1234-5678",
        "article_type": "Journal article",
    }

    httpx_mock.add_response(
        method="POST",
        url="http://localhost/fake_parser",
        json=content,
    )
    db_type = (
        "elasticsearch"
        if "ElasticSearch" in ds_client.__class__.__name__
        else "opensearch"
    )
    with (
        patch(
            "scholarag.scripts.pmc_parse_and_upload.get_session",
            return_value=mocked_session,
        ),
        patch(
            "scholarag.scripts.pmc_parse_and_upload.setup_parsing_ds",
            return_value=(ds_client, ParsingService()),
        ),
    ):
        await run(
            db_url="greaturl.com:9200",
            parsing_url="http://localhost/fake_parser",
            db_type=db_type,
            start_date=datetime(2022, 6, 1),
            index=index,
            batch_size=batch_size,
            min_paragraphs_length=0,
        )

        await ds_client.client.indices.refresh()
        assert await ds_client.count_documents(index) == 2

        # No upload due to length restrictions.
        await run(
            db_url="greaturl.com:9200",
            parsing_url="http://localhost/fake_parser",
            db_type=db_type,
            start_date=datetime(2022, 6, 1),
            index=index,
            batch_size=batch_size,
            min_paragraphs_length=0,
            max_paragraphs_length=10,
        )

        await ds_client.client.indices.refresh()
        assert await ds_client.count_documents(index) == 2
