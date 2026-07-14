"""User-facing datetime formatting."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def to_msk(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(MSK)


def format_msk(dt: datetime | None = None) -> str:
    """Format as DD.MM.YYYY HH:MM MSK."""
    return to_msk(dt or datetime.now(UTC)).strftime("%d.%m.%Y %H:%M MSK")


def format_msk_date(dt: datetime) -> str:
    return to_msk(dt).strftime("%d.%m.%Y")
