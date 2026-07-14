from __future__ import annotations

import re
import unicodedata
from typing import Any


_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify_segment(value: str, *, fallback: str = "untitled") -> str:
    """Make a filesystem-safe path segment from a title or slug."""
    text = unicodedata.normalize("NFKC", (value or "").strip())
    text = text.replace("/", "-").replace("\\", "-")
    text = _SAFE_SEGMENT.sub("-", text)
    text = re.sub(r"-{2,}", "-", text).strip(".-_")
    if not text:
        return fallback
    return text[:120]


def category_id_paths(categories: list[dict[str, Any]]) -> dict[int, list[str]]:
    """Map category id → list of sanitized title segments from root to node."""
    result: dict[int, list[str]] = {}

    def walk(nodes: list[dict[str, Any]], parents: list[str]) -> None:
        for node in nodes:
            cid = int(node["id"])
            segment = slugify_segment(str(node.get("title") or cid), fallback=str(cid))
            path = [*parents, segment]
            result[cid] = path
            children = node.get("category") or []
            if isinstance(children, list) and children:
                walk(children, path)

    walk(categories, [])
    return result


def relative_md_path(
    *,
    category_id: int,
    slug: str,
    category_paths: dict[int, list[str]],
) -> str:
    segments = category_paths.get(category_id) or ["uncategorized"]
    filename = slugify_segment(slug, fallback=f"post-{category_id}") + ".md"
    return "/".join([*segments, filename])
