"""Utilities to stream openai response."""

import json
from collections import deque
from typing import Any, AsyncIterable

from httpx import AsyncClient
from openai import AsyncOpenAI, BadRequestError

from scholarag.app.config import Settings
from scholarag.app.dependencies import ErrorCode
from scholarag.document_stores import AsyncBaseSearch
from scholarag.generative_question_answering import (
    ERROR_SEPARATOR,
    SOURCES_SEPARATOR,
    GenerativeQAWithSources,
)
from scholarag.retrieve_metadata import MetaDataRetriever


async def stream_response(
    qas: GenerativeQAWithSources,
    query: str,
    contexts_text: list[str],
    ds_client: AsyncBaseSearch,
    index_journals: str | None,
    index_paragraphs: str,
    metadata_retriever: MetaDataRetriever,
    settings: Settings,
    contexts: list[dict[str, Any]],
    indices: tuple[int, ...],
    scores: tuple[float, ...] | None,
) -> AsyncIterable[str]:
    """Generate the stream for the `streamed_generative` endpoint.

    Parameters
    ----------
    qas
        Generative QA class to run the model's inference.
    query
        Question of the user.
    contexts_text
        list of texts to run the qa against.
    ds_client
        Document store client.
    index_journals
        DB index containing the impact factors.
    index_paragraphs
        DB index containing the paragraphs.
    metadata_retriever
        Class used to retreave metadata on the fly.
    settings
        Settings of the applications.
    contexts
        Contexts as extracted from the DB (with metadata).
    indices
        Order of the contexts after (potential) reranking.
    scores
        Reranking scores.

    Yields
    ------
    Generated tokens on the fly, + entire response in the end or error messages.
    """
    # Begin a task that runs in the background.
    interrupted = False

    # Needed because of fastAPI closing connections.
    httpx_client = AsyncClient(
        timeout=settings.metadata.timeout, verify=False
    )  # Using dependencies doesn't work here.
    password = settings.db.password.get_secret_value() if settings.db.password else None
    api_key = (
        settings.generative.openai.token.get_secret_value()
        if settings.generative.openai.token
        else None
    )
    ds_client = ds_client.__class__(
        host=settings.db.host,
        port=settings.db.port,
        user=settings.db.user,
        password=password,
    )
    openai_client = AsyncOpenAI(api_key=api_key)
    qas.client = openai_client

    token_queue: deque[str] = deque(
        maxlen=4
    )  # Needs to be EXACTLY the number of tokens of the separator. See https://platform.openai.com/tokenizer
    # Some black magic.
    raw_string = ""
    try:
        async for chunk in qas.astream(
            query=query,
            contexts=contexts_text,
            prompt_template=settings.generative.prompt_template.get_secret_value(),
        ):
            raw_string += chunk
            if len(token_queue) == token_queue.maxlen:
                queued_text = "".join(list(token_queue))
                if (
                    f"{SOURCES_SEPARATOR}:" in queued_text
                    or ERROR_SEPARATOR in queued_text
                ):  # Might change if we change the separator. # This condition is subject to change based on the separator we use.
                    continue
                yield token_queue.popleft()
            token_queue.append(chunk)
    except RuntimeError as e:
        # Since finish reason is raised, it has to be recovered as such.
        finish_reason = e.args[0]

    # Errors cannot be raised due to the streaming nature of the endpoint. They're yielded as a dict instead,
    # leaving the charge to the user to catch them. The stream is simply interrupted in case of error.
    except BadRequestError as err:
        interrupted = True
        # Adding a separator before raising the error
        yield "<bbs_json_error>"
        yield json.dumps(
            {
                "Error": {
                    "status_code": 413,
                    "code": ErrorCode.INPUT_EXCEEDED_MAX_TOKENS.value,
                    "detail": err.body["message"],  # type: ignore
                }
            }
        )
    if not interrupted:
        # Post process the output to get citations.
        answer = qas._process_raw_output(raw_output=raw_string)
        # Ensure that the model finished yielding.
        if finish_reason == "length":
            # Adding a separator before raising the error.
            yield "<bbs_json_error>"
            yield json.dumps(
                {
                    "Error": {
                        "status_code": 500,
                        "code": ErrorCode.INCOMPLETE_ANSWER.value,
                        "detail": (
                            "The LLM did not have enough completion tokens available to"
                            " finish its answer. Please decrease the reranker_k or"
                            " retriever_k value by 1 or 2 depending of whether you are"
                            " using the reranker or not."
                        ),
                        "raw_answer": answer["raw_answer"],
                    }
                }
            )
        elif answer["paragraphs"] is None or len(answer["paragraphs"]) == 0:  # type: ignore
            # Adding a separator before raising the error.
            yield "<bbs_json_error>"
            yield json.dumps(
                {
                    "Error": {
                        "status_code": 404,
                        "code": ErrorCode.NO_ANSWER_FOUND.value,
                        "detail": (
                            "The LLM did not provide any source to answer the question."
                        ),
                        "raw_answer": answer["raw_answer"],
                    }
                }
            )
        else:
            # Adding a separator between the streamed answer and the processed response.
            yield "<bbs_json_data>"
            complete_answer = await retrieve_metadata(
                answer=answer,
                ds_client=ds_client,
                index_journals=index_journals,
                index_paragraphs=index_paragraphs,
                metadata_retriever=metadata_retriever,
                httpx_client=httpx_client,
                contexts=contexts,
                indices=indices,
                scores=scores,
            )
            yield json.dumps(complete_answer)


async def retrieve_metadata(
    answer: dict[str, Any],
    ds_client: AsyncBaseSearch,
    index_journals: str | None,
    index_paragraphs: str,
    metadata_retriever: MetaDataRetriever,
    httpx_client: AsyncClient,
    contexts: list[dict[str, Any]],
    indices: tuple[int, ...],
    scores: tuple[float, ...] | None,
) -> dict[str, Any]:
    """Retrieve the metadata and display them nicely.

    Parameters
    ----------
    answer
        Answer generated by the model.
    ds_client
        Document store client.
    index_journals
        DB index containing the impact factors.
    index_paragraphs
        DB index containing the paragraphs.
    metadata_retriever
        Class used to retreave metadata on the fly.
    httpx_client
        HTTPX Client.
    contexts
        Contexts as extracted from the DB (with metadata).
    indices
        Order of the contexts after (potential) reranking.
    scores
        Reranking scores.

    Returns
    -------
    Nicely formatted answer with metadata.
    """
    fetched_metadata = await metadata_retriever.retrieve_metadata(
        contexts, ds_client, index_journals, index_paragraphs, httpx_client
    )

    citedby_counts = fetched_metadata.get("get_citation_count", {})
    journal_names = fetched_metadata.get("get_journal_name", {})
    impact_factors = fetched_metadata["get_impact_factors"]
    abstracts = fetched_metadata["recreate_abstract"]

    context_ids: list[int] = answer["paragraphs"]
    metadata = []
    for context_id in context_ids:
        context = contexts[context_id]

        metadata.append(
            {
                "impact_factor": impact_factors[context.get("journal")],
                "journal_name": journal_names.get(context.get("journal")),
                "journal_issn": context.get("journal"),
                "date": context.get("date"),
                "cited_by": citedby_counts.get(context.get("doi")),
                "article_id": context["article_id"],
                "ds_document_id": context["document_id"],
                "context_id": indices[context_id],
                "reranking_score": scores[context_id] if scores is not None else None,
                "article_doi": context["doi"],
                "article_title": context["title"],
                "article_authors": context["authors"],
                "article_type": context["article_type"],
                "section": context["section"],
                "paragraph": context["text"],
                "abstract": abstracts[context.get("article_id")],
                "pubmed_id": context["pubmed_id"],
            }
        )
        answer["metadata"] = metadata

    del answer["paragraphs"]
    return answer
