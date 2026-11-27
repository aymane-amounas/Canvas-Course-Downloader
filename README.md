# Canvas Course Downloader

I wrote this because Canvas is where all my course material lives, and I wanted a local copy I could actually keep. It's a Python CLI that walks through a course, pulls down the files and pages you can already see, and lays everything out in folders on disk so you can study offline.

So here's what it actually does: it goes through the modules, exports pages and course info, downloads Canvas files and the direct media it can reach, and saves assignments, discussions, announcements, quizzes, and the syllabus whenever the Canvas API lets it. Nothing more than what your account can already open in a browser.

One thing to be clear about up front: this is a best-effort archive, not a full Canvas backup. It can't get around course permissions, institutional restrictions, locked content, or protected third-party streaming. If Canvas won't show it to you, this won't either.

## What it does

- Pick courses interactively, or pass `--all`, or name them with one or more `--course ID` values.
- Each module becomes a folder with its files and its exported pages inside.
- It looks for Canvas files embedded in pages, assignments, the syllabus, and discussions, not just the ones listed under Files.
- Direct media and document links get downloaded when the extension is one it supports.
- Assignments come with instructions, due dates, points, a rubric summary, and any linked resources.
- Discussions (topics and nested replies) are opt-in with `--include-discussions`, and off by default, because those posts can contain other students' data.
- Announcements, quiz metadata, and quiz question metadata come along when they're accessible.
- Course metadata and the syllabus get exported too.
- Anything it finds that doesn't belong to a module lands in `_unorganized_files`.
- There's optional support for the Canvas media-object endpoint, for institutions that have it enabled.
- A `manifest.json` tracks every file with its size and SHA-256 hash.
- Downloads are atomic (`.part` files), with retries, timeouts, pagination, filename sanitizing, and a report at the end.
- The network side is locked down: API requests are pinned to your Canvas host, the token is never sent off-host, download URLs that resolve to a private or loopback address are refused, and `--max-file-size` lets you cap how big a single file can get.
- Dry-run mode lets you look before you touch anything, and one course failing doesn't take down the rest of the run.

## What you need

- Python 3.10 or newer
- A Canvas API access token
- Permission to access the courses and files you're after

That last point isn't boilerplate. The tool uses your own token, so it can only reach what you can reach.

## Install

```bash
git clone https://github.com/aymane-amounas/Canvas-Course-Downloader.git
cd Canvas-Course-Downloader

python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e .
```

If you'd rather just grab the dependencies without installing the package:

```bash
pip install -r requirements.txt
```

## Setting up your Canvas token

In Canvas, go to **Account → Settings → New Access Token**. The exact wording changes from one institution to another, so don't be surprised if your menu looks a little different.

Then set your Canvas instance and token as environment variables.

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

If you don't set `CANVAS_API_TOKEN`, the program asks for it at the prompt and doesn't echo what you type, so it won't end up in your shell history or on screen.

A token is a password. Don't hardcode it, don't commit it, don't share it, and if it ever leaks, revoke it in Canvas right away.

## Using it

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

# Skip any single file larger than 500 MB
canvas-downloader --all --max-file-size 500

# Help and version
canvas-downloader --help
canvas-downloader --version
```

If you didn't install the console command, you can run the module directly:

```bash
python -m canvas_downloader --all
```

About `--resume`: it's there as an explicit reminder, but resuming is already the default. On every run, completed files are checked against their manifest hash and/or the file size Canvas reports, and skipped if they match. If a `.part` file was left behind by an interruption, it gets thrown away and downloaded again. I didn't implement HTTP byte-range continuation, so a half-finished file starts over rather than picking up where it stopped.

## How the output is laid out

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

The metadata files hold JSON, but they're saved with a `.txt` extension so they open cleanly anywhere without a viewer deciding to do something clever with them.

## What can actually be downloaded

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

### Where it stops

Every institution configures Canvas differently. Endpoints get disabled, content gets hidden by role or section or date, and some API responses just need permissions your token doesn't have. So there's a real list of things this won't get you:

- Kaltura, Panopto, Canvas Studio, YouTube, or any other protected stream.
- External tools or content hosted outside Canvas when there's no direct downloadable file behind them.
- Locked quizzes, unpublished content, or files your account can't open.
- Every single reply and attachment in every discussion configuration.

When something fails, it goes into `errors.txt` and `report.json`, and the rest of the course keeps exporting. I'd rather finish the parts that work than bail on the whole run because one file was locked.

## Resume and integrity

`manifest.json` records, for each file, where it was saved, its Canvas file ID when there is one, its byte size, its SHA-256 hash, and whether it finished. The manifest key is both the file identity and the destination path, which is deliberate: if the same file shows up in two modules, it gets stored in each module's folder instead of only one, because that's how you'd expect to find it later.

Downloads land in a `.part` file first and only get renamed once the transfer finishes and the size checks pass. A transfer that fails never turns into a completed manifest entry, so a half-download can't fool the next run into skipping it.

## Privacy

This part matters to me, so I'll go through it properly rather than leave it at "be careful."

Start with what you're allowed to do. Use it only with an account and courses you're authorized to access, and follow your institution's copyright, acceptable-use, and data-retention rules. The tool doesn't bypass Canvas permissions or access controls; it only reads what your account can already see.

Everything it writes stays on your machine. Nothing is uploaded, phoned home, or sent to any third party. `manifest.json` and `report.json` hold file paths, sizes, and SHA-256 hashes, and nothing else, so no token or credentials ever land in them.

The token itself gets careful handling. It's read from `CANVAS_API_TOKEN` or prompted for without echo, and it never gets written to disk, logs, the manifest, or the reports. It's sent only to your Canvas host over HTTPS. It's never attached to an off-host or redirected download URL, so embedded third-party media like CDNs or player links never sees it. On top of that, any off-host URL that resolves to a private or loopback address is refused outright, so a link planted in a course page can't be used to poke at localhost or your internal network.

Discussions are the one place where other people's data shows up, which is why `--include-discussions` is off by default. Posts and replies can carry other students' names and personal details. Leave the flag off and that content never enters the archive in the first place.

Keep in mind that the archive is just plain files. Anyone with access to the machine or your backups can read them. On a shared or managed computer, write to a location only you can read, or encrypt the output folder, and export `CANVAS_API_TOKEN` per session instead of leaving it in a shared shell profile.

Cleaning up is simple because there's no hidden state. The archive is a normal folder, so deleting the output directory removes everything, `manifest.json` and `report.json` included. There's no cache or database tucked away somewhere else. If you exported discussions and later want them gone, delete the `Discussions` folders or re-run without `--include-discussions` into a fresh output directory.

And the obvious one: never commit API tokens, downloaded course materials, student information, or private API responses. If the token is ever exposed, revoke it in Canvas.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

There are 32 tests covering filename and path safety, the Canvas client (host pinning, pagination, retries, off-host token isolation, SSRF guards), download integrity and size limits, and HTML extraction. They run against local fixtures, so you don't need a live Canvas account or any network access to work on this.

GitHub Actions runs `ruff` and the full suite on every push and pull request, against Python 3.10 through 3.13 ([tests.yml](.github/workflows/tests.yml)).

## Contributing

Issues and pull requests are welcome. A few things that make them easier to deal with:

1. Open an issue describing the bug or the feature.
2. Never attach API tokens, student information, or private course materials.
3. Add tests for behavior changes.
4. Run `pytest` and `ruff check .` before you send it.
5. Note any Canvas API permissions a change depends on.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This is an independent project. It's not affiliated with, endorsed by, or sponsored by Instructure or Canvas LMS.

---

<sub>Built by [lethebyte](https://github.com/aymane-amounas)</sub>
