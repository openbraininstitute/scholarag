"""Endpoints response and request schemas."""

from pydantic import BaseModel, Field


class JournalSuggestionRequest(BaseModel):
    """Request for the journal suggestion endpoint."""

    keywords: str
    limit: int = Field(100, ge=1, le=10000)


class JournalSuggestionResponse(BaseModel):
    """Class representing Journal metadata."""

    title: str
    citescore: float | None
    eissn: str | None
    snip: float | None
    sjr: float | None
    print_issn: str | None


class ArticleTypeSuggestionResponse(BaseModel):
    """Class representing article types in the db."""

    article_type: str
    docs_in_db: int


class AuthorSuggestionResponse(BaseModel):
    """Class representing authors."""

    name: str


class AuthorSuggestionRequest(BaseModel):
    """Request for the author suggestion endpoint."""

    name: str
    limit: int = Field(100, ge=1, le=1000)


class PassthroughRequest(BaseModel):
    """Request to the passthrough endpoint."""

    query: str


class RetrievalRequest(PassthroughRequest, extra="forbid"):
    """Request for the raw retrieval endpoint."""

    retriever_k: int = Field(700, ge=1, le=2000)
    use_reranker: bool = True
    reranker_k: int = Field(8, ge=1, le=100)


class GenerativeQARequest(RetrievalRequest, extra="forbid"):
    """Request for the QA endpoint."""


class ArticleCountResponse(BaseModel, extra="forbid"):
    """Response of the article_count endpoint."""

    article_count: int


class ArticleMetadata(BaseModel, extra="ignore"):
    """Metadata for an article."""

    article_title: str
    article_authors: list[str]
    article_id: str

    # Possibly missing
    article_doi: str | None = None
    pubmed_id: str | None = None
    date: str | None = None
    article_type: str | None = None
    journal_issn: str | None = None

    # Added dynamically
    journal_name: str | None = None
    cited_by: int | None = None
    impact_factor: float | None = None
    abstract: str | None = None


class DocumentMetadata(ArticleMetadata, extra="ignore"):
    """Metadata for a document retrieved directly from the db."""

    paragraph: str
    ds_document_id: str

    # Possibly missing
    section: str | None = None


class ParagraphMetadata(DocumentMetadata, extra="ignore"):
    """Metadata for a paragraphs retrieved through the retrieval service."""

    context_id: int  # Position of the context after retrieval (from db).

    # Possibly missing
    reranking_score: float | None = None


class PassthroughResponse(BaseModel):
    """Response for the passthrough endpoint."""

    answer: str


class GenerativeQAResponse(BaseModel):
    """Response for the generative QA endpoint."""

    answer: str | None
    raw_answer: str
    metadata: list[ParagraphMetadata]
