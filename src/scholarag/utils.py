"""Utilities for the master API."""

import logging
import re
from pathlib import Path

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
