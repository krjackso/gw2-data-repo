from io import StringIO
from unittest.mock import patch

from gw2_data import terminal


def test_colorize_with_tty():
    with patch("sys.stdout.isatty", return_value=True):
        result = terminal.colorize("test", terminal.Color.RED)
        assert "\033[31m" in result
        assert "test" in result
        assert "\033[0m" in result


def test_colorize_without_tty():
    with patch("sys.stdout.isatty", return_value=False):
        result = terminal.colorize("test", terminal.Color.RED)
        assert result == "test"
        assert "\033" not in result


def test_link_with_tty():
    with patch("sys.stdout.isatty", return_value=True):
        result = terminal.link("https://example.com", "Example")
        assert "https://example.com" in result
        assert "Example" in result
        assert "\033]8;" in result


def test_link_without_tty():
    with patch("sys.stdout.isatty", return_value=False):
        result = terminal.link("https://example.com", "Example")
        assert result == "Example (https://example.com)"


def test_error_with_context():
    output = StringIO()
    with patch("sys.stderr", output):
        terminal.error_with_context(
            "Something failed",
            context={"Item ID": "12345", "Name": "Test Item"},
            suggestions=["Try using --overwrite", "Check the wiki page"],
        )

    result = output.getvalue()
    assert "Something failed" in result


def test_progress_output():
    output = StringIO()
    with patch("sys.stdout", output):
        terminal.progress(5, 10, "Processing item")

    result = output.getvalue()
    assert "[5/10]" in result
    assert "Processing item" in result
