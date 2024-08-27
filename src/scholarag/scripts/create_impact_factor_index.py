"""Script to create impact factor index."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

import opensearchpy.exceptions
import pandas as pd

from scholarag.document_stores import BaseSearch, ElasticSearch, OpenSearch
from scholarag.document_stores.elastic import SETTINGS as ELASTICSEARCH_SETTINGS
from scholarag.document_stores.open import SETTINGS as OPENSEARCH_SETTINGS

logger = logging.getLogger("create_impact_factor_index")
logging.getLogger("elastic_transport").setLevel(logging.WARNING)
logging.getLogger("opensearch").setLevel(logging.WARNING)

IMPACT_FACTORS_MAPPING = {
    "dynamic": "strict",
    "properties": {
        "Citation Count": {"type": "integer"},
        "CiteScore": {"type": "float"},
        "E-ISSN": {"type": "keyword"},
        "Main Publisher": {"type": "keyword"},
        "Open Access": {"type": "keyword"},
        "Percent Cited": {"type": "float"},
        "Percentile": {"type": "integer"},
        "Print ISSN": {"type": "keyword"},
        "Publisher": {"type": "keyword"},
        "Quartile": {"type": "integer"},
        "RANK": {"type": "integer"},
        "Rank Out Of": {"type": "text"},
        "SJR": {"type": "float"},
        "SNIP": {"type": "float"},
        "Scholarly Output": {"type": "integer"},
        "Scopus ASJC Code (Sub-subject Area)": {"type": "integer"},
        "Scopus Source ID": {"type": "keyword"},
        "Scopus Sub-Subject Area": {"type": "text"},
        "Title": {"type": "text"},
        "Top 10% (CiteScore Percentile)": {"type": "keyword"},
        "Type": {"type": "keyword"},
        "URL Scopus Source ID": {"type": "text"},
    },
}


def get_parser() -> argparse.ArgumentParser:
    """Get parser for command line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "from_file",
        type=Path,
        help="Path to file containing impact factor information.",
    )
    parser.add_argument(
        "index",
        type=str,
        help="Name of the index to create.",
    )
    parser.add_argument(
        "db_url",
        type=str,
        help="URL of the database instance. Format: HOST:PORT",
    )
    parser.add_argument(
        "--db-type",
        type=str,
        choices=["elasticsearch", "opensearch"],
        default="opensearch",
        help="Type of database.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help=(
            "User of the database instance. The password is read from the environment"
            " under SCHOLARAG__DB__PASSWORD."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Control verbosity",
    )
    return parser


def run(
    document_store: BaseSearch,
    from_file: Path,
    index: str,
    settings: dict[str, Any] | None = None,
) -> None:
    """Create and populate the impact factors index from a file.

    Parameters
    ----------
    document_store
        Document store to populate with the new impact factors index.
    from_file
        File containing the data to populate the index.
    index
        Name of the index to create in the document store.
    settings
        Settings to use when creating the index.
    """
    if not from_file.exists():
        raise ValueError(f"The file {from_file} does not exist.")

    if index in document_store.get_available_indexes():
        raise ValueError(f"The index {index} already exists.")

    document_store.create_index(
        index,
        mappings=IMPACT_FACTORS_MAPPING,
        settings=settings,
    )

    document_store.client.indices.refresh()  # type: ignore

    df = pd.read_excel(from_file)
    # Clean the DataFrame, remove rows with no E-ISSN, fill NaN for others
    df = df[df["E-ISSN"].notna()]
    df = df.fillna(
        {
            "SNIP": 0,
            "SJR": 0,
            "Publisher": "",
            "Main Publisher": "",
            "Print ISSN": "",
        },
    )

    data = df.to_dict("records")
    successful, failed = [], []
    for d in data:
        # Searching the impact factors through the E-ISSN in the app, so making it the ID
        if document_store.exists(index, str(d["E-ISSN"])):
            continue
        logger.debug(f"Uploading {d['E-ISSN']}")
        try:
            document_store.add_document(
                index=index,
                doc=d,
                doc_id=str(d["E-ISSN"]),
            )
            successful.append(d["E-ISSN"])
        except (opensearchpy.exceptions.RequestError, RuntimeError):
            logger.warning(f"Failed to upload {d['E-ISSN']}")
            failed.append(d["E-ISSN"])

    logger.debug(
        f"{len(successful)} docs were successfully uploaded, {len(failed)} failed."
    )


def main() -> int:
    """Run the main logic."""
    parser = get_parser()
    args = parser.parse_args()

    logging_level = logging.INFO if args.verbose else logging.WARNING

    # setup logging
    logging.basicConfig(
        format="[%(levelname)s]  %(asctime)s %(name)s  %(message)s", level=logging_level
    )

    host, _, port = args.db_url.rpartition(":")
    password = os.getenv("SCHOLARAG__DB__PASSWORD")
    if not password:
        logger.warning("SCHOLARAG__DB__PASSWORD variable not set. defaulting to None.")

    if args.db_type == "elasticsearch":
        document_store = (
            ElasticSearch(
                host=host,
                port=port,
                user=args.user,
                password=password,
                use_ssl_and_verify_certs=False,
            )  # type: ignore
            if args.user is not None
            else ElasticSearch(host=host, port=port, use_ssl_and_verify_certs=False)  # type: ignore
        )
        settings = ELASTICSEARCH_SETTINGS

    elif args.db_type == "opensearch":
        # Opensearch doesn't accept the http protocol at the beginning of the host.
        # While we could rely on the user to not provide it, any new user of our code
        # would get highly confused. So I handle it here.
        document_store = (
            OpenSearch(
                host=host,
                port=port,
                user=args.user,
                password=password,
                use_ssl_and_verify_certs=False,  # type: ignore
            )
            if args.user is not None
            else OpenSearch(host=host, port=port, use_ssl_and_verify_certs=False)  # type: ignore
        )
        settings = OPENSEARCH_SETTINGS
    else:
        raise ValueError(
            "The db type should be either 'elasticsearch' or 'opensearch'."
        )

    run(
        document_store=document_store,
        from_file=args.from_file,
        index=args.index,
        settings=settings,
    )

    return 0


if __name__ == "__main__":
    main()
