"""Tests of the QA endpoints."""

import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from openai import BadRequestError
from scholarag.app.config import Settings, SettingsDB, SettingsMetadata
from scholarag.app.dependencies import get_settings
from scholarag.app.main import app
from scholarag.app.routers.qa import GenerativeQAResponse, ParagraphMetadata
from scholarag.document_stores import AsyncOpenSearch
from scholarag.generative_question_answering import (
    ERROR_SEPARATOR,
    SOURCES_SEPARATOR,
    GenerativeQAWithSources,
)

from app.dependencies_overrides import (
    override_ds_client,
    override_generative_qas,
    override_passthrough,
    override_reranker,
    override_rts,
)


def test_generative_qa(app_client, mock_http_calls):
    """Test the generative QA endpoint with a fake LLM."""
    override_ds_client()
    fake_rts, _ = override_rts(has_context=True)
    override_generative_qas(has_answer=True)

    params = {
        "article_types": ["thesis"],
        "authors": ["Emilie Delattre", "Jan Krepl", "Csaba Zsolnai", "Nicolas Frank"],
        "date_from": "2022-03-01",
        "date_to": "2022-12-31",
    }
    expected_query = {
        "bool": {
            "must": [
                {"terms": {"article_type": params["article_types"]}},
                {"terms": {"authors": params["authors"]}},
                {"range": {"date": {"gte": params["date_from"]}}},
                {"range": {"date": {"lte": params["date_to"]}}},
            ]
        }
    }
    response = app_client.post(
        "/qa/generative",
        params=params,
        json={"query": "aaa"},
    )

    assert response.status_code == 200
    used_query = fake_rts.arun.await_args.kwargs["db_filter"]
    assert used_query == expected_query

    response_body = response.json()

    expected_keys = set(GenerativeQAResponse.model_json_schema()["properties"].keys())
    metadata_expected_keys = set(
        ParagraphMetadata.model_json_schema()["properties"].keys()
    )

    assert response_body.keys() == expected_keys

    for context_metadata in response_body["metadata"]:
        assert set(context_metadata.keys()) == metadata_expected_keys

    assert response_body["answer"] == "This is a perfect answer."


@pytest.mark.parametrize("reranker_k", [1, 2, 4, 8, 15])
def test_generative_qa_reranker(app_client, reranker_k, mock_http_calls):
    """Test the generative QA endpoint."""
    override_ds_client()
    fakeqas = override_generative_qas(has_answer=True)
    _, sorted_scores_index = override_reranker(reranker_k=reranker_k)
    _, list_document_ids = override_rts(has_context=True)

    fakeqas.arun.side_effect = lambda **params: (
        {
            "answer": "This is a perfect answer.",
            "paragraphs": list(range(reranker_k)),
            "raw_answer": (
                f"This is a perfect answer /n{SOURCES_SEPARATOR}:"
                f" {', '.join([str(i) for i in range(reranker_k)])}"
            ),
        },
        None,
    )

    params = {}

    response = app_client.post(
        "/qa/generative",
        params=params,
        json={
            "query": "aaa",
            "retriever_k": 40,
            "reranker_k": reranker_k,
            "use_reranker": True,
        },
    )

    assert response.status_code == 200

    response_body = response.json()
    assert len(response_body["metadata"]) == reranker_k

    expected_keys = set(GenerativeQAResponse.model_json_schema()["properties"].keys())
    metadata_expected_keys = set(
        ParagraphMetadata.model_json_schema()["properties"].keys()
    )

    assert response_body.keys() == expected_keys

    for context_metadata in response_body["metadata"]:
        assert set(context_metadata.keys()) == metadata_expected_keys
    for resp, expected in zip(response.json()["metadata"], sorted_scores_index):
        assert resp["reranking_score"] == expected[0]
        assert resp["ds_document_id"] == list_document_ids[expected[-1]]


def test_generative_qa_no_answer_code_1(app_client):
    """Test the generative QA endpoint when there is no documents retrieved."""
    # Generative QAS has to be overwritten since it needs to be instantiated before returning code 1.
    override_ds_client()
    override_rts(has_context=False)
    override_generative_qas(has_answer=False)

    response = app_client.post(
        "/qa/generative",
        json={"query": "aaa"},
    )

    response_body = response.json()

    assert response.status_code == 500
    assert response_body["detail"].keys() == {"code", "detail"}
    assert response_body["detail"]["code"] == 1


def test_generative_qa_no_answer_code_2(app_client, mock_http_calls):
    """Test the generative QA endpoint when there is no answer to the query."""
    override_ds_client()
    override_rts(has_context=True)
    override_generative_qas(has_answer=False)

    response = app_client.post(
        "/qa/generative",
        json={"query": "aaa"},
    )

    response_body = response.json()

    assert response.status_code == 500
    assert response_body["detail"].keys() == {
        "code",
        "detail",
        "raw_answer",
    }
    assert response_body["detail"]["code"] == 2
    assert (
        response_body["detail"]["raw_answer"]
        == f"{ERROR_SEPARATOR}I don't know \n{SOURCES_SEPARATOR}:"
    )


def test_generative_qa_code_6(app_client, mock_http_calls):
    """Test the generative QA endpoint when the answer is incomplete."""
    override_ds_client()
    override_rts(has_context=True)
    override_generative_qas(has_answer=False, complete_answer=False)

    response = app_client.post(
        "/qa/generative",
        json={"query": "aaa"},
    )

    response_body = response.json()

    assert response.status_code == 500
    assert response_body["detail"].keys() == {
        "code",
        "detail",
        "raw_answer",
    }
    assert response_body["detail"]["code"] == 6
    assert response_body["detail"]["raw_answer"] == f"{ERROR_SEPARATOR}I don't"


def test_generative_qa_context_too_long(app_client, mock_http_calls):
    """Test the generative QA endpoint when there is too much tokens in the query."""
    override_ds_client()
    override_rts(has_context=True)
    fakeqas = override_generative_qas(has_answer=False)
    fakeqas.arun.side_effect = BadRequestError(
        message=(
            "This model's maximum context length is 4097 tokens. However, your messages"
            " resulted in 4849 tokens. Please reduce the length of the messages."
        ),
        response=httpx.Response(
            request=httpx.Request("GET", "fake-url"), status_code=413
        ),
        body={
            "message": (
                "This model's maximum context length is 4097 tokens. However, your"
                " messages resulted in 4849 tokens. Please reduce the length of the"
                " messages."
            ),
        },
    )

    response = app_client.post(
        "/qa/generative",
        json={"query": "aaa"},
    )
    response_body = response.json()

    assert response.status_code == 413
    assert response_body["detail"].keys() == {
        "code",
        "detail",
    }
    assert (
        response_body["detail"]["detail"]
        == "This model's maximum context length is 4097 tokens. However, your messages"
        " resulted in 4849 tokens. Please reduce the length of the messages."
    )
    assert response_body["detail"]["code"] == 4


def test_generative_qa_metadata_retriever_no_external_apis(app_client):
    """Test the generative QA endpoint with a fake LLM."""

    def get_settings_no_external_apis():
        settings = Settings(
            db=SettingsDB(
                db_type="opensearch", index_paragraphs="dummy", host="", port=0
            ),
            metadata=SettingsMetadata(external_apis=False),
        )
        return settings

    app.dependency_overrides[get_settings] = get_settings_no_external_apis

    override_ds_client()
    override_rts(has_context=True)
    override_generative_qas(has_answer=True)

    params = {}
    response = app_client.post(
        "/qa/generative",
        params=params,
        json={"query": "aaa"},
    )

    assert response.status_code == 200
    response_body = response.json()

    for context_metadata in response_body["metadata"]:
        assert context_metadata["journal_name"] is None
        assert context_metadata["cited_by"] is None


def test_generative_qa_metadata_retriever_external_apis(app_client):
    """Test the generative QA endpoint with a fake LLM."""
    override_ds_client()
    override_rts(has_context=True)
    override_generative_qas(has_answer=True)

    async def get_journal_name(issn, httpx_client):
        return "journalname1"

    async def get_citation_count(doi, httpx_client):
        return 12

    params = {}
    with patch(
        "scholarag.retrieve_metadata.get_citation_count",
        new=get_citation_count,
    ):
        with patch(
            "scholarag.retrieve_metadata.get_journal_name",
            new=get_journal_name,
        ):
            with patch("scholarag.retrieve_metadata.recreate_abstract") as abstract:
                abstract.__name__ = "recreate_abstract"
                abstract.return_value = "Great abstract"
                response = app_client.post(
                    "/qa/generative",
                    params=params,
                    json={"query": "aaa"},
                )

    assert response.status_code == 200
    response_body = response.json()

    for context_metadata in response_body["metadata"]:
        assert context_metadata["journal_name"] == "journalname1"
        assert context_metadata["cited_by"] == 12


async def streamed_response(**kwargs):
    response = [
        "This",
        " is",
        " an",
        " amazingly",
        " well",
        " streamed",
        " response",
        ".",
        " I",
        " can",
        "'t",
        " believe",
        " how",
        " good",
        " it",
        " is",
        "!",
        "\n",
        "<b",
        "bs",
        "_sources",
        ">:",
        " ",
        "0",
        ",",
        " ",
        "1",
        ",",
        " ",
        "2",
    ]
    for word in response:
        yield word
    raise RuntimeError("stop")


async def streamed_response_no_answer(**kwargs):
    response = [
        "<b",
        "bs",
        "_error",
        ">I",
        " don",
        r"'t",
        " know",
        r" \"",
        "n",
        "<b",
        "bs",
        "_sources",
        ">:",
    ]
    for word in response:
        yield word
    raise RuntimeError("stop")


@pytest.mark.asyncio
async def test_streamed_generative_qa(app_client, redis_fixture, mock_http_calls):
    """Test the generative QA endpoint with a fake LLM."""
    mock = override_ds_client()
    mock.mock_add_spec(AsyncOpenSearch)
    override_rts(has_context=True)
    FakeQAS = override_generative_qas()
    FakeQAS.astream = streamed_response
    FakeQAS._process_raw_output = GenerativeQAWithSources._process_raw_output

    params = {}
    expected_tokens = (
        "This is an amazingly well streamed response. I can't believe how good it is!"
    )
    with patch("scholarag.app.middleware.get_cache", redis_fixture):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            async with http_client.stream(
                method="post",
                url="/qa/streamed_generative",
                params=params,
                json={"query": "aaa"},
            ) as response:
                # Check that saving in caching worked correctly
                assert response.headers["X-fastapi-cache"] == "Miss"
                assert response.status_code == 200

                i = 0
                resp = []
                passed = False
                async for chunk in response.aiter_text(1):
                    resp.append(chunk)
                    if not passed:
                        assert chunk == expected_tokens[i]
                        i += 1
                    if chunk == expected_tokens[-1]:
                        passed = True

        resp = "".join(resp)

        assert "<bbs_json_data>" in resp
        assert resp.split("<bbs_json_data>")[0].endswith("\n")

        index_response = resp.split("<bbs_json_data>")
        response_str = index_response[1]
        answer = json.loads(response_str)
        expected_keys = set(
            GenerativeQAResponse.model_json_schema()["properties"].keys()
        )
        metadata_expected_keys = set(
            ParagraphMetadata.model_json_schema()["properties"].keys()
        )

        assert answer.keys() == expected_keys

        for context_metadata in answer["metadata"]:
            assert set(context_metadata.keys()) == metadata_expected_keys

        # Making sure that caching worked for the second call
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            response = await http_client.post(
                url="/qa/streamed_generative",
                params=params,
                json={"query": "aaa"},
            )
            assert response.headers["X-fastapi-cache"] == "Hit"
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_streamed_generative_qa_error(app_client, redis_fixture):
    """Test the streamed generative QA endpoint returning an."""
    mock = override_ds_client()
    mock.mock_add_spec(AsyncOpenSearch)
    override_rts(has_context=True)
    FakeQAS = override_generative_qas()
    FakeQAS.astream = streamed_response_no_answer
    FakeQAS._process_raw_output = GenerativeQAWithSources._process_raw_output

    params = {}
    expected_tokens = "<bbs_json_error>"  # We expect an empty answer.

    with patch("scholarag.app.middleware.get_cache", redis_fixture):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            async with http_client.stream(
                method="post",
                url="/qa/streamed_generative",
                params=params,
                json={"query": "aaa"},
            ) as response:
                # Check that caching worked correctly
                assert response.headers["X-fastapi-cache"] == "Miss"
                assert response.status_code == 200

                i = 0
                resp = []
                passed = False
                async for chunk in response.aiter_text(1):
                    resp.append(chunk)
                    if not passed:
                        assert chunk == expected_tokens[i]
                        i += 1
                    if chunk == expected_tokens[-1]:
                        passed = True

        resp = "".join(resp)
        assert "<bbs_json_error>" in resp

        index_response = resp.split("<bbs_json_error>")
        response_str = index_response[1]
        assert not index_response[0]  # No text if the model doesn't know the answer.
        error = json.loads(response_str)["Error"]

        with pytest.raises(HTTPException):
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Status_code={error['status_code']}, Code={error['code']},"
                    f" message={error['detail']}"
                ),
            )

        # Making sure that caching worked for the second call
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            response = await http_client.post(
                url="/qa/streamed_generative",
                params=params,
                json={"query": "aaa"},
            )
            assert response.headers["X-fastapi-cache"] == "Hit"
            assert response.status_code == 200


def test_passthrough(app_client):
    override_passthrough()

    response = app_client.post("/qa/passthrough", json={"query": "Great question"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Great answer."


def test_passthrough_incomplete(app_client):
    override_passthrough(finish_reason="length")
    response = app_client.post("/qa/passthrough", json={"query": "Great question"})

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == 6


def test_passthrough_too_many_tokens(app_client):
    FakePT = override_passthrough()
    FakePT.chat.completions.create.side_effect = BadRequestError(
        message=(
            "Error code 413: This model's maximum context length is 4097 tokens."
            " However, your messages resulted in 4849 tokens. Please reduce the length"
            " of the messages."
        ),
        response=httpx.Response(
            request=httpx.Request("GET", "fake-url"), status_code=413
        ),
        body=None,
    )
    response = app_client.post("/qa/passthrough", json={"query": "Great question"})

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == 4
