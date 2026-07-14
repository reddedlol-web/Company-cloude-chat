from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from src.config import Settings
from src.integrations.bossfree.client import BossFreeAuthError
from src.integrations.bossfree.models import BossFreeArticleFull, BossFreeArticleListItem
from src.integrations.bossfree.sync import sync_bossfree
from src.integrations.bossfree.writer import (
    build_markdown_document,
    read_frontmatter_updated_at,
    write_markdown_file,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        KNOWLEDGE_DIR=tmp_path / "knowledge",
        BOSSFREE_EMAIL="user@example.com",
        BOSSFREE_PASSWORD="secret",
        BOSSFREE_BASE_URL="https://topix.bossfree.pro/api",
        BOSSFREE_ORIGIN="https://topix.bossfree.pro",
    )


def test_writer_frontmatter_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    content = build_markdown_document(
        title="Отпуск",
        body_markdown="Текст про отпуск достаточно длинный для проверки.",
        bossfree_id=1,
        slug="otpusk",
        updated_at="2024-01-02T00:00:00.000Z",
        source_url="https://topix.bossfree.pro/post/otpusk",
        category_path="Компания / Отпуска",
    )
    write_markdown_file(path, content)
    assert read_frontmatter_updated_at(path) == "2024-01-02T00:00:00.000Z"
    assert "# Отпуск" in path.read_text(encoding="utf-8")


def test_sync_writes_and_skips_unchanged(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    article = BossFreeArticleFull(
        id=12191,
        title="Отпуск / отгул",
        slug="otpusk",
        category_id=9441,
        content="<p>" + ("Текст отпуска. " * 10) + "</p>",
        updated_at="2024-05-01T12:00:00.000Z",
        category=[{"id": 9441, "title": "Отпуска", "parent_id": 1}],
    )
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.login.return_value = None
    client.list_categories.return_value = [
        {"id": 9441, "title": "Отпуска", "category": []}
    ]
    client.list_posts.return_value = [
        BossFreeArticleListItem(id=12191, title="Отпуск", slug="otpusk", category_id=9441)
    ]
    client.get_post_by_slug.return_value = article
    monkeypatch.setattr(
        "src.integrations.bossfree.sync.BossFreeClient",
        lambda **kwargs: client,
    )

    report1 = sync_bossfree(settings)
    assert report1.written == 1
    assert report1.skipped_empty == 0
    files = list((settings.knowledge_dir / "bossfree").rglob("*.md"))
    assert len(files) == 1
    assert "Отпуск" in files[0].read_text(encoding="utf-8")

    report2 = sync_bossfree(settings)
    assert report2.written == 0
    assert report2.skipped_unchanged == 1


def test_sync_writes_short_and_media_only(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = BossFreeArticleFull(
        id=2,
        title="Empty",
        slug="empty",
        category_id=1,
        content="<p></p><img src='https://x/y.png'/>",
        updated_at="2024-01-01T00:00:00.000Z",
        category=[{"id": 1, "title": "Cat"}],
    )
    good = BossFreeArticleFull(
        id=3,
        title="Good",
        slug="good",
        category_id=1,
        content="<p>" + ("Полезный текст статьи. " * 8) + "</p>",
        updated_at="2024-01-01T00:00:00.000Z",
        category=[{"id": 1, "title": "Cat"}],
    )
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.list_categories.return_value = [{"id": 1, "title": "Cat", "category": []}]
    client.list_posts.return_value = [
        BossFreeArticleListItem(id=2, title="Empty", slug="empty", category_id=1),
        BossFreeArticleListItem(id=3, title="Good", slug="good", category_id=1),
    ]

    def get_slug(slug: str) -> BossFreeArticleFull:
        return empty if slug == "empty" else good

    client.get_post_by_slug.side_effect = get_slug
    monkeypatch.setattr(
        "src.integrations.bossfree.sync.BossFreeClient",
        lambda **kwargs: client,
    )

    report = sync_bossfree(settings)
    assert report.skipped_empty == 0
    assert report.written == 2
    files = list((settings.knowledge_dir / "bossfree").rglob("*.md"))
    assert {f.stem for f in files} == {"empty", "good"}


def test_sync_missing_credentials(tmp_path: Path) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        KNOWLEDGE_DIR=tmp_path / "knowledge",
        BOSSFREE_EMAIL=None,
        BOSSFREE_PASSWORD=None,
    )
    with pytest.raises(BossFreeAuthError):
        sync_bossfree(settings)


def test_sync_http_error_recorded(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.list_categories.return_value = [{"id": 1, "title": "Cat", "category": []}]
    client.list_posts.return_value = [
        BossFreeArticleListItem(id=9, title="X", slug="broken", category_id=1)
    ]
    request = httpx.Request("GET", "https://topix.bossfree.pro/api/common/posts/broken")
    response = httpx.Response(404, request=request)
    client.get_post_by_slug.side_effect = httpx.HTTPStatusError(
        "missing", request=request, response=response
    )
    monkeypatch.setattr(
        "src.integrations.bossfree.sync.BossFreeClient",
        lambda **kwargs: client,
    )

    report = sync_bossfree(settings)
    assert report.written == 0
    assert report.errors
    assert report.errors[0].message == "HTTP 404"
