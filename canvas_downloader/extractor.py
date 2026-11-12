"""HTML-to-text conversion and embedded-resource extraction."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .utils import MEDIA_EXTENSIONS


def html_text(markup: str | None) -> str:
    """Render Canvas HTML as readable plain text, keeping link/image references."""
    if not markup:
        return ""
    soup = BeautifulSoup(markup, "html.parser")
    for img in soup.find_all("img"):
        alt, src = img.get("alt", "Image"), img.get("src")
        img.replace_with(f" [Image: {alt} ({src})] " if src else f" [Image: {alt}] ")
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True) or anchor["href"]
        anchor.replace_with(f" [{label}]({anchor['href']}) ")
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def extract_embeds(markup: str | None, base_url: str) -> tuple[set[int], set[str], set[str]]:
    """Find Canvas file IDs, direct downloadable URLs, and iframe player links."""
    ids: set[int] = set()
    direct: set[str] = set()
    frames: set[str] = set()
    if not markup:
        return ids, direct, frames
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup.find_all(["a", "img", "source", "video", "audio", "iframe"]):
        raw = tag.get("href") or tag.get("src") or tag.get("data-src")
        if not raw:
            continue
        url = urljoin(base_url, raw)
        parsed = urlparse(url)
        match = re.search(r"/files/(\d+)", parsed.path)
        if match:
            ids.add(int(match.group(1)))
        elif tag.name == "iframe":
            frames.add(url)
        elif parsed.scheme in {"http", "https"}:
            suffix = Path(parsed.path).suffix.lower()
            if suffix in MEDIA_EXTENSIONS:
                direct.add(url)
    return ids, direct, frames
