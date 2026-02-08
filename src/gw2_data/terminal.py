"""
Terminal output formatting utilities with ANSI color support.

Provides colored output functions optimized for dark terminal backgrounds,
progress indicators, and structured error messages for the populate scripts.
"""

import sys
from enum import Enum


class Color(Enum):
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def colorize(text: str, *colors: Color) -> str:
    if not _supports_color():
        return text
    prefix = "".join(c.value for c in colors)
    return f"{prefix}{text}{Color.RESET.value}"


def debug(message: str) -> None:
    print(colorize(message, Color.DIM, Color.BRIGHT_BLACK))


def info(message: str) -> None:
    print(message)


def success(message: str) -> None:
    print(colorize(message, Color.BRIGHT_GREEN))


def warning(message: str) -> None:
    print(colorize(f"⚠ {message}", Color.BRIGHT_YELLOW))


def error(message: str) -> None:
    print(colorize(f"✗ {message}", Color.BRIGHT_RED), file=sys.stderr)


def section_header(title: str) -> None:
    separator = "=" * 60
    print(f"\n{colorize(separator, Color.BRIGHT_BLUE)}")
    print(colorize(title, Color.BOLD, Color.BRIGHT_CYAN))
    print(colorize(separator, Color.BRIGHT_BLUE))


def subsection(title: str) -> None:
    print(f"\n{colorize(title, Color.BOLD)}")


def progress(current: int, total: int, message: str = "") -> None:
    prefix = colorize(f"[{current}/{total}]", Color.BRIGHT_CYAN)
    print(f"{prefix} {message}")


def key_value(key: str, value: str, indent: int = 0) -> None:
    spaces = " " * indent
    colored_key = colorize(f"{key}:", Color.BRIGHT_WHITE)
    print(f"{spaces}{colored_key} {value}")


def bullet(message: str, indent: int = 2, symbol: str = "•") -> None:
    spaces = " " * indent
    print(f"{spaces}{colorize(symbol, Color.BRIGHT_BLUE)} {message}")


def code_block(content: str) -> None:
    print(colorize(content, Color.DIM))


def link(url: str, label: str | None = None) -> str:
    display = label or url
    if _supports_color():
        colored_text = colorize(display, Color.BRIGHT_CYAN, Color.BOLD)
        return f"\033]8;;{url}\033\\{colored_text}\033]8;;\033\\"
    return f"{display} ({url})"


def error_with_context(
    error_msg: str,
    context: dict[str, str] | None = None,
    suggestions: list[str] | None = None,
) -> None:
    error(error_msg)

    if context:
        print()
        for key, value in context.items():
            key_value(key, value, indent=2)

    if suggestions:
        print()
        print(colorize("Suggestions:", Color.BRIGHT_YELLOW))
        for suggestion in suggestions:
            bullet(suggestion, indent=2, symbol="→")
