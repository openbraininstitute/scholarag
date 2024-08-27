"""Impact factor retrieval."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any, Callable, Coroutine

import httpx

from scholarag.document_stores import AsyncBaseSearch

logger = logging.getLogger(__name__)


class MetaDataRetriever:
    """Class to send API calls async."""

    def __init__(
        self, tasks: list[asyncio.Task[Any]] | None = None, external_apis: bool = True
    ) -> None:
        if tasks is None:
            self.tasks = []
        else:
            self.tasks = tasks
        self.external_apis = external_apis

    def schedule_non_bulk_requests(
        self,
        coro: Callable[..., Coroutine[Any, Any, str | int | None]],
        data_list: list[str],
        **kwargs: Any,
    ) -> None:
        """Schedule multiple individual API calls."""
        # Remove duplicates before sending the requests.
        data_list = list(set(data_list))

        tasks = [asyncio.create_task(coro(data, **kwargs)) for data in data_list]
        self.tasks.append(
            asyncio.create_task(
                self.execute_sub_tasks(tasks, data_list), name=coro.__name__
            )
        )

    def schedule_bulk_request(
        self,
        coro: Callable[
            ...,
            Coroutine[
                Any, Any, list[str | None] | dict[str, Any] | list[dict[str, Any]]
            ],
        ],
        **kwargs: Any,
    ) -> None:
        """Schedule one API call that is compatible with bulk requests."""
        self.tasks.append(asyncio.create_task(coro(**kwargs), name=coro.__name__))

    @staticmethod
    async def execute_sub_tasks(
        tasks: list[asyncio.Task[Any]], data_list: list[str]
    ) -> dict[str, Any]:
        """Execute sub-tasks."""
        result = await asyncio.gather(*tasks)
        result_dict = dict(zip(data_list, result))
        return result_dict

    async def fetch(
        self,
    ) -> dict[str, Any]:
        """Run the API calls async."""
        task_names = [task.get_name() for task in self.tasks]
        results = await asyncio.gather(*self.tasks)
        return dict(zip(task_names, results))

    async def retrieve_metadata(
        self,
        contexts: list[dict[str, Any]],
        ds_client: AsyncBaseSearch,
        db_if_articles: str | None,
        db_index_paragraphs: str,
        httpx_client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        """Schedule the metadata retrieval and execute all of the tasks."""
        issns = [
            context["journal"] if "journal" in context else None for context in contexts
        ]
        dois = [context["doi"] for context in contexts if context["doi"] is not None]
        article_ids = [context["article_id"] for context in contexts]

        self.schedule_bulk_request(
            get_impact_factors,
            **{
                "ds_client": ds_client,
                "issns": issns,
                "db_index_impact_factor": db_if_articles,
            },
        )
        self.schedule_non_bulk_requests(
            recreate_abstract,
            article_ids,
            **{
                "ds_client": ds_client,
                "db_index_paragraphs": db_index_paragraphs,
            },
        )

        if self.external_apis:
            self.schedule_non_bulk_requests(
                get_citation_count, dois, **{"httpx_client": httpx_client}
            )
            self.schedule_non_bulk_requests(
                get_journal_name, issns, **{"httpx_client": httpx_client}
            )

        fetched_metadata = await self.fetch()
        return fetched_metadata


async def get_citation_count(
    doi: str | None, httpx_client: httpx.AsyncClient
) -> int | None:
    """Get the citation count for a given DOI.

    Parameters
    ----------
    doi : str | None
        The DOI of the paper.
    httpx_client : httpx.AsyncClient
        Async HTTPX Client.

    Returns
    -------
    int or None
        The number of citations for the paper if found, else None.
    """
    if doi is None:
        return None

    logger.info(f"Sending citation count request with doi {doi}.")
    ss_base_url = "https://api.semanticscholar.org/graph/v1/paper"
    ss_params = {"fields": "citationCount"}

    url = f"{ss_base_url}/{doi}"

    try:
        response = await httpx_client.get(url, params=ss_params)
        logger.debug(f"Obtained response for doi {doi}.")
        response.raise_for_status()
        citation_data = response.json()
        return citation_data.get("citationCount", None)

    except httpx.HTTPError as e:
        if hasattr(e, "detail") and hasattr(e.detail, "response"):
            logger.error(
                "Received non-success HTTP status code:"
                f" {e.detail.response.status_code}"
            )
            logger.error(f"Response content: {e.detail.response.text}")
        else:
            logger.info(f"HTTPError occurred, doi: {doi}")
        return None


async def get_impact_factors(
    ds_client: AsyncBaseSearch,
    issns: list[str],
    db_index_impact_factor: str | None,
) -> dict[str, float | None]:
    """Run impact factor search asynchronously.

    Parameters
    ----------
    ds_client
        Client to connect to Elasticsearch to get document data.
    issns
        Unique identifiers for journals.
    db_index_impact_factor
        Elasticsearch index for paragraphs

    Returns
    -------
    issn_to_citescore : dict[str, float | None]
        Dictionary containing the ISSN as keys and citescore as values.
    """
    logger.info("Running impact factor search")

    available_indexes = await ds_client.get_available_indexes()
    if (
        db_index_impact_factor is None
        or db_index_impact_factor not in available_indexes
    ):
        logger.warning(
            f"Skipping impact factor retrieval. The index {db_index_impact_factor} does"
            " not exist."
        )
        return {issn: None for issn in issns}

    filtered_issns = [issn[:4] + issn[5:] for issn in issns if issn is not None]
    query = {"query": {"terms": {"E-ISSN": filtered_issns}}}
    results = ds_client.iter_document(db_index_impact_factor, query)
    issn_to_citescore: dict[str, float | None] = {}

    for issn in issns:
        issn_to_citescore[issn] = None

    async for result in results:
        source = result["_source"]  # type: ignore
        issn = source["E-ISSN"][:4] + "-" + source["E-ISSN"][4:]
        issn_to_citescore[issn] = source["CiteScore"]
    logger.debug("Done retrieving impact factors.")
    return issn_to_citescore


async def get_journal_name(
    issn: str | None, httpx_client: httpx.AsyncClient
) -> str | None:
    """Fetch the journal name based on its issn."""
    if issn is None:
        return None
    logger.info(f"Fetching journal name based on issn: {issn}")
    url = f"https://portal.issn.org/resource/ISSN/{issn}"

    try:
        response = await httpx_client.get(url, follow_redirects=True)
        response.raise_for_status()
    except (httpx.ReadTimeout, httpx.PoolTimeout):
        logger.warning(f"Request to {url} timed out.")
        return None
    except ssl.SSLCertVerificationError:
        logger.error(f"SSL certificate issue with url {url}")
        return None
    except httpx.HTTPError:
        logger.warning(f"Request to {url} failed.")
        return None

    start = response.text.find('<script type="application/ld+json">')
    end = response.text.find("</script>", start)
    curated_text = (
        response.text[start:end]
        .replace('<script type="application/ld+json">', "")
        .replace("</script>", "")
    )
    try:
        response_dict = json.loads(curated_text)
    except json.decoder.JSONDecodeError:
        logger.warning("Could not load the API response as a JSON.")
        return None
    name = response_dict.get("name")
    logger.debug(f"Done retrieving journal name based on ISSN {issn}.")

    return name


async def recreate_abstract(
    article_id: str, ds_client: AsyncBaseSearch, db_index_paragraphs: str
) -> str | None:
    """Recreate the abstract from the article_id of the context."""
    logger.info(f"Reconstructing abstract of article {article_id}.")
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"article_id": article_id}},
                    {"term": {"section": "Abstract"}},
                ]
            }
        }
    }
    paragraphs = ds_client.iter_document(db_index_paragraphs, query)
    sorted_paragraphs = sorted(
        [paragraph["_source"] async for paragraph in paragraphs],  # type: ignore
        key=lambda x: x["paragraph_id"],
    )
    sorted_texts = [paragraph["text"] for paragraph in sorted_paragraphs]
    if len(sorted_texts) == 0:
        return None
    abstract = "".join(sorted_texts)
    logger.debug(f"Done reconstructing abstract of article {article_id}.")
    return abstract
