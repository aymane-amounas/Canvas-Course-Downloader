"""Walk a course and route its content to the download manager."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .client import CanvasClient
from .downloader import DownloadManager
from .extractor import extract_embeds, html_text
from .utils import CanvasError, safe_name

LOG = logging.getLogger("canvas_downloader")


class Exporter:
    def __init__(self, client: CanvasClient, manager: DownloadManager, include_discussions: bool):
        self.client, self.manager = client, manager
        self.api = client.api
        self.include_discussions = include_discussions

    def list_endpoint(
        self, url: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        query = {"per_page": 100}
        if params:
            query.update(params)
        try:
            return self.client.pages(url, query)
        except CanvasError as exc:
            self.manager.errors.append(f"{url}: {exc}")
            LOG.warning("Skipping inaccessible endpoint %s: %s", url, exc)
            return []

    def save_json(self, course: str, folder: str, title: str, data: Any) -> None:
        self.manager.save_text(course, folder, title, json.dumps(data, indent=2, ensure_ascii=False))

    def embedded(self, course_id: int, course: str, folder: str, markup: str | None) -> None:
        ids, direct, frames = extract_embeds(markup, self.client.base_url)
        for file_id in sorted(ids):
            info = self.client.file_info(course_id, file_id)
            if info:
                self.manager.save_file_info(course, folder, info)
        for url in sorted(direct):
            name = safe_name(Path(urlparse(url).path).name or "embedded_media")
            self.manager.save_bytes_from_url(course, folder, name, url)
        if frames:
            self.manager.save_text(
                course, folder, "_embedded_player_links",
                "These links point to external or embedded media players.\n\n" +
                "\n".join(f"- {url}" for url in sorted(frames)),
            )

    def export(self, course_data: dict[str, Any]) -> dict[str, int]:
        course_id = int(course_data["id"])
        course = safe_name(course_data.get("name") or f"course_{course_id}")
        counts = {"modules": 0, "files": 0, "pages": 0, "assignments": 0, "discussions": 0}
        before = dict(self.manager.stats)
        print(f"\n[{course}] (ID: {course_id})")

        # Course details and syllabus.
        try:
            details = self.client.json(
                f"{self.api}/courses/{course_id}",
                {"include[]": ["syllabus_body", "term", "teachers"], "per_page": 100},
            )
            self.save_json(course, "Course_Info", "course_metadata", details)
            syllabus = details.get("syllabus_body") or ""
            if syllabus:
                self.manager.save_text(course, "Course_Info", "Syllabus", html_text(syllabus))
                self.embedded(course_id, course, "Course_Info", syllabus)
        except CanvasError as exc:
            self.manager.errors.append(f"{course}: course details: {exc}")

        # Modules, files, pages, external links, and module item details.
        for module in self.list_endpoint(f"{self.api}/courses/{course_id}/modules"):
            counts["modules"] += 1
            module_folder = safe_name(module.get("name") or f"Module_{module.get('id')}")
            items_url = module.get("items_url")
            if not items_url:
                continue
            for item in self.list_endpoint(items_url):
                kind = item.get("type")
                if kind == "File" and item.get("content_id"):
                    counts["files"] += 1
                    info = self.client.file_info(course_id, int(item["content_id"]))
                    if info:
                        self.manager.save_file_info(course, module_folder, info)
                elif kind == "Page" and item.get("page_url"):
                    counts["pages"] += 1
                    try:
                        page = self.client.json(
                            f"{self.api}/courses/{course_id}/pages/{item['page_url']}"
                        )
                        body = page.get("body") or ""
                        title = page.get("title") or item.get("title") or "Untitled Page"
                        self.manager.save_text(course, module_folder, title, html_text(body))
                        self.embedded(course_id, course, module_folder, body)
                    except CanvasError as exc:
                        self.manager.errors.append(f"{course}/{module_folder}: {exc}")
                elif kind in {"ExternalUrl", "ExternalTool"}:
                    link = item.get("external_url") or item.get("url") or ""
                    self.manager.save_text(
                        course, module_folder, f"external_item_{item.get('id')}",
                        f"{item.get('title', kind)}\n{link}\n",
                    )

        # Every course file visible to the API, as fallback archive.
        for info in self.list_endpoint(f"{self.api}/courses/{course_id}/files"):
            counts["files"] += 1
            self.manager.save_file_info(course, "_unorganized_files", info)

        # Assignments, rubric summaries, and linked resources.
        for assignment in self.list_endpoint(f"{self.api}/courses/{course_id}/assignments"):
            counts["assignments"] += 1
            title = assignment.get("name") or f"Assignment_{assignment.get('id')}"
            description = assignment.get("description") or ""
            lines = [
                f"Assignment: {title}", f"ID: {assignment.get('id', '')}",
                f"Due: {assignment.get('due_at') or 'Not set'}",
                f"Points: {assignment.get('points_possible', 'N/A')}",
                f"Submission types: {', '.join(assignment.get('submission_types') or [])}",
                "", html_text(description),
            ]
            rubric = assignment.get("rubric") or []
            if rubric:
                lines += ["", "RUBRIC"]
                for criterion in rubric:
                    lines.append(
                        f"- {criterion.get('description', '')} ({criterion.get('points', '')} points)"
                    )
            self.manager.save_text(course, "Assignments", title, "\n".join(lines))
            self.embedded(course_id, course, "Assignments", description)

        # Discussions, topic posts, and nested replies. Opt-in: may contain
        # other students' personal information.
        if self.include_discussions:
            for topic in self.list_endpoint(f"{self.api}/courses/{course_id}/discussion_topics"):
                counts["discussions"] += 1
                topic_id = topic.get("id")
                title = topic.get("title") or f"Discussion_{topic_id}"
                message = topic.get("message") or ""
                lines = [
                    f"Discussion: {title}", f"ID: {topic_id}",
                    f"Author: {topic.get('user_name', 'Unknown')}",
                    f"Posted: {topic.get('posted_at', '')}", "", html_text(message),
                    "", "REPLIES", "=======",
                ]
                self.embedded(course_id, course, "Discussions", message)
                if topic_id:
                    try:
                        view = self.client.json(
                            f"{self.api}/courses/{course_id}/discussion_topics/{topic_id}/view"
                        )
                        people = {
                            p.get("id"): p.get("display_name", "Unknown")
                            for p in view.get("participants", [])
                        }

                        def walk(
                            entries: list[dict[str, Any]],
                            depth: int = 0,
                            people: dict[Any, str] = people,
                            lines: list[str] = lines,
                        ) -> None:
                            for entry in entries:
                                author = people.get(entry.get("user_id"), "Unknown")
                                body = entry.get("message") or ""
                                lines.extend([
                                    f"{'  ' * depth}[{author} | {entry.get('created_at', '')}]",
                                    html_text(body),
                                ])
                                self.embedded(course_id, course, "Discussions", body)
                                walk(entry.get("replies") or [], depth + 1)

                        walk(view.get("view") or [])
                    except CanvasError as exc:
                        self.manager.errors.append(f"{course}: discussion {topic_id}: {exc}")
                self.manager.save_text(course, "Discussions", title, "\n".join(lines))

        # Announcements: Canvas excludes them from discussion_topics unless
        # only_announcements is requested explicitly.
        for item in self.list_endpoint(
            f"{self.api}/courses/{course_id}/discussion_topics",
            {"only_announcements": "true"},
        ):
            title = item.get("title") or f"Announcement_{item.get('id')}"
            body = item.get("message") or ""
            self.manager.save_text(
                course, "Announcements", title,
                f"{title}\nPosted: {item.get('posted_at', '')}\n\n{html_text(body)}",
            )
            self.embedded(course_id, course, "Announcements", body)

        # Quizzes and quiz question metadata (when exposed to this user).
        for quiz in self.list_endpoint(f"{self.api}/courses/{course_id}/quizzes"):
            quiz_id = quiz.get("id")
            title = quiz.get("title") or f"Quiz_{quiz_id}"
            self.save_json(course, "Quizzes", title, quiz)
            if quiz_id:
                questions = self.list_endpoint(
                    f"{self.api}/courses/{course_id}/quizzes/{quiz_id}/questions"
                )
                if questions:
                    self.save_json(course, "Quizzes", f"{title}_questions", questions)

        # Canvas media objects: optional endpoint, not enabled on every instance.
        for obj in self.list_endpoint(f"{self.api}/courses/{course_id}/media_objects"):
            media_id = obj.get("media_id") or obj.get("id")
            title = safe_name(obj.get("title") or f"media_{media_id}")
            for source in obj.get("media_sources") or []:
                url = source.get("url")
                if url:
                    ext = safe_name(source.get("fileext") or "mp4")
                    self.manager.save_bytes_from_url(
                        course, "Media_Videos", f"{title}.{ext}", url,
                        file_id=f"media:{media_id}:{ext}",
                    )

        delta = {k: self.manager.stats[k] - before[k] for k in self.manager.stats}
        self._print_course_report(counts, delta)
        return counts

    @staticmethod
    def _print_course_report(counts: dict[str, int], delta: dict[str, int]) -> None:
        rows = [
            ("Modules", counts["modules"]),
            ("Files", counts["files"]),
            ("Pages", counts["pages"]),
            ("Assignments", counts["assignments"]),
            ("Discussions", counts["discussions"]),
            ("Downloaded", delta["downloaded"]),
            ("Skipped", delta["skipped"]),
            ("Failed", delta["failed"]),
        ]
        for label, value in rows:
            print(f"  {label} {'.' * (20 - len(label))} {value}")
