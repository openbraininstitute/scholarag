"""Document store class connecting to Elasticsearch."""

import logging
from collections.abc import AsyncIterable, Iterable
from typing import Any

from elasticsearch import AsyncElasticsearch, Elasticsearch
from elasticsearch.helpers import async_bulk, async_scan, bulk, scan
from pydantic import model_validator

from scholarag.document_stores import AsyncBaseSearch, BaseSearch

logger = logging.getLogger(__name__)

SETTINGS: dict[str, Any] = {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {"analyzer": {"default": {"type": "english"}}},
}

MAPPINGS_PARAGRAPHS: dict[str, Any] = {
    "dynamic": "strict",
    "properties": {
        "article_id": {"type": "keyword"},
        "doi": {"type": "keyword"},
        "pmc_id": {"type": "keyword"},
        "pubmed_id": {"type": "keyword"},
        "arxiv_id": {"type": "keyword"},
        "title": {"type": "text"},
        "authors": {"fields": {"keyword": {"type": "keyword"}}, "type": "text"},
        "journal": {"type": "keyword"},
        "date": {"type": "date", "format": "yyyy-MM-dd"},
        "section": {"type": "keyword"},
        "paragraph_id": {"type": "short"},
        "text": {"type": "text"},
        "article_type": {"type": "keyword"},
    },
}


class ElasticSearch(BaseSearch):
    """Class to use sync Elasticsearch as document store."""

    client: Elasticsearch

    @model_validator(mode="before")
    def connect_to_ds(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Connect to ES."""
        values["use_ssl_and_verify_certs"] = values.get(
            "use_ssl_and_verify_certs", False
        )  # by default we don't use SSL
        if values.get("user") is None and values.get("password") is None:
            client = Elasticsearch(
                f"{values['host']}:{values['port']}",
                verify_certs=values["use_ssl_and_verify_certs"],
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True,
            )
        else:
            client = Elasticsearch(
                f"{values['host']}:{values['port']}",
                basic_auth=(values["user"], values["password"]),
                verify_certs=values["use_ssl_and_verify_certs"],
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True,
            )

        values["client"] = client
        return values

    def get_available_indexes(self) -> list[str]:
        """Return all available indexes."""
        return list(self.client.indices.get_alias().keys())

    def remove_index(self, index: str) -> None:
        """Remove an index."""
        if index not in self.get_available_indexes():
            raise RuntimeError("Index not in the document store")
        self.client.indices.delete(index=index)
        logger.info(f"Index {index} deleted successfully")

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
        if index not in self.get_available_indexes():
            raise RuntimeError("Index not in the document store")
        if not self.client.exists(index=index, id=doc_id):
            raise RuntimeError("Document not in the document store")
        return self.client.get(index=index, id=doc_id)["_source"]

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
        if index not in self.get_available_indexes():
            raise RuntimeError("Index not in the document store")
        docs = self.client.mget(index=index, ids=doc_ids)
        docs_to_return = [
            {"document_id": doc["_id"], **doc["_source"]}
            for doc in docs["docs"]
            if doc["found"]
        ]
        return docs_to_return

    @staticmethod
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
        out = []
        for hit in res["hits"]["hits"]:
            row = {}

            row["article_id"] = hit["_source"].get("article_id")
            row["title"] = hit["_source"].get("title")
            row["authors"] = hit["_source"].get("authors")
            row["doi"] = hit["_source"].get("doi")
            row["pubmed_id"] = hit["_source"].get("pubmed_id")
            row["section"] = hit["_source"].get("section")
            row["date"] = hit["_source"].get("date")
            row["journal"] = hit["_source"].get("journal")
            row["document_id"] = hit["_id"]
            row["paragraph_id"] = hit["_source"].get("paragraph_id")
            row["pmc_id"] = hit["_source"].get("pmc_id")
            row["arxiv_id"] = hit["_source"].get("arxiv_id")
            row["text"] = hit["_source"].get("text")
            row["article_type"] = hit["_source"].get("article_type")
            row["score"] = hit["_score"]

            out.append(row)

        return out

    def get_index_mappings(self, index: str) -> dict[str, Any]:
        """Return an index mapping."""
        return self.client.indices.get_mapping(index=index).raw[index]["mappings"]

    def create_index(
        self,
        index: str,
        settings: dict[str, Any] | None,
        mappings: dict[str, Any] | None,
    ) -> None:
        """Create a new index."""
        if index in self.get_available_indexes():
            raise RuntimeError("Index already in ES")
        self.client.indices.create(index=index, settings=settings, mappings=mappings)
        logger.info(f"Index {index} created successfully")

    def add_fields(
        self,
        index: str,
        settings: dict[str, Any] | None = None,
        mapping: dict[str, Any] | None = None,
    ) -> None:
        """Update the index with a new mapping and settings."""
        if index not in self.get_available_indexes():
            raise RuntimeError("Index not in ES")
        if settings:
            self.client.indices.put_settings(index=index, settings=settings)
        if mapping:
            self.client.indices.put_mapping(index=index, properties=mapping)
        logger.info(f"Index {index} updated successfully.")

    def count_documents(self, index: str, query: dict[str, Any] | None = None) -> int:
        """Return the number of documents in an index.

        Parameters
        ----------
        index
            ES index where documents are stored.
        query
            Optional query to filter the documents to count.

        Returns
        -------
        document_count
            Number of documents in index that respect query.
        """
        if index not in self.get_available_indexes():
            raise RuntimeError("Index not in ES")
        if query is None:
            query = {"match_all": {}}

        return self.client.count(index=index, query=query)["count"]

    def exists(self, index: str, doc_id: str) -> bool:
        """Return True if this document exists in the index.

        Parameters
        ----------
        index
            ES index where documents are stored.
        doc_id
            ID under which the document might be indexed.

        Returns
        -------
            True if the document exists within an index.
        """
        return bool(self.client.exists(index=index, id=doc_id))

    def iter_document(
        self, index: str, query: dict[str, Any] | None = None, size: int = 1000
    ) -> Iterable[dict[str, Any]]:
        """Scan the documents matching a specific query."""
        if query is None:
            query = {"query": {"match_all": {}}}
        doc_gen = scan(self.client, index=index, query=query, size=size)
        return doc_gen

    def add_document(
        self, index: str, doc: dict[str, Any], doc_id: str | None = None
    ) -> None:
        """Index a document.

        Parameters
        ----------
        index
            ES index where documents are stored.
        doc
            Document to index.
        doc_id
            ID under which the document must be indexed.
        """
        if index not in self.get_available_indexes():
            raise RuntimeError("Index not in ES")
        if doc_id and self.client.exists(index=index, id=doc_id):
            raise RuntimeError("Document already in ES")
        self.client.index(index=index, id=doc_id, document=doc)
        logger.info(f"Document {doc_id} indexed successfully.")

    def bulk(
        self,
        actions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        """Bulk upload of documents."""
        bulk(client=self.client, actions=actions, **kwargs)
        logger.info("Successfully updated documents in bulk")

    def search(
        self,
        index: str,
        query: dict[str, Any] | None = None,
        size: int = 10,
        aggs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Wrap around the search api."""
        if query is not None and "query" in query.keys():
            query = query["query"]
        query = postprocess_query(query)
        return self.client.search(
            index=index, query=query, size=size, aggs=aggs, **kwargs
        ).raw

    def bm25_search(
        self,
        index_doc: str,
        query: str,
        filter_query: dict[str, Any] | None = None,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """BM25 search.

        Parameters
        ----------
        index_doc
            ES index where documents are stored.
        query
            Query to retrieve documents that match it.
        filter_query
            Dictionary containing filtering options.
        k
            Number of documents to return

        Returns
        -------
        res
            Documents retrieved.
        """
        if index_doc not in self.get_available_indexes():
            raise RuntimeError("Index for documents not in ES")
        if filter_query is not None:
            query_dict = {
                "bool": {"must": {"match": {"text": query}}, "filter": filter_query}
            }
        else:
            query_dict = {"bool": {"must": {"match": {"text": query}}}}

        res = self.client.search(
            index=index_doc,
            query=query_dict,
            size=k,
        )

        out = self._process_search_hits(res)
        return out


class AsyncElasticSearch(AsyncBaseSearch):
    """Class to use async Elasticsearch."""

    client: AsyncElasticsearch

    @model_validator(mode="before")
    def connect_to_ds(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Connect to ES."""
        values["use_ssl_and_verify_certs"] = values.get(
            "use_ssl_and_verify_certs", False
        )  # by default we don't use SSL
        if values.get("user") is None and values.get("password") is None:
            client = AsyncElasticsearch(
                f"{values['host']}:{values['port']}",
                verify_certs=values["use_ssl_and_verify_certs"],
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True,
            )
        else:
            client = AsyncElasticsearch(
                f"{values['host']}:{values['port']}",
                basic_auth=(values["user"], values["password"]),
                verify_certs=values["use_ssl_and_verify_certs"],
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True,
            )

        values["client"] = client
        return values

    async def get_available_indexes(self) -> list[str]:
        """Return all available indexes."""
        indices = await self.client.indices.get_alias()
        return list(indices.keys())

    async def remove_index(self, index: str) -> None:
        """Remove an index."""
        if index not in await self.get_available_indexes():
            raise RuntimeError("Index not in document store")
        await self.client.indices.delete(index=index)
        logger.info(f"Index {index} deleted successfully")

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
        if index not in await self.get_available_indexes():
            raise RuntimeError("Index not in the document store")
        if not await self.client.exists(index=index, id=doc_id):
            raise RuntimeError("Document not in the document store")
        doc = await self.client.get(index=index, id=doc_id)
        return doc["_source"]

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
        if index not in await self.get_available_indexes():
            raise RuntimeError("Index not in the document store")
        docs = await self.client.mget(index=index, ids=doc_ids)
        docs_to_return = [
            {"document_id": doc["_id"], **doc["_source"]}
            for doc in docs["docs"]
            if doc["found"]
        ]
        return docs_to_return

    @staticmethod
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
        out = []
        for hit in res["hits"]["hits"]:
            row = {}

            row["article_id"] = hit["_source"].get("article_id")
            row["title"] = hit["_source"].get("title")
            row["authors"] = hit["_source"].get("authors")
            row["doi"] = hit["_source"].get("doi")
            row["pubmed_id"] = hit["_source"].get("pubmed_id")
            row["pmc_id"] = hit["_source"].get("pmc_id")
            row["arxiv_id"] = hit["_source"].get("arxiv_id")
            row["section"] = hit["_source"].get("section")
            row["document_id"] = hit["_id"]
            row["date"] = hit["_source"].get("date")
            row["journal"] = hit["_source"].get("journal")
            row["paragraph_id"] = hit["_source"].get("paragraph_id")
            row["text"] = hit["_source"].get("text")
            row["article_type"] = hit["_source"].get("article_type")
            row["score"] = hit["_score"]

            out.append(row)

        return out

    async def get_index_mappings(self, index: str) -> dict[str, Any]:
        """Return an index mapping."""
        mapping = await self.client.indices.get_mapping(index=index)
        return mapping.raw[index]["mappings"]

    async def create_index(
        self,
        index: str,
        settings: dict[str, Any] | None,
        mappings: dict[str, Any] | None,
    ) -> None:
        """Create a new index."""
        if index in await self.get_available_indexes():
            raise RuntimeError("Index already in ES")
        await self.client.indices.create(
            index=index, settings=settings, mappings=mappings
        )
        logger.info(f"Index {index} created successfully")

    async def add_fields(
        self,
        index: str,
        settings: dict[str, Any] | None = None,
        mapping: dict[str, Any] | None = None,
    ) -> None:
        """Update the index with a new mapping and settings."""
        if index not in await self.get_available_indexes():
            raise RuntimeError("Index not in ES")

        if settings:
            await self.client.indices.put_settings(index=index, settings=settings)
        if mapping:
            await self.client.indices.put_mapping(index=index, properties=mapping)
        logger.info(f"Index {index} updated successfully.")

    async def count_documents(
        self, index: str, query: dict[str, Any] | None = None
    ) -> int:
        """Return the number of documents in an index.

        Parameters
        ----------
        index
            ES index where documents are stored.
        query
            Optional query to filter the documents to count.

        Returns
        -------
        document_count
            Number of documents in index that respect query.
        """
        if index not in await self.get_available_indexes():
            raise RuntimeError("Index not in ES")
        if query is None:
            query = {"match_all": {}}

        count = await self.client.count(index=index, query=query)

        return count["count"]

    async def exists(self, index: str, doc_id: str) -> bool:
        """Return True if this document exists in the index.

        Parameters
        ----------
        index
            ES index where documents are stored.
        doc_id
            ID under which the document might be indexed.

        Returns
        -------
            True if the document exists within an index.
        """
        return bool(await self.client.exists(index=index, id=doc_id))

    def iter_document(
        self, index: str, query: dict[str, Any] | None = None, size: int = 1000
    ) -> AsyncIterable[dict[str, Any]]:
        """Scan the documents matching a specific query."""
        if query is None:
            query = {"query": {"match_all": {}}}
        doc_gen = async_scan(self.client, index=index, query=query, size=size)
        return doc_gen

    async def add_document(
        self, index: str, doc: dict[str, Any], doc_id: str | None = None
    ) -> None:
        """Index a document.

        Parameters
        ----------
        index
            ES index where documents are stored.
        doc
            Document to index.
        doc_id
            ID under which the document must be indexed.
        """
        if index not in await self.get_available_indexes():
            raise RuntimeError("Index not in ES")
        if doc_id and await self.client.exists(index=index, id=doc_id):
            raise RuntimeError("Document already in ES")
        await self.client.index(index=index, id=doc_id, document=doc)
        logger.info(f"Document {doc_id} indexed successfully.")

    async def bulk(
        self,
        actions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        """Bulk upload of documents."""
        await async_bulk(client=self.client, actions=actions, **kwargs)
        logger.info("Successfully updated documents in bulk")

    async def search(
        self,
        index: str,
        query: dict[str, Any] | None = None,
        size: int = 10,
        aggs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Wrap around the search api."""
        if query is not None and "query" in query.keys():
            query = query["query"]
        query = postprocess_query(query)
        res = await self.client.search(
            index=index, query=query, size=size, aggs=aggs, **kwargs
        )
        return res.raw

    async def bm25_search(
        self,
        index_doc: str,
        query: str | dict[str, Any],
        filter_query: dict[str, Any] | None = None,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """BM25 search.

        Parameters
        ----------
        index_doc
            ES index where documents are stored.
        query
            Query to retrieve documents that match it.
        filter_query
            Dictionary of filtering criteria to add to the query.
        k
            Number of documents to return

        Returns
        -------
        res
            Documents retrieved.
        """
        if index_doc not in await self.get_available_indexes():
            raise RuntimeError("Index for documents not in ES")

        if filter_query is not None:
            query_dict = {
                "bool": {"must": {"match": {"text": query}}, "filter": filter_query}
            }
        else:
            query_dict = {"bool": {"must": {"match": {"text": query}}}}

        res = await self.client.search(
            index=index_doc,
            query=query_dict,
            size=k,
        )

        out = self._process_search_hits(res)
        return out

    async def close(self) -> None:
        """Close the aiohttp session."""
        await self.client.close()


def postprocess_query(query: dict[str, Any] | None) -> dict[str, Any] | None:
    """Post-process the query to handle special characters."""
    if query is None:
        return None

    if "query_string" in query.keys() and "query" in query["query_string"]:
        special_characters = {
            "+",
            "-",
            "=",
            "&&",
            "||",
            "!",
            "{",
            "}",
            "[",
            "]",
            "^",
            "~",
            "*",
            "?",
            ":",
            r"\"",
            "/",
            ">",
            "<",
        }
        intersection = set(query["query_string"]["query"]).intersection(
            special_characters
        )
        if len(intersection) > 0:
            query_str = query["query_string"]["query"]
            for character in intersection:
                if character in {">", "<"}:
                    query_str = query_str.replace(">", "")
                    query_str = query_str.replace("<", "")
                else:
                    query_str = query_str.replace(character, "\\" + character)
            query["query_string"]["query"] = query_str
            logger.info(f"Query had to be slightly modified to: {query}")
    return query
