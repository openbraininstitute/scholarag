"""Producer for parse and upload."""

import argparse
import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from aiobotocore.session import get_session
from botocore import UNSIGNED
from botocore.config import Config

logger = logging.getLogger(__name__)


def get_parser() -> argparse.ArgumentParser:
    """Get parser for command line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "bucket_name",
        type=str,
        help="Url of the provider where to download the articles.",
    )
    parser.add_argument(
        "queue_url",
        type=str,
        help="Url of the queue where to upload the articles.",
    )
    parser.add_argument(
        "--index",
        type=str,
        default="pmc_paragraphs",
        help="Desired name of the index holding paragraphs.",
    )
    parser.add_argument(
        "--parser-name",
        type=str,
        default=None,
        help=(
            "Endpoint of the parser to use. Specify only if the s3 bucket is not ours."
            " Else it will be fetch from the path."
        ),
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Date of the oldest document to download. Format: dd-mm-yyy.",
    )
    parser.add_argument(
        "--prefixes",
        nargs="+",
        type=str,
        default=None,
        help=(
            "Prefix in the s3 path to filter the search on. Can write multiple prefixes"
            " to make it a list."
        ),
    )
    parser.add_argument(
        "--sign-request",
        action="store_true",
        help=(
            "Sign the request with AWS credential. Should be activated for our bucket,"
            " not for public external buckets."
        ),
    )
    parser.add_argument(
        "--file-extension",
        type=str,
        default=None,
        help="Extension of the file to enqueue. Leave None to parse any file type.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Control verbosity",
    )
    return parser


async def run(
    bucket_name: str,
    queue_url: str,
    index: str,
    start_date: datetime,
    parser_name: str | None = None,
    prefixes: list[str | None] | None = None,
    sign_request: bool = False,
    file_extension: str | None = None,
) -> int:
    """Run the queue upload.

    Parameters
    ----------
    bucket_name
        Name of the s3 bucket where the articles are fetched.
    queue_url
        URL of the queue that holds the articles.
    index
        Index in the db where to send the parsed documents.
    start_date
        Date after which articles will be picked.
    parser_name
        Name of the parser to use to parse those documents. Leave None if using our private s3.
    prefixes
        Partial path inside the s3 bucket where to fetch articles.
    sign_request
        Sign the s3 request with AWS credentials. Should be True if there are documents from our private s3 bucket in the queue.
    file_extension
        Partial match of the name of the file (e.g. to specify a specific file type).

    Returns
    -------
    1 or 0
    """
    # Setup s3 bucket
    logger.info("Starting S3 client.")
    session = get_session()
    start_time = time.time()
    async with (
        session.create_client(
            "s3",
            region_name="us-east-1",
            config=Config(signature_version=UNSIGNED) if not sign_request else None,
        ) as s3_client,
        session.create_client("sqs", region_name="us-east-1") as q_client,
    ):
        prefixes = prefixes if prefixes else [None]
        for prefix in prefixes:
            s3_paginator = s3_client.get_paginator("list_objects_v2")
            s3_iterator = s3_paginator.paginate(
                Bucket=bucket_name, Prefix=prefix if prefix else ""
            )
            logger.info(
                f"Filtering interesting articles. Current prefix: {prefix}, current"
                f" date: {start_date}."
            )
            filtered_iterator = s3_iterator.search(
                f"""Contents[?to_string(LastModified)>='\"{start_date.strftime('%Y-%m-%d %H:%M:%S%')}+00:00\"'
                    && contains(Key, '.{file_extension if file_extension else ""}')]"""
            )
            finished = False
            while not finished:
                start_time_batch = time.time()

                messages = []
                i = 0
                parser_names = {
                    "jats_xml",
                    "tei_xml",
                    "xocs_xml",
                    "core_json",
                    "grobid_pdf",
                    "pypdf_pdf",
                    "pubmed_xml",
                }
                # Creating batches.
                async for obj in filtered_iterator:
                    i += 1
                    message: dict[str, Any] = {}
                    s3_bucket_key = obj["Key"]
                    message["Id"] = hashlib.md5(
                        s3_bucket_key.encode(), usedforsecurity=False
                    ).hexdigest()

                    # For our bucket, we assume a layout with 7 folders named after each parser, and corresponding papers inside.
                    # For external bucket, specify directly the name of the parser to use.
                    parser = (
                        parser_name
                        if parser_name
                        else next(
                            (term for term in parser_names if term in s3_bucket_key)
                        )
                    )
                    message["MessageBody"] = "Hello I am the producer."
                    message["MessageAttributes"] = {
                        "Key": {"DataType": "String", "StringValue": s3_bucket_key},
                        "Bucket_Name": {
                            "DataType": "String",
                            "StringValue": bucket_name,
                        },
                        "Parser_Endpoint": {
                            "DataType": "String",
                            "StringValue": parser,
                        },
                        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sqs/client/send_message.html
                        "Sign": {
                            "DataType": "Number",
                            "StringValue": str(int(sign_request)),
                        },
                        "Index": {"DataType": "String", "StringValue": index},
                    }
                    messages.append(message)
                    # 10 is the maximum number of messages one can send per batch.
                    if i == 10:
                        break
                if i != 10:
                    finished = True
                if messages:
                    results = await q_client.send_message_batch(
                        QueueUrl=queue_url, Entries=messages
                    )
                else:
                    continue
                if "Failed" in results:
                    logger.info(f"Failed: {results['Failed']}")
                logger.info(
                    f"Done producing a batch. Took {time.time() - start_time_batch}s to"
                    f" process it. Total time: {time.time() - start_time}"
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
    args.__dict__["start_date"] = start_date
    args.__dict__.pop("verbose")
    raise SystemExit(asyncio.run(run(**args.__dict__)))


if __name__ == "__main__":
    main()
