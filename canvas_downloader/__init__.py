"""Canvas Course Downloader — archive accessible Canvas course content."""

from __future__ import annotations

__version__ = "1.0.0"
VERSION = __version__


def main(argv: list[str] | None = None) -> int:
    from .cli import main as _main
    return _main(argv)


__all__ = ["VERSION", "__version__", "main"]
