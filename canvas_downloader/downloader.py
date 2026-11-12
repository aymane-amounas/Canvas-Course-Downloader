"""Streaming, atomic downloads with a persistent resume manifest."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import requests

from .client import CanvasClient
from .utils import safe_name, sha256_file, under_root

LOG = logging.getLogger("canvas_downloader")


class DownloadManager:
    def __init__(self, client: CanvasClient, output: Path, dry_run: bool):
        self.client = client
        self.output = output.expanduser().resolve()
        self.dry_run = dry_run
        self.manifest_path = self.output / "manifest.json"
        self.manifest: dict[str, Any] = {"version": 1, "downloads": {}}
        self.stats = {"downloaded": 0, "skipped": 0, "failed": 0, "planned": 0}
        self.errors: list[str] = []
        if not dry_run:
            self.output.mkdir(parents=True, exist_ok=True)
            if self.manifest_path.exists():
                try:
                    old = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                    if isinstance(old, dict) and isinstance(old.get("downloads"), dict):
                        self.manifest = old
                except (OSError, json.JSONDecodeError):
                    LOG.warning("Could not read manifest; creating a new one.")

    def save_manifest(self) -> None:
        if self.dry_run:
            return
        temp = self.manifest_path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temp, self.manifest_path)

    def save_bytes_from_url(
        self, course: str, folder: str, name: str, url: str,
        file_id: int | str | None = None, expected_size: int | None = None,
    ) -> None:
        destination = under_root(self.output, course, folder, name)
        relative = destination.relative_to(self.output).as_posix()
        key = f"{file_id if file_id is not None else url}|{relative}"
        record = self.manifest["downloads"].get(key, {})
        if destination.exists():
            size_ok = expected_size is None or destination.stat().st_size == expected_size
            hash_ok = not record.get("sha256") or sha256_file(destination) == record["sha256"]
            if size_ok and hash_ok:
                self.stats["skipped"] += 1
                return
            if not self.dry_run:
                destination.unlink(missing_ok=True)
        if self.dry_run:
            self.stats["planned"] += 1
            print(f"  [DRY RUN] {relative}")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".part")
        try:
            response = self.client.download(url)
            response.raise_for_status()
            total = 0
            with response, partial.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        stream.write(chunk)
                        total += len(chunk)
                stream.flush()
                os.fsync(stream.fileno())
                content_length = response.headers.get("Content-Length")
            if expected_size is not None and total != expected_size:
                raise OSError(f"Expected {expected_size} bytes, received {total}")
            if content_length and content_length.isdigit() and total != int(content_length):
                raise OSError(f"Transfer incomplete: expected {content_length}, received {total}")
            digest = sha256_file(partial)
            os.replace(partial, destination)
            self.manifest["downloads"][key] = {
                "file_id": file_id, "path": relative, "size": total,
                "sha256": digest, "status": "complete",
            }
            self.save_manifest()
            self.stats["downloaded"] += 1
            print(f"  [+] {relative}")
        except (requests.RequestException, OSError, ValueError) as exc:
            partial.unlink(missing_ok=True)
            self.stats["failed"] += 1
            self.errors.append(f"{relative}: {exc}")
            LOG.error("Download failed: %s: %s", relative, exc)

    def save_text(self, course: str, folder: str, title: str, content: str) -> None:
        destination = under_root(self.output, course, folder, safe_name(title) + ".txt")
        relative = destination.relative_to(self.output).as_posix()
        key = f"text|{relative}"
        if destination.exists():
            record = self.manifest["downloads"].get(key, {})
            if record.get("sha256") == sha256_file(destination):
                self.stats["skipped"] += 1
                return
            if not record:
                self.stats["skipped"] += 1
                return
        if self.dry_run:
            self.stats["planned"] += 1
            print(f"  [DRY RUN] {relative}")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".part")
        try:
            temp.write_text(content, encoding="utf-8")
            os.replace(temp, destination)
            self.manifest["downloads"][key] = {
                "path": relative, "size": destination.stat().st_size,
                "sha256": sha256_file(destination), "status": "complete",
            }
            self.save_manifest()
            self.stats["downloaded"] += 1
        except OSError as exc:
            temp.unlink(missing_ok=True)
            self.stats["failed"] += 1
            self.errors.append(f"{relative}: {exc}")

    def save_file_info(self, course: str, folder: str, info: dict[str, Any]) -> None:
        url = info.get("url")
        if not url:
            self.stats["failed"] += 1
            self.errors.append(f"File {info.get('id')}: Canvas did not return a download URL")
            return
        raw_size = info.get("size")
        try:
            size = int(raw_size) if raw_size is not None else None
        except (TypeError, ValueError):
            size = None
        name = info.get("display_name") or info.get("filename") or f"file_{info.get('id', 'unknown')}"
        self.save_bytes_from_url(course, folder, safe_name(name), url, info.get("id"), size)
