"""Script to create, delete or reset an index in a document store."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any

from scholarag.document_stores import BaseSearch, ElasticSearch, OpenSearch
from scholarag.document_stores.elastic import (
    MAPPINGS_PARAGRAPHS as ELASTICSEARCH_MAPPINGS_PARAGRAPHS,
)
from scholarag.document_stores.elastic import SETTINGS as ELASTICSEARCH_SETTINGS
from scholarag.document_stores.open import (
    MAPPINGS_PARAGRAPHS as OPENSEARCH_MAPPINGS_PARAGRAPHS,
)
from scholarag.document_stores.open import SETTINGS as OPENSEARCH_SETTINGS

logger = logging.getLogger("create_index")
logging.getLogger("elastic_transport").setLevel(logging.WARNING)


def get_parser() -> argparse.ArgumentParser:
    """Get parser for command line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "task",
        type=str,
        default="create",
        choices=["create", "delete", "reset"],
        help="Specify the action to take. Reset = delete -> create.",
    )
    parser.add_argument(
        "index",
        type=str,
        help="Name of the index to deal with.",
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
        "--n-shards", default=2, type=int, help="Number of shards for the index."
    )
    parser.add_argument(
        "--n-replicas", default=1, type=int, help="Number of replicas for the index."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Control verbosity",
    )
    return parser


def manage_index(
    task: str,
    document_store: BaseSearch,
    index: str,
    mappings: dict[str, Any] | None = None,
    settings: dict[str, str] | None = None,
) -> None:
    """Run the logic."""
    if task in ["delete", "reset"]:
        document_store.remove_index(index)
        logger.info(f"Successfully removed index {index}")
    if task in ["create", "reset"] and mappings is not None and settings is not None:
        document_store.create_index(index, settings, mappings)
        logger.info(f"Successfully created index {index}")


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
        mappings = ELASTICSEARCH_MAPPINGS_PARAGRAPHS
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
        mappings = OPENSEARCH_MAPPINGS_PARAGRAPHS
        settings = OPENSEARCH_SETTINGS
    else:
        raise ValueError(
            "The db type should be either 'elasticsearch' or 'opensearch'."
        )

    settings["number_of_shards"] = args.n_shards
    settings["number_of_replicas"] = args.n_replicas

    manage_index(
        task=args.task,
        document_store=document_store,
        index=args.index,
        mappings=mappings,
        settings=settings,
    )

    raise SystemExit(0)


if __name__ == "__main__":
    main()
