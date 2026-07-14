from src.integrations.bossfree.html_to_markdown import (
    html_to_markdown,
    is_empty_article,
    plain_text_length,
)
from src.integrations.bossfree.paths import (
    category_id_paths,
    relative_md_path,
    slugify_segment,
)


def test_slugify_strips_unsafe() -> None:
    assert "/" not in slugify_segment("A/B C")
    assert slugify_segment("???") == "untitled"


def test_category_paths_nested() -> None:
    cats = [
        {
            "id": 1,
            "title": "Компания",
            "category": [
                {"id": 2, "title": "Политики", "category": []},
            ],
        }
    ]
    paths = category_id_paths(cats)
    assert paths[1][0]
    assert paths[2][-1]


def test_relative_md_path() -> None:
    paths = {10: ["company", "policies"]}
    rel = relative_md_path(category_id=10, slug="otpusk", category_paths=paths)
    assert rel.endswith("otpusk.md")
    assert rel.startswith("company/policies/")


def test_html_to_markdown_keeps_text_and_image() -> None:
    html = (
        "<p>Hello <b>world</b>. This paragraph is long enough to clear the empty threshold.</p>"
        '<img src="https://example.com/a.png" alt="shot"/>'
    )
    md = html_to_markdown(html)
    assert "Hello" in md
    assert "https://example.com/a.png" in md
    assert not is_empty_article(md)


def test_html_iframe_becomes_link() -> None:
    html = '<iframe src="https://youtube.com/embed/x"></iframe><p>Text enough for threshold here ok.</p>'
    md = html_to_markdown(html)
    assert "youtube.com" in md
    assert "Видео (YouTube):" in md
    assert "watch?v=x" in md
    assert plain_text_length(md) >= 20


def test_empty_html_detected() -> None:
    assert is_empty_article(html_to_markdown("<p></p><img src='x'/>"))
