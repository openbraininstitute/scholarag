import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from scholarag.scripts.parse_and_upload import get_parser, run
from scholarag.services import ParsingService


def test_get_parser():
    parser = get_parser()
    args = parser.parse_args(["path/to/file.json", "parser_url", "db_url"])
    assert isinstance(args.path, Path)
    assert str(args.path) == "path/to/file.json"
    assert args.parser_url == "parser_url"
    assert args.db_url == "db_url"
    # default values
    assert args.articles_per_bulk == 1000
    assert args.max_paragraphs_length is None
    assert args.min_paragraphs_length is None
    assert args.multipart_params is None
    assert args.max_concurrent_requests == 10
    assert args.db_type == "opensearch"
    assert args.user is None
    assert args.index == "paragraphs"
    assert args.files_failing_path is None
    assert args.recursive is False
    assert args.use_ssl is False
    assert args.verbose is False

    # flags
    args = parser.parse_args(
        ["path/to/file.json", "parser_url", "db_url", "-v", "--use-ssl", "-r"]
    )
    assert args.recursive is True
    assert args.use_ssl is True
    assert args.verbose is True

    # errors
    with pytest.raises(SystemExit):
        _ = parser.parse_args(
            ["path/to/file.json", "parser_url", "db_url", "--db-type", "wrong-type"]
        )


@pytest.mark.asyncio
async def test_raise_error(tmp_path):
    with pytest.raises(ValueError):
        with patch(
            "scholarag.scripts.parse_and_upload.setup_parsing_ds",
            return_value=(AsyncMock(), AsyncMock()),
        ):
            await run(
                db_url="http://greaturl.com",
                path=tmp_path / "wrong_path",
                recursive=True,
                match_filename=".xml",
                parser_url="http://localhost/parser",
                multipart_params=None,
                max_concurrent_requests=1,
                articles_per_bulk=10,
                index="paragraphs",
            )


@pytest.mark.asyncio
async def test_run(tmp_path, httpx_mock):
    # Create two files
    file1_path = tmp_path / "file1.json"
    file1_path.touch()
    file2_path = tmp_path / "file2.json"
    file2_path.touch()

    # Mock the requests to the server
    content = {
        "uid": "article_uid",
        "authors": "fake_authors",
        "title": "fake_title",
        "abstract": [
            "fake_abstract",
        ],
        "pubmed_id": "fake_pubmed_id",
        "pmc_id": "fake_pmc_id",
        "arxiv_id": "fake_arxiv_id",
        "doi": "fake_doi",
        "date": datetime(1700, 1, 1).strftime("%Y-%m-%d"),
        "section_paragraphs": [("Section 1", "Paragraph 1")],
        "journal": "1234-5678",
        "article_type": "Journal article",
    }

    httpx_mock.add_response(
        method="POST",
        url="http://localhost/fake_parser",
        json=content,
    )

    with patch(
        "scholarag.scripts.parse_and_upload.setup_parsing_ds",
        return_value=(AsyncMock(), ParsingService(url="http://localhost/fake_parser")),
    ):
        # Call specifying one file
        await run(
            db_url="greaturl.com:9200",
            path=file1_path,
            recursive=False,
            match_filename=None,
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            index="paragraphs",
        )

        assert len(httpx_mock.get_requests()) == 1

        # Call specifying the directory with two files
        # Reset mock calls
        httpx_mock.reset(assert_all_responses_were_requested=False)
        httpx_mock.add_response(
            method="POST",
            url="http://localhost/fake_parser",
            json=content,
        )

        # Launching the function
        await run(
            db_url="greaturl.com:9200",
            path=tmp_path,
            recursive=True,
            match_filename=r".*\.json$",
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            index="paragraphs",
        )

    assert len(httpx_mock.get_requests()) == 2


async def fake_close(self):
    pass


@pytest.mark.asyncio
@patch("scholarag.document_stores.AsyncOpenSearch.close", new=fake_close)
async def test_run_with_es_instance(tmp_path, httpx_mock, get_testing_async_ds_client):
    ds_client, parameters = get_testing_async_ds_client

    # Create a fake file
    file1_path = tmp_path / "file1.json"
    file1_path.touch()

    # Mock the requests to the server
    content = {
        "uid": "article_uid",
        "authors": "fake_authors",
        "title": "fake_title",
        "abstract": [
            "fake_abstract",
        ],
        "pubmed_id": "fake_pubmed_id",
        "pmc_id": "fake_pmc_id",
        "doi": "fake_doi",
        "arxiv_id": "fake_arxiv_id",
        "date": datetime(1700, 1, 1).strftime("%Y-%m-%d"),
        "section_paragraphs": [("Section 1", "Paragraph 1")],
        "journal": "1234-5678",
        "article_type": "Journal article",
    }

    httpx_mock.add_response(
        method="POST",
        url="http://localhost/fake_parser",
        json=content,
    )

    index = "paragraphs_parse_script_pytest"
    db_type = (
        "elasticsearch"
        if "ElasticSearch" in ds_client.__class__.__name__
        else "opensearch"
    )
    await ds_client.create_index(index, settings=parameters[-1], mappings=parameters[0])
    await ds_client.client.indices.refresh()
    with patch(
        "scholarag.scripts.parse_and_upload.setup_parsing_ds",
        return_value=(ds_client, ParsingService(url="http://localhost/fake_parser")),
    ):
        # Call specifying one file
        await run(
            db_url="zdadas",
            db_type=db_type,
            path=file1_path,
            recursive=True,
            match_filename=r".*\.json$",
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            index=index,
        )

        # Just wait for the update to be done
        await ds_client.client.indices.refresh()
        assert await ds_client.count_documents(index) == 2

        # Call with the exact same file should not add any data to the ES
        await run(
            db_url="zdadas",
            db_type=db_type,
            path=file1_path,
            recursive=True,
            match_filename=r".*\.json$",
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            index=index,
        )
        assert await ds_client.count_documents(index) == 2
        paragraph_uid = hashlib.md5(
            ("article_uid" + "Paragraph 1").encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        uploaded_paragraph = await ds_client.get_document(index, paragraph_uid)
        assert uploaded_paragraph["article_id"] == "article_uid"
        assert uploaded_paragraph["title"] == "fake_title"

        # Mock the requests to have a new response (faking a new article)
        content = {
            "uid": "article_uid2",
            "authors": "fake_authors",
            "title": "fake_title",
            "abstract": [
                "fake_abstract",
            ],
            "pubmed_id": "fake_pubmed_id",
            "pmc_id": "fake_pmc_id",
            "doi": "fake_doi",
            "arxiv_id": "fake_arxiv_id",
            "date": datetime(1700, 1, 1).strftime("%Y-%m-%d"),
            "section_paragraphs": [("Section 1", "Paragraph 1")],
            "journal": "1234-5678",
            "article_type": "Journal article",
        }

        httpx_mock.add_response(
            method="POST",
            url="http://localhost/fake_parser",
            json=content,
        )

        await run(
            db_url="zdadas",
            db_type=db_type,
            path=file1_path,
            recursive=True,
            match_filename=r".*\.json$",
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            index=index,
        )
        # Just wait for the update to be done
        await ds_client.client.indices.refresh()
        assert await ds_client.count_documents(index) == 4

        # Mock the requests to the server
        content = {
            "uid": "article_uid_3",
            "authors": "fake_authors",
            "title": "fake_title",
            "abstract": [
                "abstract",
            ],
            "pubmed_id": "fake_pubmed_id",
            "pmc_id": "fake_pmc_id",
            "doi": "fake_doi",
            "arxiv_id": "fake_arxiv_id",
            "date": datetime(1700, 1, 1).strftime("%Y-%m-%d"),
            "section_paragraphs": [("Section 1", "Paragraphs 1")],
            "journal": "1234-5678",
            "article_type": "Journal article",
        }

        httpx_mock.add_response(
            method="POST",
            url="http://localhost/fake_parser",
            json=content,
        )
        # Test excluding short paragraphs
        await run(
            db_url="zdadas",
            db_type=db_type,
            path=file1_path,
            recursive=True,
            match_filename=None,
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            min_paragraphs_length=10,
            index=index,
        )

        # Just wait for the update to be done
        await ds_client.client.indices.refresh()
        assert await ds_client.count_documents(index) == 5

        # Mock the requests to the server
        content = {
            "uid": "article_uid_5",
            "authors": "fake_authors",
            "title": "fake_title",
            "abstract": [
                "abstract",
            ],
            "pubmed_id": "fake_pubmed_id",
            "pmc_id": "fake_pmc_id",
            "doi": "fake_doi",
            "arxiv_id": "fake_arxiv_id",
            "date": datetime(1700, 1, 1).strftime("%Y-%m-%d"),
            "section_paragraphs": [("Section 1", "Paragraph 1")],
            "journal": "1234-5678",
            "article_type": "Journal article",
        }

        httpx_mock.add_response(
            method="POST",
            url="http://localhost/fake_parser",
            json=content,
        )
        # Test excluding long paragraphs
        await run(
            db_url="zdadas",
            db_type=db_type,
            path=file1_path,
            recursive=True,
            match_filename=None,
            parser_url="http://localhost/fake_parser",
            multipart_params=None,
            max_concurrent_requests=1,
            articles_per_bulk=10,
            min_paragraphs_length=0,
            max_paragraphs_length=10,
            index=index,
        )

        # Just wait for the update to be done
        await ds_client.client.indices.refresh()
        assert await ds_client.count_documents(index) == 6
