"""Test journal_suggestion related functions."""

import pytest
from scholarag.utils import find_files, format_issn


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
