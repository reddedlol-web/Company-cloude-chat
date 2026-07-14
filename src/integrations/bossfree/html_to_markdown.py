from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, urlparse

from markdownify import markdownify as md


EMPTY_TEXT_THRESHOLD = 50

_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.I)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.I)
_IFRAME_SRC_RE = re.compile(
    r'<iframe[^>]+src=["\']([^"\']+)["\'][^>]*>[\s\S]*?</iframe>',
    re.I,
)
_VIDEO_SRC_RE = re.compile(
    r'<video[^>]+src=["\']([^"\']+)["\'][^>]*>[\s\S]*?</video>',
    re.I,
)


def youtube_watch_url(url: str) -> str:
    """Normalize YouTube embed/shorts URLs to a regular watch URL when possible."""
    raw = (url or "").strip()
    if not raw:
        return raw
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if "youtu.be" in host:
        video_id = parsed.path.strip("/")
        return f"https://www.youtube.com/watch?v={video_id}" if video_id else raw
    if "youtube.com" in host or "youtube-nocookie.com" in host:
        if "/embed/" in parsed.path or "/shorts/" in parsed.path:
            video_id = parsed.path.rstrip("/").split("/")[-1]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
        qs = parse_qs(parsed.query)
        if qs.get("v"):
            return f"https://www.youtube.com/watch?v={qs['v'][0]}"
    return raw


def _media_markdown_link(url: str) -> str:
    watch = youtube_watch_url(url)
    label = "Видео"
    if "youtube.com" in watch.lower() or "youtu.be" in watch.lower():
        label = "Видео (YouTube)"
    return f'<p><strong>{label}:</strong> <a href="{watch}">{watch}</a></p>'


def html_to_markdown(html: str) -> str:
    """Convert Boss Free article HTML to Markdown (images/links preserved as URLs)."""
    cleaned = _SCRIPT_RE.sub("", html or "")
    cleaned = _STYLE_RE.sub("", cleaned)
    # Prefer explicit video labels so RAG + LLM do not treat media-only posts as empty.
    cleaned = _IFRAME_SRC_RE.sub(lambda m: _media_markdown_link(m.group(1)), cleaned)
    cleaned = _VIDEO_SRC_RE.sub(lambda m: _media_markdown_link(m.group(1)), cleaned)
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
