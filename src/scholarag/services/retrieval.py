"""Run semantic search."""

import logging
from typing import Any

import pydantic.v1 as pydantic

from scholarag.document_stores import AsyncBaseSearch, BaseSearch

logger = logging.getLogger(__name__)


class RetrievalService(pydantic.BaseModel):
    """Class to run semantic search.

    Parameters
    ----------
    db_index_paragraphs
        Document store index for paragraphs.
    """

    db_index_paragraphs: str

    def run(
        self,
        ds_client: BaseSearch,
        query: str,
        retriever_k: int = 10,
        db_filter: dict[str, Any] | None = None,
        max_length: int = 100000,
    ) -> list[dict[str, Any]]:
        """Run bm25.

        Parameters
        ----------
        ds_client
            Documents store client.
        query
            Query to retrieve the most relevant documents from the documents store.
        retriever_k
            Number of documents to retrieve.
        db_filter
            Filtering parameters to add to the retrieval.
        max_length
            Maximum length of the documents to retrieve.

        Returns
        -------
        res: list[dict[str, Any]]
            List of retrieved documents saved under dictionary with all metadata.
        """
        res = ds_client.bm25_search(
            index_doc=self.db_index_paragraphs,
            query=query,
            filter_query=db_filter,
            k=retriever_k,
        )

        # Filtering long paragraphs
        res = [r for r in res if len(r["text"]) < max_length]
        return res

    async def arun(
        self,
        ds_client: AsyncBaseSearch,
        query: str,
        retriever_k: int = 10,
        db_filter: dict[str, Any] | None = None,
        max_length: int = 100000,
    ) -> list[dict[str, Any]]:
        """Run bm25.

        Parameters
        ----------
        ds_client
            Documents store client.
        query
            Query to retrieve the most relevant documents from the documents store.
        retriever_k
            Number of documents to retrieve.
        db_filter
            Filtering parameters to add to the retrieval.
        max_length
            Maximum length of the documents to retrieve.

        Returns
        -------
        res: list[dict[str, Any]]
            List of retrieved documents saved under dictionary with all metadata.
        """
        res = await ds_client.bm25_search(
            index_doc=self.db_index_paragraphs,
            query=query,
            filter_query=db_filter,
            k=retriever_k,
        )

        # Filtering long paragraphs
        res = [r for r in res if len(r["text"]) < max_length]
        return res
