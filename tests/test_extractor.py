from canvas_downloader.extractor import extract_embeds, html_text

BASE = "https://school.instructure.com"


def test_html_text_renders_links_and_images():
    out = html_text('<p>See <a href="/x">the notes</a></p><img alt="chart" src="/c.png">')
    assert "[the notes](/x)" in out
    assert "[Image: chart (/c.png)]" in out


def test_html_text_empty():
    assert html_text(None) == ""
    assert html_text("") == ""


def test_extract_embeds_finds_canvas_file_ids():
    ids, direct, frames = extract_embeds('<a href="/courses/1/files/987/download">f</a>', BASE)
    assert ids == {987}
    assert not direct and not frames


def test_extract_embeds_direct_media_only_known_extensions():
    markup = '<a href="https://cdn.x/clip.mp4">v</a><a href="https://cdn.x/page.html">p</a>'
    ids, direct, _frames = extract_embeds(markup, BASE)
    assert direct == {"https://cdn.x/clip.mp4"}
    assert ids == set()


def test_extract_embeds_iframe_captured_as_frame():
    _ids, _direct, frames = extract_embeds('<iframe src="https://youtube.com/embed/x"></iframe>', BASE)
    assert frames == {"https://youtube.com/embed/x"}


def test_extract_embeds_resolves_relative_against_base():
    ids, _direct, _frames = extract_embeds('<video src="/files/55/download"></video>', BASE)
    assert ids == {55}
