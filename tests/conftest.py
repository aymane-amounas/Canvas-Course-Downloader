"""Shared test doubles for the Canvas client and downloader."""

from __future__ import annotations

from typing import Any


class FakeResponse:
    """Minimal stand-in for requests.Response used across client/download tests."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        links: dict[str, dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ):
        self.status_code = status_code
        self._json = json_data
        self.links = links or {}
        self.headers = headers or {}
        self._chunks = chunks or []

    def json(self) -> Any:
        if isinstance(self._json, Exception):
            raise self._json
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, _size: int):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
