import pathlib
from pathlib import Path

import pytest
from scholarag.scripts.create_impact_factor_index import (
    IMPACT_FACTORS_MAPPING,
    get_parser,
    run,
)


def test_get_parser():
    parser = get_parser()
    args = parser.parse_args(["path/to/file.xlsx", "index_name", "db_url"])
    assert isinstance(args.from_file, Path)
    assert str(args.from_file) == "path/to/file.xlsx"
    assert args.index == "index_name"
    assert args.db_url == "db_url"
    # default values
    assert args.db_type == "opensearch"
    assert args.user is None
    assert args.verbose is False

    # flags
    args = parser.parse_args(["path/to/file.xlsx", "index_name", "db_url", "-v"])
    assert args.verbose is True

    # errors
    with pytest.raises(SystemExit):
        _ = parser.parse_args(
            ["path/to/file.json", "parser_url", "db_url", "--db-type", "wrong-type"]
        )


def test_run_errors(get_testing_ds_client, tmp_path):
    ds_client, parameters = get_testing_ds_client

    with pytest.raises(ValueError) as e:
        run(
            document_store=ds_client,
            from_file=Path("file/does/not/exists.json"),
            index="impact_factors",
            settings=parameters[1],
        )

    assert "The file file/does/not/exists.json does not exist." == str(e.value)

    ds_client.create_index(
        "test_impact_factor1",
        mappings=IMPACT_FACTORS_MAPPING,
        settings=parameters[1],
    )

    with pytest.raises(ValueError) as e1:
        file = pathlib.Path(__file__).parent.parent / "data" / "citescore_sample.xlsx"
        run(
            document_store=ds_client,
            from_file=file,
            index="test_impact_factor1",
            settings=parameters[1],
        )

    assert str(e1.value) == "The index test_impact_factor1 already exists."


def test_run(get_testing_ds_client, tmp_path):
    ds_client, parameters = get_testing_ds_client
    file = pathlib.Path(__file__).parent.parent / "data" / "citescore_sample.xlsx"
    run(
        document_store=ds_client,
        from_file=file,
        index="test_impact_factors",
        settings=parameters[1],
    )
    ds_client.client.indices.refresh()
    assert ds_client.count_documents(index="test_impact_factors") == 3
