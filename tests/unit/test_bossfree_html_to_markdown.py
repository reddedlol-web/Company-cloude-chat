"""HTML→Markdown unit tests (subset also in test_bossfree_paths for convenience)."""

from src.integrations.bossfree.html_to_markdown import (
    html_to_markdown,
    is_empty_article,
    youtube_watch_url,
)
from src.rag.prompts import SYSTEM_PROMPT


def test_lists_preserved() -> None:
    html = (
        "<ul><li>One</li><li>Two</li></ul>"
        "<p>Extra explanatory sentence for length that exceeds fifty characters clearly.</p>"
    )
    md = html_to_markdown(html)
    assert "One" in md
    assert "Two" in md
    assert not is_empty_article(md)


def test_video_tag_to_link() -> None:
    html = (
        '<video src="https://cdn.example/v.mp4"></video>'
        "<p>Enough text body to pass empty threshold for the article.</p>"
    )
    md = html_to_markdown(html)
    assert "cdn.example/v.mp4" in md
    assert "Видео:" in md


def test_youtube_iframe_labeled_as_video() -> None:
    html = (
        '<p><iframe frameborder="0" height="360" '
        'src="https://www.youtube.com/embed/hNu0IfefQ_0?rel=0" width="640"></iframe></p>'
    )
    md = html_to_markdown(html)
    assert "Видео (YouTube):" in md
    assert "https://www.youtube.com/watch?v=hNu0IfefQ_0" in md
    assert "embed" not in md


def test_youtube_watch_url_normalizes_embed() -> None:
    assert (
        youtube_watch_url("https://www.youtube.com/embed/abc123?rel=0")
        == "https://www.youtube.com/watch?v=abc123"
    )


def test_system_prompt_treats_video_as_answer() -> None:
    assert "Видео" in SYSTEM_PROMPT
    assert "Do NOT say there is no information" in SYSTEM_PROMPT
