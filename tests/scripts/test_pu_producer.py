"""Test Parse and Upload producer."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from scholarag.scripts.pu_producer import get_parser, run


def test_get_parser():
    parser = get_parser()
    args = parser.parse_args(["bucket-name", "queue-url"])
    assert args.bucket_name == "bucket-name"
    assert args.queue_url == "queue-url"

    # default
    assert args.index == "pmc_paragraphs"
    assert args.parser_name is None
    assert args.start_date is None
    assert args.prefixes is None
    assert args.sign_request is False
    assert args.file_extension is None
    assert args.verbose is False


def moto_config(endpoint_url):
    kw = {
        "endpoint_url": endpoint_url,
        "aws_secret_access_key": "xxx",
        "aws_access_key_id": "xxx",
    }

    return kw


@pytest.mark.asyncio
async def test_run(
    session,
    region,
    config,
    s3_server,
    sqs_server,
    mocking_test,
    s3_verify,
    bucket_name,
    sqs_queue_url,
    monkeypatch,
    create_object,
):
    for i in range(5):
        key_name = "jats_xml/key%s.txt" % i
        await create_object(key_name)

    def get_client(service_name, **kwargs):
        if service_name == "s3":
            kw = moto_config(s3_server) if mocking_test else {}
            return session.create_client(
                "s3", region_name=region, config=config, verify=s3_verify, **kw
            )
        elif service_name == "sqs":
            kw = moto_config(sqs_server) if mocking_test else {}
            return session.create_client("sqs", region_name=region, config=config, **kw)

    get_session_mock = Mock()
    session_mock = Mock()
    get_session_mock.return_value = session_mock
    monkeypatch.setattr("scholarag.scripts.pu_producer.get_session", get_session_mock)
    session_mock.create_client.side_effect = get_client

    index_name = "paragraphs"
    result = await run(
        bucket_name=bucket_name,
        queue_url=sqs_queue_url,
        index=index_name,
        start_date=datetime(1970, 1, 1),
    )

    kw = moto_config(sqs_server) if mocking_test else {}
    async with session.create_client(
        "sqs", region_name=region, config=config, **kw
    ) as sqs_client_tmp:
        # response = await sqs_client_tmp.list_queues()
        response = await sqs_client_tmp.receive_message(
            QueueUrl=sqs_queue_url,
            WaitTimeSeconds=2,
            MaxNumberOfMessages=10,
            MessageAttributeNames=[
                "Key",
                "Bucket_Name",
                "Parser_Endpoint",
                "Sign",
                "Index",
            ],
        )
    assert result == 0
    assert len(response["Messages"]) == 5
    assert {
        "jats_xml/key0.txt",
        "jats_xml/key1.txt",
        "jats_xml/key2.txt",
        "jats_xml/key3.txt",
        "jats_xml/key4.txt",
    } == {
        message["MessageAttributes"]["Key"]["StringValue"]
        for message in response["Messages"]
    }
    assert {"jats_xml"} == {
        message["MessageAttributes"]["Parser_Endpoint"]["StringValue"]
        for message in response["Messages"]
    }
    assert {index_name} == {
        message["MessageAttributes"]["Index"]["StringValue"]
        for message in response["Messages"]
    }
