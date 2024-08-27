"""Parse articles and upload them on the document store."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pathlib
import time
from datetime import datetime, timedelta
from typing import Any

from aiobotocore.session import get_session
from botocore import UNSIGNED
from botocore.config import Config
from elasticsearch import ApiError
from elasticsearch.helpers import BulkIndexError as ESBulkIndexError
from httpx import AsyncClient
from opensearchpy.exceptions import TransportError
from opensearchpy.helpers import BulkIndexError as OSBulkIndexError

from scholarag.ds_utils import check_docs_exists_in_db, ds_upload, setup_parsing_ds

logger = logging.getLogger(__name__)


def get_parser() -> argparse.ArgumentParser:
    """Get parser for command line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "db_url",
        type=str,
        help="URL of the database instance (together with the port).",
    )
    parser.add_argument(
        "parser_url",
        type=str,
        help="URL of the parser (needs to contain the host:port and the parser type).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help=(
            "Date of the oldest document to download. Defaults to yesterday. Format:"
            " dd-mm-yyy."
        ),
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
        "--batch-size",
        type=int,
        default=500,
        help="Maximum number of articles to process before sending them to the db.",
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
        default=None,
        help=(
            "User of the database instance. The password is read from the environment"
            " under SCHOLARAG__DB__PASSWORD."
        ),
        required=False,
    )
    parser.add_argument(
        "--index",
        type=str,
        default="pmc_paragraphs",
        help="Desired name of the index holding paragraphs.",
    )
    parser.add_argument(
        "--files-failing-path",
        type=pathlib.Path,
        default=None,
        help=(
            "Path where to dump the files that failed. Expects a file. Not dumping if"
            " None."
        ),
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
    db_url: str,
    parsing_url: str,
    start_date: datetime,
    db_type: str,
    multipart_params: dict[str, Any] | None = None,
    max_concurrent_requests: int = 10,
    index: str = "pmc_paragraphs",
    batch_size: int = 500,
    min_paragraphs_length: int | None = None,
    max_paragraphs_length: int | None = None,
    user: str | None = None,
    use_ssl: bool = False,
    files_failing_path: pathlib.Path | None = None,
) -> int:
    """Run the article parsing and upload results on DS."""
    password = os.getenv("SCHOLARAG__DB__PASSWORD")
    if not password:
        logger.warning("SCHOLARAG__DB__PASSWORD variable not set. defaulting to None.")
    ds_client, parsing_service = await setup_parsing_ds(
        db_url,
        db_type,
        user,
        password,
        max_concurrent_requests,
        use_ssl,
    )
    # Setup s3 bucket
    logger.info("Starting S3 client.")
    session = get_session()
    start_time = time.time()
    async with (
        session.create_client(
            "s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED)
        ) as client,
        AsyncClient() as httpx_client,
    ):
        for prefix in [
            "oa_comm/xml/all/",
            "oa_noncomm/xml/all/",
            "author_manuscript/xml/all/",
        ]:
            s3_paginator = client.get_paginator("list_objects_v2")
            s3_iterator = s3_paginator.paginate(Bucket="pmc-oa-opendata", Prefix=prefix)
            logger.info("Filtering interesting articles.")
            filtered_iterator = s3_iterator.search(
                f"""Contents[?to_string(LastModified)>='\"{start_date.strftime('%Y-%m-%d %H:%M:%S%')}+00:00\"'
                    && contains(Key, '.xml')]"""
            )
            finished = False
            while not finished:
                start_time_batch = time.time()

                s3_bucket_dict = {}
                i = 0
                # Creating batches.
                async for obj in filtered_iterator:
                    i += 1
                    s3_bucket_key = pathlib.Path(obj["Key"])
                    s3_bucket_dict[s3_bucket_key.stem] = s3_bucket_key
                    if i == batch_size:
                        break

                if i != batch_size:
                    finished = True

                all_pmc_ids = list(s3_bucket_dict.keys())
                if not all_pmc_ids:
                    continue
                existing_files = await check_docs_exists_in_db(
                    ds_client, index, all_pmc_ids
                )

                s3_bucket_keys = [
                    v for k, v in s3_bucket_dict.items() if k not in existing_files
                ]

                logger.info("Get objects.")
                files = []
                for s3_bucket_key in s3_bucket_keys:
                    response = await client.get_object(
                        Bucket="pmc-oa-opendata", Key=str(s3_bucket_key)
                    )
                    body = await response["Body"].read()
                    files.append(body)

                logger.info(f"Request server to parse {len(s3_bucket_keys)} documents.")
                results = await parsing_service.arun(
                    url=parsing_url,
                    files=files,
                    multipart_params=multipart_params,
                    httpx_client=httpx_client,
                )
                logger.info("Collecting data to upload to the document store.")
                indices = [index for _ in range(len(s3_bucket_keys))]
                try:
                    files_failing = await ds_upload(
                        filenames=s3_bucket_keys,
                        results=results,
                        ds_client=ds_client,
                        min_paragraphs_length=min_paragraphs_length,
                        max_paragraphs_length=max_paragraphs_length,
                        indices=indices,
                    )
                except (ApiError, ESBulkIndexError, TransportError, OSBulkIndexError):
                    files_failing = s3_bucket_keys

                if files_failing and files_failing_path is not None:
                    logger.info(
                        f"Dumping failing files to {files_failing_path.resolve()}"
                    )
                    with open(files_failing_path, "a") as f:
                        for file in files_failing:
                            f.write(json.dumps(file))
                            f.write("\n")
                    logger.info(
                        f"From start took: {time.time() - start_time}. Batch took:"
                        f" {time.time() - start_time_batch}"
                    )

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
    if args.start_date is not None:
        start_date = datetime.strptime(args.start_date, "%d-%m-%Y")
        if start_date > datetime.today():
            raise ValueError(
                "Date is in the future! Hope you found the secret for time travelling."
            )
    else:
        start_date = datetime.today() - timedelta(days=1)
    raise SystemExit(
        asyncio.run(
            run(
                db_url=args.db_url,
                parsing_url=args.parser_url,
                start_date=start_date,
                db_type=args.db_type,
                user=args.user,
                index=args.index,
                min_paragraphs_length=args.min_paragraphs_length,
                max_paragraphs_length=args.max_paragraphs_length,
                multipart_params=args.multipart_params,
                max_concurrent_requests=args.max_concurrent_requests,
                use_ssl=args.use_ssl,
                batch_size=args.batch_size,
                files_failing_path=args.files_failing_path,
            )
        )
    )


if __name__ == "__main__":
    main()
