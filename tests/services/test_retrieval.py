"""test_semantic_search pipeline."""

from unittest.mock import AsyncMock, Mock

import pytest
from scholarag.document_stores import AsyncBaseSearch, BaseSearch
from scholarag.services.retrieval import RetrievalService


def test_semantic_search_real(monkeypatch):
    """Test semantic search."""
    query = "That is a happy person."

    fake_client_instance = Mock(spec=BaseSearch)
    fake_client_instance.bm25_search.return_value = [{"text": "bbb"}]

    monkeypatch.setattr(
        "scholarag.services.retrieval.BaseSearch",
        Mock(return_value=fake_client_instance),
    )

    retrieval_service = RetrievalService(db_index_paragraphs="test_paragraphs")
    response_bm25 = retrieval_service.run(
        fake_client_instance, query=query, retriever_k=3
    )

    assert response_bm25 == [{"text": "bbb"}]


def test_bm25_with_long_paragraphs(monkeypatch):
    """Test semantic search."""
    query = "That is a happy person."

    fake_client_instance = Mock(spec=BaseSearch)
    fake_client_instance.bm25_search.return_value = [
        {"text": "b" * 1000000},
        {"text": "bbb"},
    ]

    monkeypatch.setattr(
        "scholarag.services.retrieval.BaseSearch",
        Mock(return_value=fake_client_instance),
    )

    retrieval_service = RetrievalService(
        db_index_paragraphs="test_paragraphs",
    )
    response_bm25 = retrieval_service.run(
        fake_client_instance, query=query, retriever_k=3
    )

    assert response_bm25 == [{"text": "bbb"}]


@pytest.mark.asyncio
async def test_async_semantic_search_real(monkeypatch):
    """Test semantic search."""
    query = "That is a happy person."

    fake_client_instance = AsyncMock(spec=AsyncBaseSearch)
    fake_client_instance.bm25_search.return_value = [{"text": "bbb"}]

    monkeypatch.setattr(
        "scholarag.services.retrieval.AsyncBaseSearch",
        Mock(return_value=fake_client_instance),
    )

    retrieval_service = RetrievalService(db_index_paragraphs="test_paragraphs")
    response_bm25 = await retrieval_service.arun(
        fake_client_instance, query=query, retriever_k=3
    )

    assert response_bm25 == [{"text": "bbb"}]
