"""HTML→Markdown unit tests (subset also in test_bossfree_paths for convenience)."""

from src.integrations.bossfree.html_to_markdown import html_to_markdown, is_empty_article


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
