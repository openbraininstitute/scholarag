"""Base classes for document stores."""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable, Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr

logger = logging.getLogger(__name__)


class BaseSearch(BaseModel, ABC):
    """Base class for sync document stores."""

    host: str
    port: int
    user: str | None = None
    password: SecretStr | None = None
    use_ssl_and_verify_certs: bool | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @abstractmethod
    def get_available_indexes(self) -> list[str]:
        """Return all available indexes."""

    @abstractmethod
    def remove_index(self, index: str) -> None:
        """Remove an index."""

    @abstractmethod
    def get_document(self, index: str, doc_id: str) -> dict[str, Any]:
        """Return a document.

        Parameters
        ----------
        index
            DB index where documents are stored.
        doc_id
            ID under which the document is indexed.

        Returns
        -------
        doc
            Document retrieved.
        """

    @abstractmethod
    def get_documents(self, index: str, doc_ids: list[str]) -> list[dict[str, Any]]:
        """Return a list of documents.

        Parameters
        ----------
        index
            DB index where documents are stored.
        doc_ids
            list of ids under which the documents are indexed.

        Returns
        -------
        docs
            list of document retrieved.
        """

    @staticmethod
    @abstractmethod
    def _process_search_hits(res: Any) -> list[dict[str, Any]]:
        """Process search hits.

        Parameters
        ----------
        res
            Result of a DB query.

        Returns
        -------
        out
            Processed results.
        """

    @abstractmethod
    def get_index_mappings(self, index: str) -> dict[str, Any]:
        """Return an index mapping."""

    @abstractmethod
    def create_index(
        self,
        index: str,
        settings: dict[str, Any] | None,
        mappings: dict[str, Any] | None,
    ) -> None:
        """Create a new index."""

    @abstractmethod
    def add_fields(
        self,
        index: str,
        settings: dict[str, Any] | None = None,
        mapping: dict[str, Any] | None = None,
    ) -> None:
        """Update the index with a new mapping and settings."""

    @abstractmethod
    def count_documents(self, index: str, query: dict[str, Any] | None = None) -> int:
        """Return the number of documents in an index."""

    @abstractmethod
    def exists(self, index: str, doc_id: str) -> bool:
        """Return True if this document exists in the index."""

    @abstractmethod
    def iter_document(
        self, index: str, query: dict[str, Any] | None = None, size: int = 1000
    ) -> Iterable[dict[str, Any]]:
        """Scan the documents matching a specific query."""

    @abstractmethod
    def add_document(
        self, index: str, doc: dict[str, Any], doc_id: str | None = None
    ) -> None:
        """Index a document."""

    @abstractmethod
    def bulk(self, actions: list[dict[str, Any]], **kwargs: Any) -> None:
        """Bulk upload of documents."""

    @abstractmethod
    def search(
        self,
        index: str,
        query: dict[str, Any] | None = None,
        size: int = 10,
        aggs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Wrap around the search api."""

    @abstractmethod
    def bm25_search(
        self,
        index_doc: str,
        query: str,
        filter_query: dict[str, Any] | None = None,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """BM25 search."""


class AsyncBaseSearch(BaseModel, ABC):
    """Base class for async document stores."""

    host: str
    port: int
    user: str | None = None
    password: SecretStr | None = None
    use_ssl: bool | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    async def get_available_indexes(self) -> list[str]:
        """Return all available indexes."""

    @abstractmethod
    async def remove_index(self, index: str) -> None:
        """Remove an index."""

    @abstractmethod
    async def get_document(self, index: str, doc_id: str) -> dict[str, Any]:
        """Return a document.

        Parameters
        ----------
        index
            DB index where documents are stored.
        doc_id
            ID under which the document is indexed.

        Returns
        -------
        doc
            Document retrieved.
        """

    @abstractmethod
    async def get_documents(
        self, index: str, doc_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Return a list of documents.

        Parameters
        ----------
        index
            DB index where documents are stored.
        doc_ids
            list of ids under which the documents are indexed.

        Returns
        -------
        docs
            list of document retrieved.
        """

    @staticmethod
    @abstractmethod
    def _process_search_hits(res: Any) -> list[dict[str, Any]]:
        """Process search hits.

        Parameters
        ----------
        res
            Result of a DB query.

        Returns
        -------
        out
            Processed results.
        """

    @abstractmethod
    async def get_index_mappings(self, index: str) -> dict[str, Any]:
        """Return an index mapping."""

    @abstractmethod
    async def create_index(
        self, index: str, settings: dict[str, Any], mappings: dict[str, Any]
    ) -> None:
        """Create a new index."""

    @abstractmethod
    async def add_fields(
        self,
        index: str,
        settings: dict[str, Any] | None = None,
        mapping: dict[str, Any] | None = None,
    ) -> None:
        """Update the index with a new mapping and settings."""

    @abstractmethod
    async def count_documents(
        self, index: str, query: dict[str, Any] | None = None
    ) -> int:
        """Return the number of documents in an index."""

    @abstractmethod
    async def exists(self, index: str, doc_id: str) -> bool:
        """Return True if this document exists in the index."""

    @abstractmethod
    def iter_document(
        self, index: str, query: dict[str, Any] | None = None, size: int = 1000
    ) -> AsyncIterable[dict[str, Any]] | AsyncGenerator[int, None]:
        """Scan the documents matching a specific query."""

    @abstractmethod
    async def add_document(
        self, index: str, doc: dict[str, Any], doc_id: str | None = None
    ) -> None:
        """Index a document."""

    @abstractmethod
    async def bulk(self, actions: list[dict[str, Any]], **kwargs: Any) -> None:
        """Bulk upload of documents."""

    @abstractmethod
    async def search(
        self,
        index: str,
        query: dict[str, Any] | None = None,
        size: int = 10,
        aggs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Wrap around the search api."""

    @abstractmethod
    async def bm25_search(
        self,
        index_doc: str,
        query: str,
        filter_query: dict[str, Any] | None = None,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """BM25 search."""

    async def close(self) -> None:
        """Close the aiohttp session."""
