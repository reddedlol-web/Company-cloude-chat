"""Human-readable Russian labels for admin analytics."""

from typing import Any

BREAKDOWN_ROWS: tuple[tuple[str, str, str], ...] = (
    ("answered", "✅", "Ответ из базы"),
    ("no_answer", "❓", "Нет в базе"),
    ("off_topic", "💬", "Не по теме"),
    ("error", "⚠️", "Ошибка сервиса"),
    ("rate_limited", "🚫", "Лимит исчерпан"),
    ("unauthorized", "⛔", "Нет доступа"),
)

_STATUS_TO_CATEGORY = {
    "success": "answered",
    "no_answer": "no_answer",
    "error": "error",
    "rate_limited": "rate_limited",
    "unauthorized": "unauthorized",
}


def pct(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{part * 100 // total}%"


def normalize_category_counts(by_category: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, count in by_category.items():
        if count <= 0:
            continue
        norm = _STATUS_TO_CATEGORY.get(key, key)
        out[norm] = out.get(norm, 0) + count
    return out


def merge_breakdown(
    by_status: dict[str, int], by_category: dict[str, int]
) -> dict[str, int]:
    cats = normalize_category_counts(by_category)
    if sum(cats.values()) > 0:
        return cats

    out: dict[str, int] = {}
    for status, count in by_status.items():
        if count <= 0:
            continue
        key = _STATUS_TO_CATEGORY.get(status, status)
        out[key] = out.get(key, 0) + count
    return out


def format_token_usage(tokens_input: int, tokens_output: int) -> str:
    total = tokens_input + tokens_output
    return f"💰 Расход AI: {total:,} токенов".replace(",", " ")


def format_users_questions(unique_users: int, total_queries: int) -> str:
    if unique_users == 1:
        who = "1 сотрудник"
    elif 2 <= unique_users <= 4:
        who = f"{unique_users} сотрудника"
    else:
        who = f"{unique_users} сотрудников"

    if total_queries == 1:
        what = "1 вопрос"
    elif 2 <= total_queries <= 4:
        what = f"{total_queries} вопроса"
    else:
        what = f"{total_queries} вопросов"

    return f"👥 {who} · {what}"


def format_breakdown_lines(merged: dict[str, int], total: int) -> list[str]:
    lines: list[str] = []
    for key, icon, label in BREAKDOWN_ROWS:
        count = merged.get(key, 0)
        if count <= 0:
            continue
        lines.append(f"{icon} {label} — {count} ({pct(count, total)})")
    return lines


def format_top_sources(top_sources: list[dict[str, Any]], limit: int = 5) -> list[str]:
    if not top_sources:
        return []
    lines = ["📎 Из каких документов:"]
    for item in top_sources[:limit]:
        title = str(item.get("title", "unknown"))
        count = int(item.get("count", 0))
        lines.append(f"• {title} — {count}")
    return lines


def format_comparison(cmp_queries: str | None, cmp_tokens: str | None) -> str | None:
    parts: list[str] = []
    if cmp_queries:
        parts.append(f"вопросов {cmp_queries}")
    if cmp_tokens:
        parts.append(f"токенов {cmp_tokens}")
    if not parts:
        return None
    return f"📉 К прошлому периоду: {', '.join(parts)}"


def period_title(period_label: str) -> str:
    label = period_label.replace(", UTC", "").strip()
    if label in {"сегодня", "7 дней", "30 дней"}:
        return f"за {label}"
    return f"за {label}"
