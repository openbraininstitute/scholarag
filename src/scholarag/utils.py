"""Utilities for the master API."""

import logging
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from scholarag.hierarchy_resolving import get_descendants_names

logger = logging.getLogger(__name__)


def format_issn(source_issns: str | None) -> str | None:
    """Reformat issns to contain dash and add heading zeroes.

    Parameters
    ----------
    source_issns
        Single str containing original issns from the index.

    Returns
    -------
    str | None
        Single str containing formatted issns or None.
    """
    issn_pattern = r"^\d{4}-\d{3}[0-9X]$"

    if source_issns is None:
        return None
    else:
        issns = []

        for issn in source_issns.split():
            issn = issn.rjust(8, "0")

            issn = issn[:4] + "-" + issn[4:]
            if not re.match(issn_pattern, issn):
                raise ValueError(f"ISSN '{issn}' not in correct format.")
            issns.append(issn)

        return " ".join(issns)


def find_files(
    input_path: Path,
    recursive: bool,
    match_filename: str | None = None,
) -> list[Path]:
    """Find files inside of `input_path`.

    Parameters
    ----------
    input_path
        File or directory to consider.
    recursive
        If True, directories and all subdirectories are considered in a recursive way.
    match_filename
        Only filename matching match_filename are kept.

    Returns
    -------
    inputs : list[Path]
        List of kept files.

    Raises
    ------
    ValueError
        If the input_path does not exists.
    """
    if input_path.is_file():
        return [input_path]

    elif input_path.is_dir():
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"
        files = (x for x in input_path.glob(pattern) if x.is_file())

        if match_filename is None:
            selected = files
        elif match_filename == "":
            raise ValueError("Value for argument 'match-filename' should not be empty!")
        else:
            regex = re.compile(match_filename)
            selected = (x for x in files if regex.fullmatch(x.name))

        return sorted(selected)

    else:
        raise ValueError(
            "Argument 'input_path' should be a path to an existing file or directory!"
        )


def build_search_query(
    topics: list[str] | None = None,
    regions: list[str] | None = None,
    filter_query: dict[str, Any] | None = None,
    resolve_hierarchy: bool = False,
) -> dict[str, Any]:
    """
    Build the Elasticsearch query and aggregations based on provided topics, regions, and filters.

    Args:
        topics: A list of topic keywords to match against "title" and "text".
        regions: A list of region keywords to match against "title" and "text".
        filter_query: Additional filter query dict with a structure containing {"bool": {"must": ...}}.
        number_results: The number of results to include in the aggregation.
        sort_by_date: If True, adjust the aggregation to sort by the "date" field instead of relevance.

    Raises
    ------
        HTTPException: If neither topics nor regions are provided.

    Returns
    -------
        query: The main query dict.
    """
    if not topics and not regions:
        raise HTTPException(
            status_code=422, detail="Please provide at least one region or topic."
        )

    # Build queries for topics.
    topic_query = (
        [
            {
                "multi_match": {
                    "query": topic,
                    "type": "phrase",
                    "fields": ["title", "text"],
                }
            }
            for topic in topics
        ]
        if topics is not None
        else []
    )

    # Resolve names of the brain hierarchy
    if regions and resolve_hierarchy:
        expanded_brain_regions = []
        for region in regions:
            expanded_brain_regions.extend(
                get_descendants_names(region, "brainregion_hierarchy.json")
            )
        # limit query length because of OS limit of 1024
        max_query_len = 1024 - len(topics) if topics else 1024
        if 2 * len(expanded_brain_regions) > max_query_len:  # 2 queries per region
            expanded_brain_regions = expanded_brain_regions[: max_query_len // 2]

    else:
        expanded_brain_regions = regions  # type: ignore

    # Build queries for regions.
    regions_query = (
        [
            {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": region,
                                "type": "phrase",
                                "fields": ["title", "text"],
                            }
                        }
                        for region in expanded_brain_regions
                    ]
                }
            }
        ]
        if regions is not None
        else []
    )

    # Extract filter queries if provided.
    filter_query_list = (
        filter_query.get("bool", {}).get("must", []) if filter_query else []
    )

    # Construct the main query.
    query: dict[str, Any] = {
        "query": {
            "bool": {
                "must": [
                    *topic_query,
                    *regions_query,
                    *filter_query_list,
                ]
            }
        }
    }

    return query
