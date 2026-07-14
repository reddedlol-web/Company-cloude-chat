"""Integration-style sync flow with mocked Boss Free HTTP client."""

from pathlib import Path
from unittest.mock import MagicMock

from src.config import Settings
from src.integrations.bossfree.models import BossFreeArticleFull, BossFreeArticleListItem
from src.integrations.bossfree.sync import sync_bossfree


def test_sync_flow_dry_run_counts_without_files(
    tmp_path: Path, monkeypatch
) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        KNOWLEDGE_DIR=tmp_path / "knowledge",
        BOSSFREE_EMAIL="a@b.c",
        BOSSFREE_PASSWORD="x",
    )
    article = BossFreeArticleFull(
        id=1,
        title="Demo",
        slug="demo",
        category_id=1,
        content="<p>" + ("Демо текст статьи для проверки dry-run. " * 5) + "</p>",
        updated_at="2025-01-01T00:00:00.000Z",
        category=[{"id": 1, "title": "DemoCat"}],
    )
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.list_categories.return_value = [{"id": 1, "title": "DemoCat", "category": []}]
    client.list_posts.return_value = [
        BossFreeArticleListItem(id=1, title="Demo", slug="demo", category_id=1)
    ]
    client.get_post_by_slug.return_value = article
    monkeypatch.setattr(
        "src.integrations.bossfree.sync.BossFreeClient",
        lambda **kwargs: client,
    )

    report = sync_bossfree(settings, dry_run=True)
    assert report.written == 1
    assert list((settings.knowledge_dir / "bossfree").rglob("*.md")) == []
