"""Class to use the Cohere reranking service."""

import logging
import time
from typing import Any

import cohere
from pydantic import BaseModel, ConfigDict, model_validator

logger = logging.getLogger(__name__)


class CohereRerankingService(BaseModel):
    """Main class to call Cohere's reranking endpoint."""

    api_key: str | None = None
    client: cohere.Client
    async_client: cohere.AsyncClient
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    def create_client(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Instantiate the clients upon class creation."""
        if values.get("api_key") is not None:
            client = cohere.Client(values["api_key"])
            async_client = cohere.AsyncClient(values["api_key"])
        else:
            raise ValueError(
                "No API key provided. You must provide a Cohere API key to call methods"
                " of this class."
            )
        values["client"] = client
        values["async_client"] = async_client
        return values

    def run(
        self, query: str, contexts: list[str]
    ) -> list[dict[str, str | float | int | None]]:
        """Return contexts in decreasing likeliness order of holding the answer to the question.

        Parameters
        ----------
        query
            Question to answer.
        contexts
            Contexts to rerank.

        Returns
        -------
        response: list[dict[str, str | float | int | None]]
            List of dictionaries containing in score order the text and the associated score.
        """
        response = self.client.rerank(
            model="rerank-english-v2.0",
            query=query,
            documents=contexts,
            return_documents=True,
            top_n=len(contexts),
            max_chunks_per_doc=10_000 // len(contexts),
        )
        reranked_contexts = [
            {
                "text": (
                    reranked.document.text if reranked.document is not None else None
                ),
                "score": reranked.relevance_score,
                "index": reranked.index,
            }
            for reranked in response.results
        ]
        return reranked_contexts

    async def arun(
        self, query: str, contexts: list[str]
    ) -> list[dict[str, str | float | int | None]]:
        """Return contexts in decreasing likeliness order of holding the answer to the question.

        Parameters
        ----------
        query
            Question to answer.
        contexts
            Contexts to rerank.

        Returns
        -------
        response: list[dict[str, str | float | int | None]]
            List of dictionaries containing in score order the text and the associated score.
        """
        response = await self.async_client.rerank(
            model="rerank-english-v2.0",
            query=query,
            documents=contexts,
            return_documents=True,
            top_n=len(contexts),
            max_chunks_per_doc=10_000 // len(contexts),
        )

        reranked_contexts = [
            {
                "text": (
                    reranked.document.text if reranked.document is not None else None
                ),
                "score": reranked.relevance_score,
                "index": reranked.index,
            }
            for reranked in response.results
        ]
        return reranked_contexts

    async def rerank(
        self,
        query: str,
        contexts: list[dict[str, Any]],
        reranker_k: int,
    ) -> tuple[list[dict[str, Any]], list[str], tuple[float], tuple[int]]:
        """Run the reranking logic.

        Parameters
        ----------
        query
            Query to use to handle the reranking of the contexts.
        contexts
            Paragraphs saved under dictionaries with metadata to rerank in regard of the query.
        reranker_k
            Number of paragraphs to keep after the reranking.

        Returns
        -------
        new_contexts: list[dict[str, Any]]
            Contexts kept and reordered after the reranking.
        new_contexts_text: list[str]
            Contexts text after reranking.
        scores: tuple[float]
            Scores given by reranker for the different contexts
        indices: tuple[int]
            Initial indices of the contexts before the reranking phase.
        """
        contexts_text = [context["text"] for context in contexts]
        logger.info(
            f"Reranking {len(contexts_text)} contexts with Cohere reranker. "
            f"Keeping the {reranker_k} most relevant ones..."
        )
        start = time.time()
        reranked = await self.arun(query=query, contexts=contexts_text)
        logger.info(f"Reranking took {time.time() - start}s.")
        reranked_contexts, scores, indices = zip(
            *[
                (context["text"], context["score"], context["index"])
                for context in reranked[:reranker_k]
            ]
        )
        logger.info(f"New contexts position: {indices} with scores: {scores}.")
        new_contexts = [contexts[i] for i in indices]
        new_contexts_text = list(reranked_contexts)
        return new_contexts, new_contexts_text, scores, indices
