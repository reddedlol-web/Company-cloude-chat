from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BossFreeArticleListItem:
    id: int
    title: str
    slug: str
    category_id: int
    sort: int = 0


@dataclass
class BossFreeArticleFull:
    id: int
    title: str
    slug: str
    category_id: int
    content: str
    updated_at: str
    category: list[dict[str, Any]] = field(default_factory=list)

    @property
    def category_path(self) -> str:
        titles = [
            str(item.get("title", "")).strip()
            for item in self.category
            if str(item.get("title", "")).strip()
        ]
        return " / ".join(titles)

    @property
    def source_url(self) -> str:
        return ""  # filled by sync with origin


@dataclass
class SyncError:
    slug: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "message": self.message}


@dataclass
class SyncReport:
    status: str
    fetched: int = 0
    written: int = 0
    skipped_unchanged: int = 0
    skipped_empty: int = 0
    errors: list[SyncError] = field(default_factory=list)
    knowledge_dir: str = "knowledge/bossfree"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "fetched": self.fetched,
            "written": self.written,
            "skipped_unchanged": self.skipped_unchanged,
            "skipped_empty": self.skipped_empty,
            "errors": [e.to_dict() for e in self.errors],
            "knowledge_dir": self.knowledge_dir,
        }
