"""Test re-ranking pipeline."""

from unittest.mock import AsyncMock, Mock

import pytest
from cohere import (
    RerankResponse,
    RerankResponseResultsItem,
    RerankResponseResultsItemDocument,
)
from scholarag.services import CohereRerankingService

RESULTS = [
    RerankResponseResultsItem(
        document=RerankResponseResultsItemDocument(
            text="Berlin is the capital of Germany"
        ),
        index=2,
        relevance_score=0.9756467938423157,
    ),
    RerankResponseResultsItem(
        document=RerankResponseResultsItemDocument(
            text="The mountains in Switzerland are impressive"
        ),
        index=0,
        relevance_score=2.7073356250184588e-05,
    ),
    RerankResponseResultsItem(
        document=RerankResponseResultsItemDocument(text="Yesterday was a nice day"),
        index=1,
        relevance_score=2.4477983970427886e-05,
    ),
]


def test_run():
    """Test re-ranking pipeline."""
    # Run the test
    client_mock = Mock()
    client_mock.rerank.return_value = RerankResponse(
        id="047a2fc0-f640-46ad-97d4-aa57fdff3b65",
        results=RESULTS,
        meta={"api_version": {"version": "1"}},
    )

    crs = CohereRerankingService(api_key="asdadafsdazf")
    crs.client = client_mock
    answers = crs.run(
        query="What is the capital of Germany?",
        contexts=[
            "The mountains in Switzerland are impressive",
            "Yesterday was a nice day",
            "Berlin is the capital of Germany",
        ],
    )

    assert answers == [
        {
            "text": "Berlin is the capital of Germany",
            "score": 0.9756467938423157,
            "index": 2,
        },
        {
            "text": "The mountains in Switzerland are impressive",
            "score": 2.7073356250184588e-05,
            "index": 0,
        },
        {
            "text": "Yesterday was a nice day",
            "score": 2.4477983970427886e-05,
            "index": 1,
        },
    ]


@pytest.mark.asyncio
async def test_arun():
    """Test re-ranking pipeline."""
    async_client_mock = AsyncMock()
    async_client_mock.rerank.return_value = RerankResponse(
        id="047a2fc0-f640-46ad-97d4-aa57fdff3b65",
        results=RESULTS,
        meta={"api_version": {"version": "1"}},
    )

    crs = CohereRerankingService(api_key="asdadafsdazf")
    crs.async_client = async_client_mock

    answers = await crs.arun(
        query="What is the capital of Germany?",
        contexts=[
            "The mountains in Switzerland are impressive",
            "Yesterday was a nice day",
            "Berlin is the capital of Germany",
        ],
    )
    await crs.async_client.close()
    assert answers == [
        {
            "text": "Berlin is the capital of Germany",
            "score": 0.9756467938423157,
            "index": 2,
        },
        {
            "text": "The mountains in Switzerland are impressive",
            "score": 2.7073356250184588e-05,
            "index": 0,
        },
        {
            "text": "Yesterday was a nice day",
            "score": 2.4477983970427886e-05,
            "index": 1,
        },
    ]


def test_cohere_reranker_error():
    """Test cohere reranker fail when no api-key is specified."""
    with pytest.raises(ValueError):
        _ = CohereRerankingService()


@pytest.mark.parametrize("reranker_k", [1, 2, 3])
@pytest.mark.asyncio
async def test_cohere_reranker_rerank(reranker_k):
    """Test cohere reranker rerank method."""
    async_client_mock = AsyncMock()

    # This rerank function is called inside `arun` method
    # called inside the `rerank` method of our CohereRerankingService
    async_client_mock.rerank.return_value = RerankResponse(
        id="047a2fc0-f640-46ad-97d4-aa57fdff3b65",
        results=RESULTS,
        meta={"api_version": {"version": "1"}},
    )

    contexts = [
        {"text": "The mountains in Switzerland are impressive"},
        {"text": "Yesterday was a nice day"},
        {"text": "Berlin is the capital of Germany"},
    ]
    crs = CohereRerankingService(api_key="asdadafsdazf")
    crs.async_client = async_client_mock

    new_contexts, new_contexts_text, scores, indices = await crs.rerank(
        query="This is a test query",
        contexts=contexts,
        reranker_k=reranker_k,
    )

    assert len(new_contexts) == reranker_k
    assert len(new_contexts_text) == reranker_k
    assert len(scores) == reranker_k
    assert len(indices) == reranker_k

    expected_new_contexts = [
        {"text": "Berlin is the capital of Germany"},
        {"text": "The mountains in Switzerland are impressive"},
        {"text": "Yesterday was a nice day"},
    ]

    assert new_contexts == expected_new_contexts[:reranker_k]
    assert (
        scores
        == (0.9756467938423157, 2.7073356250184588e-05, 2.4477983970427886e-05)[
            :reranker_k
        ]
    )
    assert indices == (2, 0, 1)[:reranker_k]
