"""Document Store utilities."""

from __future__ import annotations

import hashlib
import logging
import math
import pathlib
from typing import Any

from elasticsearch import ApiError
from elasticsearch.helpers import BulkIndexError as ESBulkIndexError
from opensearchpy.exceptions import TransportError
from opensearchpy.helpers import BulkIndexError as OSBulkIndexError

from scholarag.document_stores import (
    AsyncBaseSearch,
    AsyncElasticSearch,
    AsyncOpenSearch,
)
from scholarag.services import ParsingService
from scholarag.utils import find_files

logger = logging.getLogger("ds_utils")
logger_os = logging.getLogger("opensearch")
logger_es = logging.getLogger("elasticsearch")


class NoParsingFilter(logging.Filter):
    """Class to filter logs coming from ds_client.exists()."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        """Filter logs coming from ds_client.exists()."""
        return not record.getMessage().startswith("GET")


logger_os.addFilter(NoParsingFilter())
logger_es.addFilter(NoParsingFilter())


async def check_docs_exists_in_db(
    client: AsyncBaseSearch, index: str, pmc_ids: list[str]
) -> list[str]:
    """Return list of index of documents .

    Parameters
    ----------
    client
        Async Opensearch client.
    index
        OS index where documents are stored.
    pmc_ids
        PMC IDs of the documents.

    Returns
    -------
        True if the document exists within an index.
    """
    query = {"query": {"terms": {"pmc_id": pmc_ids}}}
    aggs = {"matched_ids": {"terms": {"field": "pmc_id", "size": len(pmc_ids)}}}
    docs = await client.search(index=index, query=query, aggs=aggs, size=0)
    existing_ids = [
        doc["key"] for doc in docs["aggregations"]["matched_ids"]["buckets"]
    ]
    return existing_ids


async def setup_parsing_ds(
    db_url: str,
    db_type: str = "opensearch",
    user: str | None = None,
    password: str | None = None,
    max_concurrent_requests: int = 10,
    use_ssl: bool = False,
) -> tuple[AsyncBaseSearch, ParsingService]:
    """Create the ds client and parsing service.

    Parameters
    ----------
    db_url
        Url of the DB
    db_type
        Opensearch or Elasticsearch
    user
        Username to connect to the DB
    password
        Password to connect to the DB
    max_concurrent_requests
        Max number of requests to send simultaneously to the parser
    use_ssl
        Whether certificates should be verified or not

    Returns
    -------
    ds_client, parsing_service
    """
    # Setup document store.
    host, _, port = db_url.rpartition(":")
    ds_client = (
        AsyncOpenSearch(  # type:ignore
            host=host,
            port=int(port),
            user=user,
            password=password,
            use_ssl_and_verify_certs=use_ssl,
        )
        if db_type == "opensearch"
        else AsyncElasticSearch(  # type: ignore
            host=host,
            port=int(port),
            user=user,
            password=password,
            use_ssl_and_verify_certs=use_ssl,
        )
    )

    # Setup parsing service
    parsing_service = ParsingService(
        ignore_errors=True,
        max_concurrent_requests=max_concurrent_requests,
    )
    return ds_client, parsing_service


def get_files(
    path: pathlib.Path,
    recursive: bool,
    articles_per_bulk: int,
    match_filename: str | None = None,
) -> list[list[pathlib.Path]]:
    """Fetch local files to parser and upload."""
    # Check the path and iterate to have a list of papers to parse
    if not path.exists():
        raise ValueError(f"The path {path} does not exist.")

    if path.is_dir():
        inputs = find_files(path, recursive, match_filename)
    else:
        inputs = [
            path,
        ]

    logger.info(
        f"There are {len(inputs)} files to parse, split in"
        f" {math.ceil(len(inputs) / articles_per_bulk)} batches."
    )
    batches = [
        inputs[i : i + articles_per_bulk]
        for i in range(0, len(inputs), articles_per_bulk)
    ]
    return batches


async def ds_upload(
    filenames: list[pathlib.Path],
    results: list[dict[str, Any] | None],
    indices: list[str],
    ds_client: AsyncBaseSearch,
    min_paragraphs_length: int | None = None,
    max_paragraphs_length: int | None = None,
) -> list[pathlib.Path]:
    """Upload results to document store.

    Parameters
    ----------
    filenames
        List of files from which the content is uploaded
    results
        Output of the parser
    indices
        List of index to which each document belong to.
    ds_client
        Document store client
    min_paragraphs_length
        Minimum length a paragraph is allowed to have to be uploaded to the DB.
    max_paragraphs_length
        Maximum length a paragraph is allowed to have to be uploaded to the DB.

    Returns
    -------
    List of files that failed to be pushed.
    """
    upload_bulk = []
    files_failing: list[pathlib.Path] = []
    doc_ids: set[str] = set()
    for k, (res, index) in enumerate(zip(results, indices)):
        if res is None:
            logging.error(f"File {filenames[k]} failed to be parsed.")
            files_failing.append(filenames[k])
            continue
        try:
            for i, abstract in enumerate(res["abstract"]):
                doc_id = hashlib.md5(
                    (res["uid"] + abstract).encode("utf-8"),
                    usedforsecurity=False,
                ).hexdigest()
                # Check length (not expensive) before doing a db call to check existence.
                if (
                    min_paragraphs_length and len(abstract) <= min_paragraphs_length
                ) or (max_paragraphs_length and len(abstract) >= max_paragraphs_length):
                    continue
                # if length is ok, check if it already exists somewhere.
                if doc_id in doc_ids or await ds_client.exists(index, doc_id):
                    continue
                else:
                    doc_ids.add(doc_id)

                par = {
                    "_index": index,
                    "_id": doc_id,
                    "_source": {
                        "article_id": res["uid"],
                        "section": "Abstract",
                        "text": abstract,
                        "paragraph_id": i,
                        "authors": res["authors"],
                        "title": res["title"],
                        "pubmed_id": res["pubmed_id"],
                        "pmc_id": res["pmc_id"],
                        "arxiv_id": res["arxiv_id"],
                        "doi": res["doi"],
                        "date": res["date"],
                        "journal": res["journal"],
                        "article_type": res["article_type"],
                    },
                }
                if len(par) > 0:
                    upload_bulk.append(par)

            for ppos, (section, text) in enumerate(res["section_paragraphs"]):
                doc_id = hashlib.md5(
                    (res["uid"] + text).encode("utf-8"), usedforsecurity=False
                ).hexdigest()
                # Check length (not expensive) before doing a db call to check existence.
                if (min_paragraphs_length and len(text) <= min_paragraphs_length) or (
                    max_paragraphs_length and len(text) >= max_paragraphs_length
                ):
                    continue
                # if length is ok, check if it already exists.
                if doc_id in doc_ids or await ds_client.exists(index, doc_id):
                    continue
                else:
                    doc_ids.add(doc_id)

                par = {
                    "_index": index,
                    "_id": doc_id,
                    "_source": {
                        "article_id": res["uid"],
                        "section": section,
                        "text": text,
                        "paragraph_id": ppos + len(res["abstract"]),
                        "authors": res["authors"],
                        "title": res["title"],
                        "pubmed_id": res["pubmed_id"],
                        "pmc_id": res["pmc_id"],
                        "arxiv_id": res["arxiv_id"],
                        "doi": res["doi"],
                        "date": res["date"],
                        "journal": res["journal"],
                        "article_type": res["article_type"],
                    },
                }
                if len(par) > 0:
                    upload_bulk.append(par)
        except TypeError as e:
            logger.error(f"Article {filenames[k]} could not be parsed properly. {e}")
            files_failing.append(filenames[k])
            continue

    logger.info("Upload data to database.")
    try:
        await ds_client.bulk(upload_bulk)
    except (ApiError, ESBulkIndexError, TransportError, OSBulkIndexError) as e:
        logger.info(f"Results could not be uploaded properly. {e}")
        logger.info(f"List of files that failed: {filenames}")
        raise e

    return files_failing
