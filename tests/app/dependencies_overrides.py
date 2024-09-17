"""Overrides functionalities endpoints."""

import random
from unittest.mock import AsyncMock

from openai.types.chat.chat_completion import (
    ChatCompletion,
    ChatCompletionMessage,
    Choice,
)
from scholarag.app.config import Settings
from scholarag.app.dependencies import (
    get_ds_client,
    get_generative_qas,
    get_openai_client,
    get_reranker,
    get_rts,
    get_settings,
)
from scholarag.app.main import app
from scholarag.document_stores import AsyncBaseSearch
from scholarag.generative_question_answering import GenerativeQAOutput


def override_rts(has_context=True):
    """Get a fake retrieval service."""
    FakeRTS = AsyncMock()
    list_document_ids = ["abc", "def", "ghi", "jkl"] * 300
    if has_context:
        FakeRTS.arun.side_effect = lambda **params: [
            {
                "article_id": "ID12345",
                "authors": ["Alice", "Bob"],
                "doi": "ID12345",
                "paragraph_id": "q3jGeoQBVjZFRS3h-y27",
                "pubmed_id": "34258598",
                "score": 0.84878886,
                "section": "Methods",
                "document_id": list_document_ids[i],
                "text": (
                    "This is the actual text of the paragraph. This is context number"
                    f" {i}."
                ),
                "journal": "1234-5678",
                "title": "Very important article",
                "article_type": "Journal Article",
            }
            for i in range(params["retriever_k"])
        ]
    else:
        FakeRTS.arun.side_effect = lambda **params: []
    app.dependency_overrides[get_rts] = lambda: FakeRTS
    return FakeRTS, list_document_ids


def override_ds_client_with_redis():
    """Get a fake Elasticsearch client."""
    mock = AsyncMock(spec=AsyncBaseSearch)
    mock.close = AsyncMock()
    app.dependency_overrides[get_ds_client] = lambda: mock
    test_settings = Settings(
        db={
            "db_type": "elasticsearch",
            "index_paragraphs": "foo",
            "index_journals": "bar",
            "host": "host.com",
            "port": 1515,
        },
        redis={
            "host": "localhost",
            "port": 6380,
        },
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    return mock


def override_ds_client():
    """Get a fake Elasticsearch client."""
    mock = AsyncMock(spec=AsyncBaseSearch)
    mock.close = AsyncMock()
    app.dependency_overrides[get_ds_client] = lambda: mock

    return mock


def override_reranker(reranker_k):
    FakeRS = AsyncMock()
    scores = [i / reranker_k for i in range(1, reranker_k + 1)]
    random.shuffle(scores)
    sorted_scores_index = sorted(zip(scores, range(reranker_k)), reverse=True)
    FakeRS.rerank.side_effect = lambda **params: [
        [params["contexts"][i] for (_, i) in sorted_scores_index],
        [params["contexts"][i]["text"] for (_, i) in sorted_scores_index],
        [score for (score, _) in sorted_scores_index],
        [i for (_, i) in sorted_scores_index],
    ]
    app.dependency_overrides[get_reranker] = lambda: FakeRS
    return FakeRS, sorted_scores_index


def override_generative_qas(has_answer=True, complete_answer=True):
    """Get a fake question answering service."""
    FakeQAS = AsyncMock()
    FakeQAS.arun.__name__ = "arun"
    if has_answer:
        FakeQAS.arun.side_effect = lambda **params: (
            GenerativeQAOutput(
                has_answer=True,
                answer="This is a perfect answer.",
                paragraphs=[0, 1, 2],
            ),
            "stop",
        )
    else:
        if complete_answer:
            FakeQAS.arun.side_effect = lambda **params: (
                GenerativeQAOutput(
                    has_answer=False, answer="I don't know.", paragraphs=[]
                ),
                "stop",
            )
        else:
            FakeQAS.arun.side_effect = lambda **params: (
                GenerativeQAOutput(has_answer=False, answer="I don't", paragraphs=[]),
                "length",
            )
    app.dependency_overrides[get_generative_qas] = lambda: FakeQAS
    return FakeQAS


def override_passthrough(finish_reason="stop"):
    FakePT = AsyncMock()
    FakePT.chat.completions.create.side_effect = lambda **params: ChatCompletion(
        id="qbcd",
        created=123445,
        model="gpt-ni.colas-turbo",
        object="chat.completion",
        choices=[
            Choice(
                finish_reason=finish_reason,
                index=0,
                message=ChatCompletionMessage(
                    content="Great answer.", role="assistant"
                ),
            )
        ],
    )

    app.dependency_overrides[get_openai_client] = lambda: FakePT
    return FakePT
