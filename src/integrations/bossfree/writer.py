from __future__ import annotations

import re
from pathlib import Path


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def build_markdown_document(
    *,
    title: str,
    body_markdown: str,
    bossfree_id: int,
    slug: str,
    updated_at: str,
    source_url: str,
    category_path: str,
) -> str:
    # Escape YAML double quotes in strings
    def yq(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        "---",
        f"bossfree_id: {bossfree_id}",
        f'slug: "{yq(slug)}"',
        f'updated_at: "{yq(updated_at)}"',
        f'source_url: "{yq(source_url)}"',
        f'category_path: "{yq(category_path)}"',
        "---",
        "",
        f"# {title.strip()}",
        "",
        body_markdown.strip(),
        "",
    ]
    return "\n".join(lines)


def read_frontmatter_updated_at(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    for line in match.group(1).splitlines():
        if line.strip().startswith("updated_at:"):
            raw = line.split(":", 1)[1].strip().strip('"').strip("'")
            return raw
    return None


def write_markdown_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
