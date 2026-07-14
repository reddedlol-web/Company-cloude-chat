from __future__ import annotations

import logging
from pathlib import Path

import httpx

from src.config import Settings
from src.integrations.bossfree.client import BossFreeAuthError, BossFreeClient
from src.integrations.bossfree.html_to_markdown import html_to_markdown, is_empty_article
from src.integrations.bossfree.models import SyncError, SyncReport
from src.integrations.bossfree.paths import category_id_paths, relative_md_path
from src.integrations.bossfree.writer import (
    build_markdown_document,
    read_frontmatter_updated_at,
    write_markdown_file,
)

logger = logging.getLogger(__name__)

# Re-export for callers / tests
__all__ = ["SyncReport", "sync_bossfree"]


def sync_bossfree(
    settings: Settings,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> SyncReport:
    email = (settings.bossfree_email or "").strip()
    password = settings.bossfree_password or ""
    if not email or not password:
        raise BossFreeAuthError(
            "BOSSFREE_EMAIL and BOSSFREE_PASSWORD are required for sync"
        )

    out_dir = settings.knowledge_dir / "bossfree"
    report = SyncReport(status="ok", knowledge_dir=str(out_dir))

    base_url = str(settings.bossfree_base_url).rstrip("/")
    origin = str(settings.bossfree_origin).rstrip("/")

    try:
        with BossFreeClient(
            base_url=base_url,
            email=email,
            password=password,
        ) as client:
            client.login()
            categories = client.list_categories()
            cat_paths = category_id_paths(categories)
            posts = client.list_posts()

            for item in posts:
                if not item.slug:
                    report.errors.append(
                        SyncError(slug=str(item.id), message="missing slug")
                    )
                    continue
                try:
                    article = client.get_post_by_slug(item.slug)
                    report.fetched += 1
                    body = html_to_markdown(article.content)
                    if is_empty_article(body):
                        report.skipped_empty += 1
                        continue

                    rel = relative_md_path(
                        category_id=article.category_id or item.category_id,
                        slug=article.slug or item.slug,
                        category_paths=cat_paths,
                    )
                    target = out_dir / rel
                    if (
                        not force
                        and article.updated_at
                        and read_frontmatter_updated_at(target) == article.updated_at
                    ):
                        report.skipped_unchanged += 1
                        continue

                    source_url = f"{origin}/post/{article.slug}"
                    category_path = article.category_path or ""
                    document = build_markdown_document(
                        title=article.title or item.title,
                        body_markdown=body,
                        bossfree_id=article.id,
                        slug=article.slug,
                        updated_at=article.updated_at,
                        source_url=source_url,
                        category_path=category_path,
                    )
                    if dry_run:
                        report.written += 1
                        continue
                    write_markdown_file(target, document)
                    report.written += 1
                except httpx.HTTPStatusError as exc:
                    report.errors.append(
                        SyncError(
                            slug=item.slug,
                            message=f"HTTP {exc.response.status_code}",
                        )
                    )
                    logger.warning("Boss Free fetch failed slug=%s status=%s", item.slug, exc.response.status_code)
                except Exception as exc:
                    report.errors.append(
                        SyncError(slug=item.slug, message=_safe_error_message(exc))
                    )
                    logger.warning("Boss Free article failed slug=%s: %s", item.slug, _safe_error_message(exc))
    except BossFreeAuthError:
        raise
    except httpx.HTTPError as exc:
        raise BossFreeAuthError(f"Boss Free request failed: {_safe_error_message(exc)}") from exc

    if report.errors and (report.written + report.skipped_unchanged + report.skipped_empty) == 0:
        report.status = "error"
    elif report.errors:
        report.status = "partial"
    return report


def _safe_error_message(exc: BaseException) -> str:
    text = str(exc)
    # Never echo potential tokens/cookies from raw exceptions into report JSON.
    lowered = text.lower()
    for needle in ("bear", "token", "cookie", "password", "authorization"):
        if needle in lowered:
            return exc.__class__.__name__
    return text[:200]
