SYSTEM_PROMPT = """You are a corporate knowledge assistant. Answer ONLY based on the provided context.
If the context does not contain the answer, say "В предоставленных документах нет информации по этому вопросу."
Do not invent facts. Respond in the same language as the user's question.

If the most relevant document is mainly a video or media link (for example lines like "Видео:" / "Видео (YouTube):" / youtube.com / embed), that IS an answer: tell the user that the instruction is in a video, give the clickable video URL from the context, and mention the source title. Do NOT say there is no information just because there is no written step-by-step text.

When the context contains a numbered or bulleted list (values, rules, steps, items), include EVERY item from that list in the answer — do not stop halfway.
Be complete but concise. Prefer the most relevant source document when several overlap.
Cite source document titles when answering."""


def build_user_prompt(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return f"Context:\n---\n(no context)\n---\n\nUser question: {question}"

    parts = []
    for chunk in chunks:
        title = str(chunk.get("title") or "unknown")
        url = str(chunk.get("source_url") or "").strip()
        header = f"[Source: {title}]"
        if url:
            header = f"[Source: {title} | URL: {url}]"
        parts.append(f"{header}\n{chunk.get('content', '')}\n---")
    context_block = "\n".join(parts)
    return f"Context:\n---\n{context_block}\n\nUser question: {question}"


def format_sources_html(chunks: list[dict]) -> str:
    """Deduped Telegram-HTML source line with clickable URLs when available."""
    from html import escape

    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        title = str(chunk.get("title") or "").strip() or "unknown"
        url = str(chunk.get("source_url") or "").strip()
        key = title.casefold()
        if key in seen:
            # Prefer filling URL if an earlier entry lacked it
            if url:
                for i, (t, u) in enumerate(ordered):
                    if t.casefold() == key and not u:
                        ordered[i] = (t, url)
            continue
        seen.add(key)
        ordered.append((title, url))

    rendered: list[str] = []
    for title, url in ordered:
        safe_title = escape(title)
        if url.startswith(("http://", "https://")):
            rendered.append(f'<a href="{escape(url, quote=True)}">{safe_title}</a>')
        else:
            rendered.append(safe_title)
    return "📎 Источники: " + ", ".join(rendered)
