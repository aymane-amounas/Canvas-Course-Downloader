import json
from pathlib import Path

from conftest import FakeResponse

from canvas_downloader.downloader import DownloadManager


class FakeClient:
    def __init__(self, chunks, headers=None):
        self._chunks = chunks
        self._headers = headers or {}

    def download(self, url):
        return FakeResponse(chunks=list(self._chunks), headers=dict(self._headers))


def test_download_writes_file_and_manifest(tmp_path: Path):
    client = FakeClient([b"hello ", b"world"])
    mgr = DownloadManager(client, tmp_path, dry_run=False)
    mgr.save_bytes_from_url("Course", "Mod", "a.txt", "http://x/a", file_id=1, expected_size=11)

    dest = tmp_path / "Course" / "Mod" / "a.txt"
    assert dest.read_bytes() == b"hello world"
    assert mgr.stats["downloaded"] == 1
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert any(v["path"] == "Course/Mod/a.txt" for v in manifest["downloads"].values())


def test_interrupted_size_mismatch_is_failure(tmp_path: Path):
    client = FakeClient([b"short"])
    mgr = DownloadManager(client, tmp_path, dry_run=False)
    mgr.save_bytes_from_url("Course", "Mod", "a.txt", "http://x/a", file_id=1, expected_size=999)

    assert mgr.stats["failed"] == 1
    assert mgr.stats["downloaded"] == 0
    assert not (tmp_path / "Course" / "Mod" / "a.txt").exists()
    assert not (tmp_path / "Course" / "Mod" / "a.txt.part").exists()


def test_resume_skips_completed_file(tmp_path: Path):
    client = FakeClient([b"data"])
    first = DownloadManager(client, tmp_path, dry_run=False)
    first.save_bytes_from_url("C", "M", "f.bin", "http://x/f", file_id=7, expected_size=4)
    assert first.stats["downloaded"] == 1

    second = DownloadManager(client, tmp_path, dry_run=False)
    second.save_bytes_from_url("C", "M", "f.bin", "http://x/f", file_id=7, expected_size=4)
    assert second.stats["skipped"] == 1
    assert second.stats["downloaded"] == 0


def test_dry_run_writes_nothing(tmp_path: Path):
    client = FakeClient([b"data"])
    mgr = DownloadManager(client, tmp_path, dry_run=True)
    mgr.save_bytes_from_url("C", "M", "f.bin", "http://x/f", file_id=7)

    assert mgr.stats["planned"] == 1
    assert not (tmp_path / "C").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_save_text_writes_then_skips(tmp_path: Path):
    client = FakeClient([])
    mgr = DownloadManager(client, tmp_path, dry_run=False)
    mgr.save_text("C", "Info", "Notes", "line one")
    assert (tmp_path / "C" / "Info" / "Notes.txt").read_text() == "line one"
    assert mgr.stats["downloaded"] == 1

    again = DownloadManager(client, tmp_path, dry_run=False)
    again.save_text("C", "Info", "Notes", "line one")
    assert again.stats["skipped"] == 1
