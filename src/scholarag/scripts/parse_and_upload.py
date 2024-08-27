"""Parse articles and upload them on Elastic Search."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pathlib
from typing import Any

from elasticsearch import ApiError
from elasticsearch.helpers import BulkIndexError as ESBulkIndexError
from opensearchpy.exceptions import TransportError
from opensearchpy.helpers import BulkIndexError as OSBulkIndexError

from scholarag.ds_utils import ds_upload, get_files, setup_parsing_ds

logger = logging.getLogger(__name__)


def get_parser() -> argparse.ArgumentParser:
    """Get parser for command line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "path",
        type=pathlib.Path,
        help="File or directory where are located the articles to parse.",
    )
    parser.add_argument(
        "parser_url",
        type=str,
        help="URL of the parser (needs to contain this address and the parser).",
    )
    parser.add_argument(
        "db_url",
        type=str,
        help="URL of the database instance (together with the port).",
    )
    parser.add_argument(
        "--articles-per-bulk",
        type=int,
        default=1000,
        help="Maximum number of articles to process before sending them to the db.",
    )
    parser.add_argument(
        "--max-paragraphs-length",
        "-u",
        type=int,
        help="Maximum length a paragraph is allowed to have to be uploaded to the DB.",
        default=None,
    )
    parser.add_argument(
        "--min-paragraphs-length",
        "-l",
        type=int,
        help="Minimum length a paragraph is allowed to have to be uploaded to the DB.",
        default=None,
    )
    parser.add_argument(
        "--multipart-params",
        default=None,
        type=json.loads,
        help=(
            "Dictionary for the multipart parameters for parsers that require some."
            " Must be passed as a json formated dict."
        ),
    )
    parser.add_argument(
        "--max-concurrent-requests",
        type=int,
        default=10,
        help=(
            "Maximum number of articles sent to the etl server PER BATCH OF"
            " 'articles-per-bulk' articles."
        ),
    )
    parser.add_argument(
        "--db-type",
        type=str,
        choices=["elasticsearch", "opensearch"],
        help="Type of database.",
        default="opensearch",
        required=False,
    )
    parser.add_argument(
        "--user",
        type=str,
        help=(
            "User of the database instance. The password is read from the environment"
            " under SCHOLARAG__DB__PASSWORD."
        ),
        required=False,
    )
    parser.add_argument(
        "--index",
        type=str,
        default="paragraphs",
        help="Desired name of the index holding paragraphs.",
    )
    parser.add_argument(
        "--files-failing-path",
        type=pathlib.Path,
        default=None,
        help="Path where to dump the files that failed. Expects a file.",
    )
    parser.add_argument(
        "-m",
        "--match-filename",
        type=str,
        help="""
        Parse only files with a name matching the given regular expression.
        Ignored when 'input_path' is a path to a file.
        """,
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="""
        Parse files recursively.
        """,
    )
    parser.add_argument(
        "--use-ssl",
        action="store_true",
        help="Whether to verify ssl certificates or not.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Control verbosity",
    )
    return parser


async def run(
    path: pathlib.Path,
    recursive: bool,
    match_filename: str | None,
    db_url: str,
    parser_url: str,
    multipart_params: dict[str, Any] | None,
    max_concurrent_requests: int = 10,
    articles_per_bulk: int = 1000,
    min_paragraphs_length: int | None = None,
    max_paragraphs_length: int | None = None,
    db_type: str = "opensearch",
    index: str = "paragraphs",
    user: str | None = None,
    password: str | None = None,
    files_failing_path: pathlib.Path | None = None,
    use_ssl: bool = False,
) -> int:
    """Run the article parsing and upload results on ES."""
    ds_client, parsing_service = await setup_parsing_ds(
        db_url,
        db_type,
        user,
        password,
        max_concurrent_requests,
        use_ssl,
    )
    batches = get_files(
        path,
        recursive,
        match_filename=match_filename,
        articles_per_bulk=articles_per_bulk,
    )
    for i, batch in enumerate(batches):
        logger.info(f"Request server to parse batch {i}.")
        results = await parsing_service.arun(
            files=batch,
            url=parser_url,
            multipart_params=multipart_params,
        )
        logger.info("Collecting data to upload to the document store.")
        indices = [index for _ in range(len(batch))]
        try:
            files_failing = await ds_upload(
                filenames=batch,
                results=results,
                ds_client=ds_client,
                min_paragraphs_length=min_paragraphs_length,
                max_paragraphs_length=max_paragraphs_length,
                indices=indices,
            )
        except (ApiError, ESBulkIndexError, TransportError, OSBulkIndexError):
            files_failing = batch

    if files_failing and files_failing_path is not None:
        logger.info(f"Dumping failing files to {files_failing_path.resolve()}")
        with open(files_failing_path, "a") as f:
            for files in files_failing:
                f.write(json.dumps(files))
                f.write("\n")
    await ds_client.close()
    logger.info("Done.")

    return 0


def main() -> None:
    """Run the main logic."""
    # Parse command line
    parser = get_parser()
    args = parser.parse_args()

    # Additional parameters
    logging_level = logging.INFO if args.verbose else logging.WARNING

    # setup logging
    logging.basicConfig(
        format="[%(levelname)s]  %(asctime)s %(name)s  %(message)s", level=logging_level
    )
    password = os.getenv("SCHOLARAG__DB__PASSWORD")

    # Run the main function
    raise SystemExit(
        asyncio.run(
            run(
                path=args.path,
                recursive=args.recursive,
                match_filename=args.match_filename,
                db_url=args.db_url,
                db_type=args.db_type,
                parser_url=args.parser_url,
                multipart_params=args.multipart_params,
                max_concurrent_requests=args.max_concurrent_requests,
                articles_per_bulk=args.articles_per_bulk,
                min_paragraphs_length=args.min_paragraphs_length,
                max_paragraphs_length=args.max_paragraphs_length,
                index=args.index,
                user=args.user,
                password=password,
                files_failing_path=args.files_failing_path,
                use_ssl=args.use_ssl,
            )
        )
    )


if __name__ == "__main__":
    main()
