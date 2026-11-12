from pathlib import Path

from canvas_downloader.utils import safe_name, under_root


def test_safe_name_strips_path_separators_and_control_chars():
    assert safe_name("a/b\\c") == "a_b_c"
    assert safe_name("file\x00name") == "file_name"


def test_safe_name_rejects_dot_segments():
    assert safe_name("..") == "untitled"
    assert safe_name(".") == "untitled"
    assert safe_name("") == "untitled"


def test_safe_name_escapes_windows_reserved():
    assert safe_name("CON") == "_CON"
    assert safe_name("com1") == "_com1"
    assert safe_name("nul.txt") == "_nul.txt"


def test_safe_name_trims_trailing_dots_and_spaces():
    assert safe_name("report. ") == "report"
    assert safe_name("  spaced  ") == "spaced"


def test_safe_name_truncates_long_input():
    assert len(safe_name("x" * 500)) == 150


def test_under_root_allows_nested_paths(tmp_path: Path):
    result = under_root(tmp_path, "course", "folder", "file.pdf")
    assert result == (tmp_path / "course" / "folder" / "file.pdf").resolve()


def test_under_root_neutralizes_traversal(tmp_path: Path):
    # safe_name turns ".." into a harmless component, so the result stays inside root.
    result = under_root(tmp_path, "..", "..", "etc")
    assert tmp_path.resolve() in result.parents
    assert "untitled" in result.parts  # ".." was sanitized away
