"""Canvas REST client: host-pinned requests, retries, and pagination."""

from __future__ import annotations

import ipaddress
import logging
import socket
import time
from typing import Any
from urllib.parse import urlparse

import requests

from .utils import CanvasError

LOG = logging.getLogger("canvas_downloader")


def host_is_public(host: str) -> bool:
    """False when host resolves to any private, loopback, link-local, reserved,
    multicast or unspecified address. Blocks off-host download URLs that would
    reach localhost, the cloud metadata endpoint, or the internal network."""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unresolvable: let requests raise a normal connection error
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        ):
            return False
    return True


class CanvasClient:
    def __init__(self, base_url: str, token: str, timeout: float, retries: int):
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Canvas base URL must be an absolute HTTP(S) URL")
        self.host = parsed.netloc
        self.api = self.base_url + "/api/v1"
        self.timeout, self.retries = timeout, retries
        self.session = requests.Session()
        from . import __version__
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": f"Canvas-Course-Downloader/{__version__}",
        })

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != self.host:
            raise CanvasError(f"Refusing API request to unexpected host: {parsed.netloc}")
        kwargs.setdefault("timeout", self.timeout)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                retryable = response.status_code == 429 or 500 <= response.status_code < 600
                if retryable and attempt < self.retries:
                    header = response.headers.get("Retry-After", "")
                    delay = float(header) if header.isdigit() else min(2 ** attempt, 30)
                    LOG.warning(
                        "Canvas returned HTTP %s; retrying in %ss",
                        response.status_code, delay,
                    )
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 30))
            except requests.HTTPError as exc:
                raise CanvasError(f"HTTP error for {url}: {exc}") from exc
        raise CanvasError(f"Request failed after retries: {url}: {last_error}")

    def json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return self.request("GET", url, params=params).json()
        except ValueError as exc:
            raise CanvasError(f"Invalid JSON response from {url}") from exc

    def pages(self, url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        next_url: str | None = url
        next_params = dict(params or {})
        while next_url:
            response = self.request("GET", next_url, params=next_params)
            next_params = {}
            try:
                data = response.json()
            except ValueError as exc:
                raise CanvasError(f"Invalid JSON response from {next_url}") from exc
            if not isinstance(data, list):
                raise CanvasError(f"Expected a list from paginated endpoint: {next_url}")
            output.extend(x for x in data if isinstance(x, dict))
            next_url = response.links.get("next", {}).get("url")
        return output

    def courses(self) -> list[dict[str, Any]]:
        return self.pages(
            f"{self.api}/courses",
            {"enrollment_state": "active", "per_page": 100, "include[]": ["term"]},
        )

    def file_info(self, course_id: int, file_id: int) -> dict[str, Any] | None:
        for url in (
            f"{self.api}/courses/{course_id}/files/{file_id}",
            f"{self.api}/files/{file_id}",
        ):
            try:
                result = self.json(url)
                return result if isinstance(result, dict) else None
            except CanvasError:
                continue
        return None

    def download(self, url: str) -> requests.Response:
        # On-host URLs are fetched with the API session, which carries the
        # bearer token; requests drops that token if Canvas redirects to a
        # different host (for example a signed CDN URL). URLs on any other
        # host - including third-party media embedded in course HTML - are
        # fetched WITHOUT the session, so the Canvas token is never disclosed
        # to an external host on the initial request either. Off-host URLs that
        # resolve to a private, loopback or link-local address are refused to
        # keep attacker-authored embeds from reaching localhost, the cloud
        # metadata endpoint or the internal network. The check covers the
        # initial request only; a public host that redirects to a private one
        # is not re-validated.
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise CanvasError(f"Refusing to download non-HTTP(S) URL: {url}")
        if parsed.netloc == self.host:
            return self.session.get(
                url, stream=True, allow_redirects=True, timeout=self.timeout
            )
        if not host_is_public(parsed.hostname or ""):
            raise CanvasError(f"Refusing to download from non-public host: {parsed.netloc}")
        return requests.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=self.timeout,
            headers={"User-Agent": self.session.headers["User-Agent"]},
        )
