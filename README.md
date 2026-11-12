# Canvas Course Downloader

A Python CLI tool for downloading and organizing accessible Canvas course materials for offline study.

It traverses modules, exports pages and course information, downloads Canvas files and supported direct media, and saves assignments, discussions, announcements, quizzes, and syllabus content when the Canvas API allows access.

> **Scope:** This is a best-effort course archive, not a complete Canvas backup. It cannot bypass course permissions, institutional restrictions, locked content, or protected third-party streaming services.

## Features

- Interactive course selection, `--all`, or one/multiple `--course ID` values.
- Module-based folders containing module files and exported pages.
- Embedded Canvas file discovery in pages, assignments, syllabus, and discussions.
- Direct linked media/document downloads for supported file extensions.
- Assignment instructions, due dates, points, rubric summaries, and linked resources.
- Discussion topics and nested replies, opt-in via `--include-discussions` (off by default; posts can contain other students' data).
- Announcements, quiz metadata, and quiz question metadata when accessible.
- Course metadata and syllabus export.
- Course-wide file fallback in `_unorganized_files`.
- Optional Canvas media-object endpoint support when enabled by the institution.
- Persistent `manifest.json` with file sizes and SHA-256 hashes.
- Atomic `.part` downloads, retries, timeouts, pagination, portable filenames, and reports.
- Dry-run mode and per-course error isolation.

## Requirements

- Python 3.10+
- Canvas API access token
- Permission to access the selected courses and files

## Install

```bash
git clone https://github.com/YOUR_USERNAME/canvas-course-downloader.git
cd canvas-course-downloader

python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Canvas token setup

In Canvas, open **Account → Settings → New Access Token** (the wording may vary by institution).

Set your Canvas instance and token as environment variables.

macOS / Linux:

```bash
export CANVAS_BASE_URL="https://your-school.instructure.com"
export CANVAS_API_TOKEN="your-token"
```

Windows PowerShell:

```powershell
$env:CANVAS_BASE_URL = "https://your-school.instructure.com"
$env:CANVAS_API_TOKEN = "your-token"
```

If `CANVAS_API_TOKEN` is not set, the program prompts for it without echoing the token.

**Never hardcode your token, commit it, or share it.** Revoke it in Canvas if exposed.

## Usage

```bash
# Interactive course picker
canvas-downloader

# Download all active courses visible to your account
canvas-downloader --all

# Download one course
canvas-downloader --course 123456

# Download multiple courses
canvas-downloader --course 123456 --course 67890

# Select an output folder
canvas-downloader --all --output ~/University

# Preview paths without writing files
canvas-downloader --all --dry-run

# Explicit Canvas instance
canvas-downloader --base-url https://aui.instructure.com --all

# Include discussion posts/replies (off by default; may contain other students' data)
canvas-downloader --all --include-discussions

# Adjust network behavior
canvas-downloader --all --timeout 60 --retries 8

# Help and version
canvas-downloader --help
canvas-downloader --version
```

You can also run it without installing the console command:

```bash
python -m canvas_downloader --all
```

`--resume` is included as an explicit reminder, but resuming/skipping completed files is the default. Completed files are checked against their manifest hash and/or expected Canvas file size. Interrupted `.part` files are discarded and downloaded again; HTTP byte-range continuation is not implemented.

## Output structure

```text
Canvas_Downloads/
├── manifest.json
├── report.json
├── errors.txt                    # only if errors occurred
│
├── Object Oriented Programming/
│   ├── Course_Info/
│   │   ├── course_metadata.txt
│   │   └── Syllabus.txt
│   ├── Week 1 - Introduction/
│   │   ├── lecture.pdf
│   │   └── Introduction.txt
│   ├── Assignments/
│   ├── Discussions/
│   ├── Announcements/
│   ├── Quizzes/
│   ├── Media_Videos/
│   └── _unorganized_files/
└── Calculus/
    └── ...
```

Metadata files containing JSON are saved as text files with JSON-formatted content.

## What can be downloaded?

| Canvas content | Behavior |
|---|---|
| Modules | Lists modules and walks their items |
| Module files | Downloads files into their module folder |
| Pages | Exports readable text and extracts linked files |
| Course files | Downloads API-visible course files into fallback folder |
| Syllabus | Exports syllabus text and linked resources |
| Assignments | Exports instructions, due dates, points, rubric summaries, and embeds |
| Discussions | Exports topics and nested replies where permitted |
| Announcements | Exports topics flagged as announcements |
| Quizzes | Exports quiz and question metadata where exposed |
| Embedded files | Resolves Canvas `/files/ID` links through the API |
| Direct media | Downloads supported direct media URLs |
| External players | Saves iframe URLs as references; does not rip protected streams |
| Canvas media objects | Attempts the optional media endpoint and exposed direct sources |

### Important limitations

Canvas is configurable by each institution. Some endpoints may be disabled, some content may be hidden by role/section/date settings, and some API responses require additional permissions.

This tool does **not** promise to download:

- Kaltura, Panopto, Canvas Studio, YouTube, or other protected streams.
- External tools or content hosted outside Canvas when no direct downloadable file is exposed.
- Locked quizzes, unpublished content, or files your account cannot access.
- Every reply or attachment in every discussion configuration.

Failures are reported in `errors.txt` and `report.json`; the rest of the course export continues when possible.

## Resume and integrity

`manifest.json` stores the destination, Canvas file ID when available, byte size, SHA-256 hash, and completion status. A file referenced in multiple modules can be stored in each relevant module folder because the manifest key includes both file identity and destination path.

Downloads are written to a `.part` file and renamed only after the transfer completes and size checks pass. A failed transfer does not become a completed manifest entry.

## Privacy and responsible use

- Use only with an account and courses you are authorized to access.
- Follow your institution's copyright, acceptable-use, and data-retention policies.
- Discussion exports can include other students' names and posts. Keep archives private and secure.
- Never commit API tokens, downloaded course materials, student information, or private API responses.
- The software does not bypass Canvas permissions or access controls.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

Tests run locally with fixtures and do not need a live Canvas account.

## Contributing

Issues and pull requests are welcome.

1. Describe bugs or feature requests in an issue.
2. Never attach API tokens, student information, or private course materials.
3. Add tests for behavior changes.
4. Run `pytest` and `ruff check .`.
5. Document any Canvas API permission requirements.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This project is independent and is not affiliated with, endorsed by, or sponsored by Instructure or Canvas LMS.

---

<p align="center">
  Built with curiosity. Engineered with purpose.
</p>

---

<sub>Built by [Aymane](https://github.com/aymane-amounas)</sub>
