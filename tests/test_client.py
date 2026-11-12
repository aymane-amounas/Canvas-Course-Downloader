import pytest
from conftest import FakeResponse

from canvas_downloader import client as client_mod
from canvas_downloader.client import CanvasClient
from canvas_downloader.utils import CanvasError

BASE = "https://school.instructure.com"


def make_client() -> CanvasClient:
    return CanvasClient(BASE, "tok", timeout=5, retries=3)


def test_rejects_non_http_base_url():
    with pytest.raises(ValueError):
        CanvasClient("ftp://x", "tok", 5, 1)


def test_request_refuses_foreign_host():
    c = make_client()
    with pytest.raises(CanvasError):
        c.request("GET", "https://evil.example.com/api/v1/courses")


def test_pagination_follows_link_header():
    c = make_client()
    page1 = FakeResponse(
        json_data=[{"id": 1}, {"id": 2}],
        links={"next": {"url": f"{c.api}/courses?page=2"}},
    )
    page2 = FakeResponse(json_data=[{"id": 3}], links={})
    responses = iter([page1, page2])
    c.session.request = lambda *a, **k: next(responses)

    result = c.pages(f"{c.api}/courses")
    assert [r["id"] for r in result] == [1, 2, 3]


def test_pagination_rejects_non_list():
    c = make_client()
    c.session.request = lambda *a, **k: FakeResponse(json_data={"not": "a list"})
    with pytest.raises(CanvasError):
        c.pages(f"{c.api}/courses")


def test_retry_on_429_then_success(monkeypatch):
    monkeypatch.setattr(client_mod.time, "sleep", lambda *_: None)
    c = make_client()
    responses = iter([
        FakeResponse(status_code=429, headers={"Retry-After": "1"}),
        FakeResponse(status_code=200, json_data={"ok": True}),
    ])
    c.session.request = lambda *a, **k: next(responses)

    assert c.json(f"{c.api}/courses/1") == {"ok": True}


def test_json_raises_on_invalid_body():
    c = make_client()
    c.session.request = lambda *a, **k: FakeResponse(json_data=ValueError("bad json"))
    with pytest.raises(CanvasError):
        c.json(f"{c.api}/courses/1")
