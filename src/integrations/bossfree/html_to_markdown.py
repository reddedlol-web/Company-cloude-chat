from __future__ import annotations

import re
from html import unescape

from markdownify import markdownify as md


EMPTY_TEXT_THRESHOLD = 50

_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.I)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.I)


def html_to_markdown(html: str) -> str:
    """Convert Boss Free article HTML to Markdown (images/links preserved as URLs)."""
    cleaned = _SCRIPT_RE.sub("", html or "")
    cleaned = _STYLE_RE.sub("", cleaned)
    # Prefer link fallback for iframes/videos so RAG keeps a URL cue.
    cleaned = re.sub(
        r'<iframe[^>]+src=["\']([^"\']+)["\'][^>]*>[\s\S]*?</iframe>',
        r'<p><a href="\1">\1</a></p>',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r'<video[^>]+src=["\']([^"\']+)["\'][^>]*>[\s\S]*?</video>',
        r'<p><a href="\1">\1</a></p>',
        cleaned,
        flags=re.I,
    )
    text = md(
        cleaned,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def plain_text_length(markdown: str) -> int:
    """Approximate visible text length (ignore markdown image/link markup noise lightly)."""
    without_images = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", markdown or "")
    without_links = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", without_images)
    plain = re.sub(r"[#*_>`~\-]+", " ", without_links)
    plain = re.sub(r"\s+", " ", plain).strip()
    return len(plain)


def is_empty_article(markdown: str, *, threshold: int = EMPTY_TEXT_THRESHOLD) -> bool:
    return plain_text_length(markdown) < threshold
