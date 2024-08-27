"""Document store classes for Scholarag."""

from scholarag.document_stores.base import AsyncBaseSearch, BaseSearch
from scholarag.document_stores.elastic import AsyncElasticSearch, ElasticSearch
from scholarag.document_stores.open import AsyncOpenSearch, OpenSearch

__all__ = [
    "BaseSearch",
    "AsyncBaseSearch",
    "ElasticSearch",
    "AsyncElasticSearch",
    "OpenSearch",
    "AsyncOpenSearch",
]
