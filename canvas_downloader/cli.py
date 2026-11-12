"""Command-line entry point: arguments, course selection, and reporting."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests

from . import __version__
from .client import CanvasClient
from .config import Config, ConfigError
from .downloader import DownloadManager
from .organizer import Exporter
from .utils import CanvasError

LOG = logging.getLogger("canvas_downloader")


def choose_courses(courses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    print("\nAccessible active courses:")
    for index, course in enumerate(courses, 1):
        print(f"  {index:>2}. {course.get('name', 'Unnamed')} (ID: {course.get('id')})")
    answer = input("\nSelect numbers separated by commas, 'all', or 'q': ").strip().lower()
    if answer in {"q", "quit"}:
        return []
    if answer == "all":
        return courses
    try:
        indexes = {int(part.strip()) for part in answer.split(",") if part.strip()}
        if not indexes or min(indexes) < 1 or max(indexes) > len(courses):
            raise ValueError
        return [course for i, course in enumerate(courses, 1) if i in indexes]
    except ValueError:
        print("Invalid selection.")
        return []


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="canvas-downloader",
        description="Archive accessible Canvas course content for offline use.",
    )
    p.add_argument(
        "--base-url",
        default=os.getenv("CANVAS_BASE_URL", "https://canvas.instructure.com"),
        help="Canvas instance base URL (env: CANVAS_BASE_URL).",
    )
    p.add_argument("--course", type=int, action="append", help="Course ID; repeat to select multiple.")
    p.add_argument("--all", action="store_true", dest="all_courses", help="Download all active courses.")
    p.add_argument("--output", type=Path, default=Path("./Canvas_Downloads"))
    p.add_argument("--resume", action="store_true", help="Resume from manifest (also the default behavior).")
    p.add_argument("--dry-run", action="store_true", help="Preview destinations without writing files.")
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--retries", type=int, default=5)
    p.add_argument(
        "--include-discussions",
        action="store_true",
        help="Export discussion topics and replies (may contain other students' personal data).",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _select_courses(client: CanvasClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.course:
        selected = []
        for course_id in args.course:
            try:
                selected.append(client.json(f"{client.api}/courses/{course_id}"))
            except CanvasError as exc:
                print(f"Could not access course {course_id}: {exc}", file=sys.stderr)
        return selected
    print("Fetching active courses...")
    available = client.courses()
    return available if args.all_courses else choose_courses(available)


def _final_report(
    manager: DownloadManager, totals: dict[str, int], processed: int, output: Path, dry_run: bool
) -> None:
    print("\n" + "─" * 40)
    print("Download completed." if not dry_run else "Dry run completed.")
    print(f"  Courses processed .... {processed}")
    print(f"  Files downloaded ..... {manager.stats['downloaded']}")
    print(f"  Files skipped ........ {manager.stats['skipped']}")
    print(f"  Files failed ......... {manager.stats['failed']}")
    print(f"  Pages exported ....... {totals['pages']}")
    print(f"  Errors ............... {len(manager.errors)}")
    print(f"\n  Output: {output}")
    if not dry_run:
        print(f"  Report: {output / 'report.json'}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if args.all_courses and args.course:
        print("Choose either --all or --course, not both.", file=sys.stderr)
        return 2

    try:
        config = Config.from_args(args)
    except ConfigError as exc:
        print(f"Error: {exc}.", file=sys.stderr)
        return 2

    try:
        client = CanvasClient(config.base_url, config.token, config.timeout, config.retries)
        print(f"\nCanvas Course Downloader {__version__}")
        print(f"Canvas: {client.host}")

        selected = _select_courses(client, args)
        if not selected:
            print("No courses selected.")
            return 0

        print(f"\nSelected {len(selected)} course(s).")
        print(f"Output: {config.output.expanduser().resolve()}")
        if config.dry_run:
            print("DRY RUN: nothing will be written.")

        manager = DownloadManager(client, config.output, config.dry_run)
        exporter = Exporter(client, manager, config.include_discussions)
        totals = {"modules": 0, "files": 0, "pages": 0, "assignments": 0, "discussions": 0}
        processed = 0
        for course in selected:
            if not course.get("id"):
                manager.errors.append(f"Course has no ID: {course!r}")
                continue
            try:
                counts = exporter.export(course)
                for key in totals:
                    totals[key] += counts.get(key, 0)
                processed += 1
            except Exception as exc:
                LOG.exception("Unexpected error in course %s", course.get("id"))
                manager.errors.append(f"Course {course.get('id')}: {exc}")

        _final_report(manager, totals, processed, manager.output, config.dry_run)

        if not config.dry_run:
            (manager.output / "report.json").write_text(
                json.dumps(
                    {"stats": manager.stats, "totals": totals, "errors": manager.errors},
                    indent=2,
                ),
                encoding="utf-8",
            )
            if manager.errors:
                (manager.output / "errors.txt").write_text(
                    "\n".join(manager.errors) + "\n", encoding="utf-8"
                )
        return 1 if manager.stats["failed"] or manager.errors else 0
    except (CanvasError, requests.RequestException, OSError, ValueError) as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1
