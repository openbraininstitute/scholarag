import json
import unittest.mock as mock
from unittest.mock import MagicMock

import httpx
import pytest
from scholarag.document_stores import AsyncBaseSearch
from scholarag.retrieve_metadata import (
    MetaDataRetriever,
    get_citation_count,
    get_impact_factors,
    get_journal_name,
    recreate_abstract,
)


class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.parametrize(
    "issns,return_value,response",
    [
        (
            ["1234-5678", "9101-1121"],
            [
                {
                    "_index": "impact_factors",
                    "_id": "NAmRrYkB3O3HeJL6-cS3",
                    "_score": None,
                    "_source": {
                        "Scopus Source ID": 21100826277,
                        "Title": "Frontiers in Cell and Developmental Biology",
                        "Citation Count": 51808,
                        "Scholarly Output": 8178,
                        "Percent Cited": 78,
                        "CiteScore": 1.0,
                        "SNIP": 0.995,
                        "SJR": 1.418,
                        "Scopus ASJC Code (Sub-subject Area)": 1309,
                        "Scopus Sub-Subject Area": "Developmental Biology",
                        "Percentile": 69,
                        "RANK": 24,
                        "Rank Out Of": 78,
                        "Main Publisher": "Frontiers Media S.A.",
                        "Type": "j",
                        "Open Access": "YES",
                        "Quartile": 2,
                        "Top 10% (CiteScore Percentile)": False,
                        "URL Scopus Source ID": (
                            "https://www.scopus.com/sourceid/21100826277"
                        ),
                        "Print ISSN": None,
                        "E-ISSN": "12345678",
                    },
                    "sort": [48471],
                },
                {
                    "_index": "impact_factors",
                    "_id": "NAmRrYkB3O3HeJL6-cS3",
                    "_score": None,
                    "_source": {
                        "Scopus Source ID": 21100826277,
                        "Title": "Frontiers in Cell and Developmental Biology",
                        "Citation Count": 51808,
                        "Scholarly Output": 8178,
                        "Percent Cited": 78,
                        "CiteScore": 2.0,
                        "SNIP": 0.995,
                        "SJR": 1.418,
                        "Scopus ASJC Code (Sub-subject Area)": 1309,
                        "Scopus Sub-Subject Area": "Developmental Biology",
                        "Percentile": 69,
                        "RANK": 24,
                        "Rank Out Of": 78,
                        "Main Publisher": "Frontiers Media S.A.",
                        "Type": "j",
                        "Open Access": "YES",
                        "Quartile": 2,
                        "Top 10% (CiteScore Percentile)": False,
                        "URL Scopus Source ID": (
                            "https://www.scopus.com/sourceid/21100826277"
                        ),
                        "Print ISSN": None,
                        "E-ISSN": "91011121",
                    },
                    "sort": [48471],
                },
            ],
            {"1234-5678": 1.0, "9101-1121": 2.0},
        ),
        (["9999-9999"], [], {"9999-9999": None}),
        ([None], [], {None: None}),
    ],
)
@pytest.mark.asyncio
async def test_get_impact_factor(issns, return_value, response):
    """Test retrieving the impact factor."""
    fake_ds_client_instance = MagicMock(spec=AsyncBaseSearch)
    fake_ds_client_instance.get_available_indexes.return_value = [
        "something",
    ]
    fake_ds_client_instance.iter_document.return_value = AsyncIterator(return_value)

    impact_factors = await get_impact_factors(
        ds_client=fake_ds_client_instance,
        issns=issns,
        db_index_impact_factor="something",
    )

    assert impact_factors == response


@pytest.mark.parametrize(
    "issns,return_value,response",
    [
        (
            ["1234-5678", "9101-1121"],
            [
                {
                    "_index": "impact_factors",
                    "_id": "NAmRrYkB3O3HeJL6-cS3",
                    "_score": None,
                    "_source": {
                        "Scopus Source ID": 21100826277,
                        "Title": "Frontiers in Cell and Developmental Biology",
                        "Citation Count": 51808,
                        "Scholarly Output": 8178,
                        "Percent Cited": 78,
                        "CiteScore": 1.0,
                        "SNIP": 0.995,
                        "SJR": 1.418,
                        "Scopus ASJC Code (Sub-subject Area)": 1309,
                        "Scopus Sub-Subject Area": "Developmental Biology",
                        "Percentile": 69,
                        "RANK": 24,
                        "Rank Out Of": 78,
                        "Main Publisher": "Frontiers Media S.A.",
                        "Type": "j",
                        "Open Access": "YES",
                        "Quartile": 2,
                        "Top 10% (CiteScore Percentile)": False,
                        "URL Scopus Source ID": (
                            "https://www.scopus.com/sourceid/21100826277"
                        ),
                        "Print ISSN": None,
                        "E-ISSN": "12345678",
                    },
                    "sort": [48471],
                },
                {
                    "_index": "impact_factors",
                    "_id": "NAmRrYkB3O3HeJL6-cS3",
                    "_score": None,
                    "_source": {
                        "Scopus Source ID": 21100826277,
                        "Title": "Frontiers in Cell and Developmental Biology",
                        "Citation Count": 51808,
                        "Scholarly Output": 8178,
                        "Percent Cited": 78,
                        "CiteScore": 2.0,
                        "SNIP": 0.995,
                        "SJR": 1.418,
                        "Scopus ASJC Code (Sub-subject Area)": 1309,
                        "Scopus Sub-Subject Area": "Developmental Biology",
                        "Percentile": 69,
                        "RANK": 24,
                        "Rank Out Of": 78,
                        "Main Publisher": "Frontiers Media S.A.",
                        "Type": "j",
                        "Open Access": "YES",
                        "Quartile": 2,
                        "Top 10% (CiteScore Percentile)": False,
                        "URL Scopus Source ID": (
                            "https://www.scopus.com/sourceid/21100826277"
                        ),
                        "Print ISSN": None,
                        "E-ISSN": "91011121",
                    },
                    "sort": [48471],
                },
            ],
            {"1234-5678": 1.0, "9101-1121": 2.0},
        ),
        (["9999-9999"], [], {"9999-9999": None}),
        ([None], [], {None: None}),
    ],
)
@pytest.mark.asyncio
async def test_metadata_retriever_get_impact_factor(issns, return_value, response):
    """Test retrieving the impact factor."""
    fake_ds_client_instance = MagicMock(spec=AsyncBaseSearch)
    fake_ds_client_instance.get_available_indexes.return_value = [
        "something",
    ]
    fake_ds_client_instance.iter_document.return_value = AsyncIterator(return_value)

    retriever = MetaDataRetriever()
    retriever.schedule_bulk_request(
        get_impact_factors,
        **{
            "ds_client": fake_ds_client_instance,
            "issns": issns,
            "db_index_impact_factor": "something",
        },
    )
    impact_factors = await retriever.fetch()

    assert impact_factors["get_impact_factors"] == response


@pytest.mark.asyncio
async def test_get_citation_count(httpx_mock):
    """Test get_citation_count."""
    doi = "1"
    response = {"citationCount": 2}

    httpx_mock.add_response(
        url=(
            f"https://api.semanticscholar.org/graph/v1/paper/{doi}?fields=citationCount"
        ),
        method="GET",
        json=response,
    )
    async with httpx.AsyncClient() as client:
        result = await get_citation_count(doi, client)

    assert result == 2


@pytest.mark.asyncio
async def test_get_citation_count_no_doi():
    """Test get_citation_count."""
    doi = None

    async with httpx.AsyncClient() as client:
        result = await get_citation_count(doi, client)

    assert result is None


@pytest.mark.asyncio
async def test_metadata_retriever_get_citation_count(httpx_mock):
    """Test get_citation_counts."""
    dois = ["1", "2", "3"]
    responses = [{"citationCount": 2}, {"citationCount": 5}, {}]
    retriever = MetaDataRetriever()
    for doi, response in zip(dois, responses):
        httpx_mock.add_response(
            url=f"https://api.semanticscholar.org/graph/v1/paper/{doi}?fields=citationCount",
            method="GET",
            json=response,
        )
    async with httpx.AsyncClient() as client:
        retriever.schedule_non_bulk_requests(
            get_citation_count, dois, **{"httpx_client": client}
        )
        result = await retriever.fetch()

    assert result["get_citation_count"] == {"1": 2, "2": 5, "3": None}


@pytest.mark.asyncio
async def test_get_citation_counts_exception(httpx_mock):
    """Test get_citation_counts in case of failure."""
    # Test case with DOI that triggers httpx.HTTPError
    doi = "error_doi"

    httpx_mock.add_exception(
        url=(
            f"https://api.semanticscholar.org/graph/v1/paper/{doi}?fields=citationCount"
        ),
        exception=httpx.HTTPError(
            "DOI not found"
        ),  # Use httpx.HTTPError to trigger exception
    )
    async with httpx.AsyncClient() as client:
        result = await get_citation_count(doi, client)

    assert result is None


@pytest.mark.asyncio
async def test_reconstruct_abstract():
    fake_paragraph_1 = {
        "_index": "fake_index",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 2,
            "section": "Abstract",
            "text": "but the third one is even better.",
        },
    }
    fake_paragraph_2 = {
        "_index": "fake_index",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 0,
            "section": "Abstract",
            "text": (
                "This first paragraph contains the great first part of the great"
                " abstract, "
            ),
        },
    }
    fake_paragraph_3 = {
        "_index": "fake_index",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 1,
            "section": "Abstract",
            "text": "however i believe that this second part is amazing ",
        },
    }
    fake_ds_instance = MagicMock(spec=AsyncBaseSearch)

    fake_ds_instance.iter_document.return_value = AsyncIterator(
        [fake_paragraph_1, fake_paragraph_2, fake_paragraph_3]
    )

    abstract = await recreate_abstract("1234abcd", fake_ds_instance, "fake_index")

    assert (
        abstract
        == "This first paragraph contains the great first part of the great abstract,"
        " however i believe that this second part is amazing but the third one is"
        " even better."
    )


@pytest.mark.asyncio
async def test_recreate_abstract_with_db(get_testing_async_ds_client):
    ds_client, parameters = get_testing_async_ds_client

    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )

    fake_paragraph_1 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 2,
            "section": "Abstract",
            "text": "but the third one is even better.",
        },
    }
    fake_paragraph_2 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 0,
            "section": "Abstract",
            "text": (
                "This first paragraph contains the great first part of the great"
                " abstract, "
            ),
        },
    }
    fake_paragraph_3 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 1,
            "section": "Abstract",
            "text": "however i believe that this second part is amazing ",
        },
    }
    doc_bulk = [fake_paragraph_1, fake_paragraph_2, fake_paragraph_3]

    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()

    abstract = await recreate_abstract("1234abcd", ds_client, "test_paragraphs")

    assert (
        abstract
        == "This first paragraph contains the great first part of the great abstract,"
        " however i believe that this second part is amazing but the third one is"
        " even better."
    )


@pytest.mark.asyncio
async def test_metadata_retriever_recreate_abstract_with_db(
    get_testing_async_ds_client,
):
    ds_client, parameters = get_testing_async_ds_client

    index_doc = "test_paragraphs"

    await ds_client.create_index(
        index_doc, settings=parameters[-1], mappings=parameters[0]
    )

    fake_paragraph_1 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 2,
            "section": "Abstract",
            "text": "but the third one is even better.",
        },
    }
    fake_paragraph_2 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 0,
            "section": "Abstract",
            "text": (
                "This first paragraph contains the great first part of the great"
                " abstract, "
            ),
        },
    }
    fake_paragraph_3 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "1234abcd",
            "paragraph_id": 1,
            "section": "Abstract",
            "text": "however i believe that this second part is amazing ",
        },
    }
    fake_paragraph_4 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "article2",
            "paragraph_id": 2,
            "section": "Abstract",
            "text": " it contains a bad abstract.",
        },
    }
    fake_paragraph_5 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "article2",
            "paragraph_id": 0,
            "section": "Abstract",
            "text": "This is a new article,",
        },
    }
    fake_paragraph_6 = {
        "_index": "test_paragraphs",
        "_source": {
            "article_id": "article2",
            "paragraph_id": 1,
            "section": "Abstract",
            "text": " it is quite a good one but",
        },
    }
    doc_bulk = [fake_paragraph_1, fake_paragraph_2, fake_paragraph_3]

    await ds_client.bulk(doc_bulk)

    doc_bulk = [fake_paragraph_4, fake_paragraph_5, fake_paragraph_6]

    await ds_client.bulk(doc_bulk)

    await ds_client.client.indices.refresh()

    retriever = MetaDataRetriever()
    retriever.schedule_non_bulk_requests(
        recreate_abstract,
        ["1234abcd", "article2"],
        **{"ds_client": ds_client, "db_index_paragraphs": "test_paragraphs"},
    )

    abstract = await retriever.fetch()

    assert (
        abstract["recreate_abstract"]["1234abcd"]
        == "This first paragraph contains the great first part of the great abstract,"
        " however i believe that this second part is amazing but the third one is"
        " even better."
    )

    assert (
        abstract["recreate_abstract"]["article2"]
        == "This is a new article, it is quite a good one but it contains a bad"
        " abstract."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["issn", "name"], [("1234-5678", "great_journal"), ("3426-1936", "bad_journal")]
)
async def test_get_journal_name(httpx_mock, issn, name):
    # If ISSN is None
    async with httpx.AsyncClient() as client:
        name_found = await get_journal_name(None, client)
    assert name_found is None

    response = {
        "@context": "http://schema.org/",
        "@id": f"https://portal.issn.org/resource/ISSN/{issn}",
        "@type": "Periodical",
        "exampleOfWork": {
            "@id": f"https://portal.issn.org/resource/ISSN-L/{issn}",
            "@type": "CreativeWork",
            "workExample": [
                {"@id": f"https://portal.issn.org/resource/ISSN/{issn}", "name": name}
            ],
        },
        "issn": issn,
        "identifier": [
            {
                "@type": "PropertyValue",
                "name": "ISSN",
                "value": issn,
                "description": "Valid",
            },
            {
                "@type": "PropertyValue",
                "name": "ISSN-L",
                "value": issn,
                "description": "Valid",
            },
        ],
        "name": name,
        "alternateName": "eNeurologicalSci.",
        "publication": {
            "@id": f"https://portal.issn.org/resource/ISSN/{issn}#ReferencePublicationEvent",
            "@type": "PublicationEvent",
            "location": {
                "@id": "https://www.iso.org/obp/ui/#iso:code:3166:NL",
                "@type": "Country",
                "name": "Netherlands",
            },
        },
    }
    response = (
        '<script type="application/ld+json">' + json.dumps(response) + "</script>"
    )
    httpx_mock.add_response(
        url=f"https://portal.issn.org/resource/ISSN/{issn}",
        method="GET",
        text=response,
    )
    async with httpx.AsyncClient() as client:
        name_found = await get_journal_name(issn, client)
    assert name == name_found

    httpx_mock.reset(assert_all_responses_were_requested=False)

    httpx_mock.add_response(
        url=f"https://portal.issn.org/resource/ISSN/{issn}",
        method="GET",
        text=response,
        status_code=404,
    )
    async with httpx.AsyncClient() as client:
        name = await get_journal_name(issn, client)
    assert not name

    httpx_mock.reset(assert_all_responses_were_requested=False)

    httpx_mock.add_response(
        url=f"https://portal.issn.org/resource/ISSN/{issn}",
        method="GET",
        text="terrible response.",
        status_code=200,
    )
    async with httpx.AsyncClient() as client:
        name = await get_journal_name(issn, client)
    assert not name


@pytest.mark.asyncio
async def test_journal_name_timeout(httpx_mock):
    httpx_mock.add_exception(httpx.PoolTimeout("Timeout"))
    async with httpx.AsyncClient() as client:
        name = await get_journal_name("1234-5678", client)
    assert name is None


@pytest.mark.asyncio
async def test_journal_name_http_exception(httpx_mock):
    httpx_mock.add_exception(httpx.HTTPError("This is the error"))
    async with httpx.AsyncClient() as client:
        name = await get_journal_name("1234-5678", client)
    assert name is None


@pytest.mark.asyncio
async def test_metadata_retriever_get_journal_name(httpx_mock):
    issns = ["1234-5678", "3426-1936"]
    names = ["great_journal", "bad_journal"]
    responses = [
        {
            "@context": "http://schema.org/",
            "@id": f"https://portal.issn.org/resource/ISSN/{issn}",
            "@type": "Periodical",
            "exampleOfWork": {
                "@id": f"https://portal.issn.org/resource/ISSN-L/{issn}",
                "@type": "CreativeWork",
                "workExample": [
                    {
                        "@id": f"https://portal.issn.org/resource/ISSN/{issn}",
                        "name": name,
                    }
                ],
            },
            "issn": issn,
            "identifier": [
                {
                    "@type": "PropertyValue",
                    "name": "ISSN",
                    "value": issn,
                    "description": "Valid",
                },
                {
                    "@type": "PropertyValue",
                    "name": "ISSN-L",
                    "value": issn,
                    "description": "Valid",
                },
            ],
            "name": name,
            "alternateName": "eNeurologicalSci.",
            "publication": {
                "@id": f"https://portal.issn.org/resource/ISSN/{issn}#ReferencePublicationEvent",
                "@type": "PublicationEvent",
                "location": {
                    "@id": "https://www.iso.org/obp/ui/#iso:code:3166:NL",
                    "@type": "Country",
                    "name": "Netherlands",
                },
            },
        }
        for (issn, name) in zip(issns, names)
    ]
    for issn, response in zip(issns, responses):
        response = (
            '<script type="application/ld+json">' + json.dumps(response) + "</script>"
        )
        httpx_mock.add_response(
            url=f"https://portal.issn.org/resource/ISSN/{issn}",
            method="GET",
            text=response,
        )
    retriever = MetaDataRetriever()
    async with httpx.AsyncClient() as client:
        retriever.schedule_non_bulk_requests(
            get_journal_name, issns, **{"httpx_client": client}
        )
        name_found = await retriever.fetch()
    assert name_found["get_journal_name"] == dict(zip(issns, names))


@pytest.mark.asyncio
async def test_metadata_retriever_external_apis(get_testing_async_ds_client):
    ds_client, _ = get_testing_async_ds_client
    contexts = [
        {
            "journal": "issn1",
            "doi": "doi1",
            "article_id": "fake",
        }
    ]

    async def get_journal_name(issn, httpx_client):
        return "journalname1"

    async def get_citation_count(doi, httpx_client):
        return "citationcount1"

    with (
        mock.patch(
            "scholarag.retrieve_metadata.get_impact_factors"  # not interesting for this test
        ),
        mock.patch(
            "scholarag.retrieve_metadata.recreate_abstract"  # not interesting for this test
        ),
        mock.patch(
            "scholarag.retrieve_metadata.get_citation_count",
            new=get_citation_count,
        ),
        mock.patch(
            "scholarag.retrieve_metadata.get_journal_name",
            new=get_journal_name,
        ),
    ):
        retriever = MetaDataRetriever(external_apis=False)
        async with httpx.AsyncClient() as client:
            fetched_metadata = await retriever.retrieve_metadata(
                contexts, ds_client, "impact_factors", "paragraphs", client
            )
        assert "get_journal_name" not in fetched_metadata
        assert "get_citation_count" not in fetched_metadata

        retriever = MetaDataRetriever(external_apis=True)
        async with httpx.AsyncClient() as client:
            fetched_metadata = await retriever.retrieve_metadata(
                contexts, ds_client, "impact_factors", "paragraphs", client
            )
        assert "get_journal_name" in fetched_metadata
        assert "get_citation_count" in fetched_metadata
