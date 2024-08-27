"""Consumer for parse and upload."""

import argparse
import asyncio
import logging
import os
import pathlib
import time
from multiprocessing import Process, cpu_count
from typing import Any

from aiobotocore.session import get_session
from botocore import UNSIGNED
from botocore.config import Config
from elasticsearch import ApiError
from elasticsearch.helpers import BulkIndexError as ESBulkIndexError
from httpx import AsyncClient
from opensearchpy.exceptions import TransportError
from opensearchpy.helpers import BulkIndexError as OSBulkIndexError

from scholarag.ds_utils import ds_upload, setup_parsing_ds

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
        help="URL of the parser (needs to contain the host:port).",
    )
    parser.add_argument(
        "queue_url",
        type=str,
        help="Url of the queue where to upload the articles.",
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=500,
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
    worker_n: int,
    db_url: str,
    parser_url: str,
    queue_url: str,
    db_type: str,
    max_concurrent_requests: int = 10,
    min_paragraphs_length: int | None = None,
    max_paragraphs_length: int | None = None,
    batch_size: int = 500,
    user: str | None = None,
    use_ssl: bool = False,
) -> None:
    """Run the consumer script.

    Parameters
    ----------
    worker_n
        Number of workers.
    db_url
        URL of the db to which the documents should be sent
    parser_url
        Base url of the parser (without the endpoint).
    queue_url
        URL of the queue that holds the articles.
    db_type
        Either elasticsearch of opensearch.
    max_concurrent_requests
        Maximum number of concurrent requests sent to the etl service.
    min_paragraphs_length
        Minimum length a paragraph is allowed to have to be uploaded to the DB.
    max_paragraphs_length
        Maximum length a paragraph is allowed to have to be uploaded to the DB.
    batch_size
        Number of articles to retrieve from the queue at every iteration.
    user
        Username to authenticate in the DB.
    use_ssl
        Whether to verify ssl certificate or not.
    """
    try:
        password = os.getenv("SCHOLARAG__DB__PASSWORD")
        if not password:
            logger.warning(
                f"[WORKER {worker_n}] SCHOLARAG__DB__PASSWORD variable not set."
                " defaulting to None."
            )
        # Setup parser and db.
        ds_client, parser_service = await setup_parsing_ds(
            db_url,
            db_type,
            user,
            password,
            max_concurrent_requests,
            use_ssl,
        )
        session = get_session()
        httpx_client = AsyncClient(timeout=60)
        tested_indices: set[str] = set()

        async with (
            session.create_client(
                "s3",
                region_name="us-east-1",
            ) as signed_s3_client,
            session.create_client("sqs", region_name="us-east-1") as q_client,
            session.create_client(
                "s3",
                region_name="us-east-1",
                config=Config(signature_version=UNSIGNED),
            ) as unsigned_s3_client,
            httpx_client as httpx_client,
        ):
            # Iterate while the queue is not empty.
            while True:
                start_time_batch = time.time()
                batch: list[dict[str, Any]] = []

                # Retrieve a batch from the queue.
                logger.info(f"[WORKER {worker_n}] Polling the queue...")
                attempt = 0
                while (d_batch := batch_size - len(batch)) > 0:
                    messages = await q_client.receive_message(
                        QueueUrl=queue_url,
                        WaitTimeSeconds=2,
                        MaxNumberOfMessages=10 if d_batch > 10 else d_batch,
                        MessageAttributeNames=[
                            "Key",
                            "Bucket_Name",
                            "Parser_Endpoint",
                            "Sign",
                            "Index",
                        ],
                    )
                    if "Messages" not in messages:
                        # If there is nothing in the queue left, retry.
                        attempt += 1
                        # If there was not enough in the queue to fill a batch, run with partial batch if it is not empty.
                        if attempt >= 10 and batch:
                            logger.info(
                                f"[WORKER {worker_n}] Managed to retrieve a partial"
                                f" batch of len {len(batch)}."
                            )
                            break
                        continue
                    batch.extend(messages["Messages"])

                indices = [
                    message["MessageAttributes"]["Index"]["StringValue"]
                    for message in batch
                ]
                indices_to_test = set(indices) - tested_indices
                for index_to_test in indices_to_test:
                    if index_to_test not in await ds_client.get_available_indexes():
                        raise RuntimeError(
                            f"Index {index_to_test} not in document store. Create it"
                            " before pushing articles to it"
                        )
                    else:
                        tested_indices.add(index_to_test)

                files = []
                # Download relevant articles.
                for message in batch:
                    client = (
                        signed_s3_client
                        if bool(message["MessageAttributes"]["Sign"]["StringValue"])
                        else unsigned_s3_client
                    )
                    response = await client.get_object(
                        Bucket=message["MessageAttributes"]["Bucket_Name"][
                            "StringValue"
                        ],
                        Key=message["MessageAttributes"]["Key"]["StringValue"],
                    )
                    body = await response["Body"].read()
                    files.append(body)

                # Parse the articles.
                logger.info(
                    f"[WORKER {worker_n}] Request server to parse"
                    f" {len(batch)} documents."
                )
                filenames = [
                    pathlib.Path(message["MessageAttributes"]["Key"]["StringValue"])
                    for message in batch
                ]

                # Messages do not necessarily use the same parser, so we send them one by one with their own url.
                results = []
                for file, message in zip(files, batch):
                    url = (
                        parser_url
                        + f'/{message["MessageAttributes"]["Parser_Endpoint"]["StringValue"]}'
                    )
                    result = await parser_service.arun(
                        files=[file],
                        url=url,
                        multipart_params={} if "grobid" in url else None,
                        httpx_client=httpx_client,
                    )
                    results.extend(result)
                logger.info(
                    f"[WORKER {worker_n}] Collecting data to upload to the document"
                    " store."
                )
                # Try to upload them to the db. If successful, remove from queue.
                try:
                    await ds_upload(
                        filenames=filenames,
                        results=results,
                        ds_client=ds_client,
                        min_paragraphs_length=min_paragraphs_length,
                        max_paragraphs_length=max_paragraphs_length,
                        indices=indices,
                    )
                    to_delete_from_q = [
                        {
                            "Id": message["MessageId"],
                            "ReceiptHandle": message["ReceiptHandle"],
                        }
                        for (message, result) in zip(batch, results)
                        if result is not None
                    ]
                except (ApiError, ESBulkIndexError, TransportError, OSBulkIndexError):
                    to_delete_from_q = []
                    logger.info(f"[WORKER {worker_n}] Failed parsing the batch.")

                logger.info(
                    f"[WORKER {worker_n}] Batch took {time.time() - start_time_batch}"
                )
                # Remove successful articles from queue.
                for i in range(0, len(to_delete_from_q), 10):
                    response = await q_client.delete_message_batch(
                        QueueUrl=queue_url,
                        Entries=to_delete_from_q[
                            i : min(i + 10, len(to_delete_from_q))
                        ],
                    )
                    if "Failed" in response:
                        logger.info(f"[WORKER {worker_n}] {response['Failed']}")
                    else:
                        logger.info(
                            f"[WORKER {worker_n}] Successfully deleted"
                            f" {len(to_delete_from_q[i:min(i+10, len(to_delete_from_q))])} entries"
                            " from the queue."
                        )
    except BaseException as e:
        logger.info(f"[WORKER {worker_n}] Closed queue polling. {e}")
        await ds_client.close()
        raise e


def sub_process(
    worker_n: int,
    db_url: str,
    parser_url: str,
    queue_url: str,
    db_type: str,
    max_concurrent_requests: int = 10,
    batch_size: int = 500,
    min_paragraphs_length: int | None = None,
    max_paragraphs_length: int | None = None,
    user: str | None = None,
    use_ssl: bool = False,
    verbose: bool = False,
) -> None:
    """Run the main logic."""
    # Additional parameters
    logging_level = logging.INFO if verbose else logging.WARNING

    # setup logging
    logging.basicConfig(
        format="[%(levelname)s]  %(asctime)s %(name)s  %(message)s", level=logging_level
    )
    raise SystemExit(
        asyncio.run(
            run(
                worker_n=worker_n,
                db_url=db_url,
                parser_url=parser_url,
                queue_url=queue_url,
                db_type=db_type,
                max_concurrent_requests=max_concurrent_requests,
                batch_size=batch_size,
                min_paragraphs_length=min_paragraphs_length,
                max_paragraphs_length=max_paragraphs_length,
                user=user,
                use_ssl=use_ssl,
            )
        )
    )


def main() -> None:
    """Run multiple sub_processes."""
    # Parse command line
    parser = get_parser()
    args = parser.parse_args()
    for i in range(cpu_count()):
        p = Process(target=sub_process, kwargs={"worker_n": i + 1, **args.__dict__})
        p.start()


if __name__ == "__main__":
    main()
