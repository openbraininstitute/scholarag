"""Test embedding pipeline."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from httpx._exceptions import HTTPError
from scholarag.services import ParsingService


@pytest.mark.parametrize(
    "parser",
    [
        "tei_xml",
        "jats_xml",
        "pubmed_xml",
        "pubmed_xml",
        "pubmed_xml",
        "xocs_xml",
        "pypdf_pdf",
    ],
)
def test_run(parser, tmp_path, httpx_mock):
    """Test etl."""
    extension = "xml" if "xml" in parser else "pdf"
    text = "This is by far the best xml (or pdf) i have ever seen."
    with open(tmp_path / f"file.{extension}", "w") as f:
        f.write(text)

    # Mock the response from the ETL API
    parsing_result = {
        "title": "Article Title",
        "authors": ["Forenames 1 Lastname 1", "Lastname 2"],
        "abstract": ["Abstract Paragraph 1", "Abstract Paragraph 2"],
        "section_paragraphs": [],
        "pubmed_id": "123456",
        "pmc_id": "PMC12345",
        "arxiv_id": None,
        "doi": "10.0123/issn.0123-4567",
        "uid": "0e8400416a385b9a62d8178539b76daf",
        "date": None,
    }

    httpx_mock.add_response(
        url=f"http://localhost/{parser}", method="POST", json=parsing_result
    )

    # Run the test
    etl_service = ParsingService()
    file = Path(tmp_path / f"file.{extension}")
    multipart_params = {"amazing_parameter": True, "terrible_parameter": 0}

    parsed = etl_service.run(
        files=[file], url=f"http://localhost/{parser}"
    )  # test with one file only.

    assert parsed == [parsing_result]

    parsed = etl_service.run(
        files=[file, file, file], url=f"http://localhost/{parser}"
    )  # test with multiple files.

    assert parsed == [parsing_result] * 3

    parsed = etl_service.run(
        url=f"http://localhost/{parser}",
        files=[file],
        multipart_params=multipart_params,
    )  # test with parameters.

    assert parsed == [parsing_result]


@pytest.mark.parametrize(
    "parser",
    [
        "tei_xml",
        "jats_xml",
        "pubmed_xml",
        "pubmed_xml",
        "pubmed_xml",
        "xocs_xml",
        "pypdf_pdf",
    ],
)
@pytest.mark.asyncio
async def test_arun(parser, tmp_path, httpx_mock):
    """Test etl."""
    extension = "xml" if "xml" in parser else "pdf"
    text = "This is by far the best xml (or pdf) i have ever seen."
    with open(tmp_path / f"file.{extension}", "w") as f:
        f.write(text)

    # Mock the response from the ETL API
    parsing_result = {
        "title": "Article Title",
        "authors": ["Forenames 1 Lastname 1", "Lastname 2"],
        "abstract": ["Abstract Paragraph 1", "Abstract Paragraph 2"],
        "section_paragraphs": [],
        "pubmed_id": "123456",
        "pmc_id": "PMC12345",
        "arxiv_id": None,
        "doi": "10.0123/issn.0123-4567",
        "uid": "0e8400416a385b9a62d8178539b76daf",
        "date": None,
    }

    httpx_mock.add_response(
        url=f"http://localhost/{parser}", method="POST", json=parsing_result
    )

    # Run the test
    etl_service = ParsingService()
    file = Path(tmp_path / f"file.{extension}")
    multipart_params = {"amazing_parameter": True, "terrible_parameter": 0}
    parsed = await etl_service.arun(
        files=[file], url=f"http://localhost/{parser}"
    )  # Test async

    assert parsed == [parsing_result]

    parsed = await etl_service.arun(
        files=[file, file, file], url=f"http://localhost/{parser}"
    )  # test with multiple files async.

    assert parsed == [parsing_result] * 3

    parsed = await etl_service.arun(
        url=f"http://localhost/{parser}",
        files=[file],
        multipart_params=multipart_params,
    )  # test with parameters async.

    assert parsed == [parsing_result]


@pytest.mark.asyncio
async def test_asend_request_errors(httpx_mock, tmp_path):
    # File has the wrong type
    etl_service = ParsingService()
    httpx_client = AsyncClient()
    with pytest.raises(ValueError):
        _ = await etl_service.asend_request(
            httpx_client=httpx_client, url="wrong-url", file="wrong-file"
        )

    # Wrong status code
    file = Path(tmp_path / "file.txt")
    file.touch()

    httpx_mock.add_response(status_code=404, url="http://localhost/")

    with pytest.raises(ValueError) as error1:
        _ = await etl_service.asend_request(
            httpx_client=httpx_client,
            url="http://localhost/",
            file=file,
        )

    assert (
        str(error1.value)
        == f"Something wrong happened for the body {file}. The status code is 404."
    )

    # HTTP Error redirection
    httpx_mock.add_exception(HTTPError(message="this is an error"))

    with pytest.raises(HTTPError) as error2:
        _ = await etl_service.asend_request(
            httpx_client=httpx_client,
            url="http://localhost/",
            file=file,
        )

    assert str(error2.value) == f"Something wrong happened for the body {file}"
