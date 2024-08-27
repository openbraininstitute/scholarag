from scholarag.scripts.pu_consumer import get_parser


def test_get_parser():
    parser = get_parser()
    args = parser.parse_args(["db_url", "parser_url", "queue_url"])
    assert args.db_url == "db_url"
    assert args.parser_url == "parser_url"
    assert args.queue_url == "queue_url"

    # default
    assert args.batch_size == 500
    assert args.max_paragraphs_length is None
    assert args.min_paragraphs_length is None
    assert args.max_concurrent_requests == 10
    assert args.db_type == "opensearch"
    assert args.user is None
    assert args.use_ssl is False
    assert args.verbose is False
