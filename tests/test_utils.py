"""Test journal_suggestion related functions."""

import pytest
from fastapi import HTTPException
from scholarag.utils import build_search_query, find_files, format_issn


@pytest.mark.parametrize(
    "source_issns,formatted_issns",
    [
        (None, None),
        ("12345678", "1234-5678"),
        ("345678", "0034-5678"),
        ("12345678 91011121", "1234-5678 9101-1121"),
    ],
)
def test_format_issn(source_issns, formatted_issns):
    """Test issn formatting."""
    result_issns = format_issn(source_issns)
    assert result_issns == formatted_issns


def test_format_issn_error():
    """Test issn formatting raising issue."""
    with pytest.raises(ValueError):
        _ = format_issn("wrong-issn")


def test_find_files(tmp_path):
    """Test filtering files."""
    # Create a fake file
    file1_path = tmp_path / "file1.json"
    file1_path.touch()
    file2_path = tmp_path / "file2.txt"
    file2_path.touch()
    file3_path = tmp_path / "dir" / "file3.json"
    file3_path.parent.mkdir()
    file3_path.touch()
    file4_path = tmp_path / "dir" / "file4.txt"
    file4_path.touch()

    files = find_files(file1_path, False)
    assert len(files) == 1

    files = find_files(tmp_path, False, r".*\.json$")
    assert len(files) == 1

    files = find_files(tmp_path, False)
    assert len(files) == 2

    files = find_files(tmp_path, True, r".*\.json$")
    assert len(files) == 2


def test_find_files_errors(tmp_path):
    """Test filtering files."""
    with pytest.raises(ValueError):
        _ = find_files(tmp_path, False, "")

    # Wrong file mention
    file_path = tmp_path / "doesnotexist.json"
    with pytest.raises(ValueError):
        _ = find_files(file_path, False)


def test_no_topics_or_regions():
    with pytest.raises(HTTPException) as excinfo:
        build_search_query()
    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == "Please provide at least one region or topic."


def test_topics_only():
    topics = ["science", "technology"]
    result = build_search_query(topics=topics)
    expected_topic_queries = [
        {
            "multi_match": {
                "query": "science",
                "type": "phrase",
                "fields": ["title", "text"],
            }
        },
        {
            "multi_match": {
                "query": "technology",
                "type": "phrase",
                "fields": ["title", "text"],
            }
        },
    ]
    assert result["query"]["bool"]["must"] == expected_topic_queries


def test_regions_only():
    regions = ["europe", "asia"]
    result = build_search_query(regions=regions)
    must_list = result["query"]["bool"]["must"]
    assert len(must_list) == 1
    region_bool = must_list[0]
    expected_should = [
        {
            "multi_match": {
                "query": "europe",
                "type": "phrase",
                "fields": ["title", "text"],
            }
        },
        {
            "multi_match": {
                "query": "asia",
                "type": "phrase",
                "fields": ["title", "text"],
            }
        },
    ]
    assert region_bool["bool"]["should"] == expected_should


def test_topics_regions_and_filter():
    topics = ["health"]
    regions = ["north america"]
    filter_query = {"bool": {"must": [{"term": {"status": "active"}}]}}
    result = build_search_query(
        topics=topics, regions=regions, filter_query=filter_query
    )

    must_list = result["query"]["bool"]["must"]

    expected_topic = {
        "multi_match": {
            "query": "health",
            "type": "phrase",
            "fields": ["title", "text"],
        }
    }

    expected_region = {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": "north america",
                        "type": "phrase",
                        "fields": ["title", "text"],
                    }
                }
            ]
        }
    }

    expected_filter = {"term": {"status": "active"}}

    assert expected_topic in must_list
    assert expected_region in must_list
    assert expected_filter in must_list


# Test resolving hierarchy when resolve_hierarchy is True.
def test_resolve_hierarchy(monkeypatch):
    def dummy_get_descendants_names(region, filename):
        return [region, f"{region}_child"]

    monkeypatch.setattr(
        "scholarag.utils.get_descendants_names", dummy_get_descendants_names
    )

    regions = ["wang"]
    result = build_search_query(regions=regions, resolve_hierarchy=True)

    expected_should = [
        {
            "multi_match": {
                "query": "wang",
                "type": "phrase",
                "fields": ["title", "text"],
            }
        },
        {
            "multi_match": {
                "query": "wang_child",
                "type": "phrase",
                "fields": ["title", "text"],
            }
        },
    ]

    region_query = result["query"]["bool"]["must"][0]
    assert region_query is not None
    assert region_query["bool"]["should"] == expected_should
