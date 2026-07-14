"""Aggregate query metrics by period."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from src.db.repository import Repository

PeriodKind = Literal["today", "week", "month", "daily", "weekly"]


@dataclass
class PeriodRange:
    kind: str
    start: datetime
    end: datetime
    label: str

    @property
    def start_iso(self) -> str:
        return self.start.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end.isoformat()

    @property
    def start_date(self) -> str:
        return self.start.date().isoformat()

    @property
    def end_date(self) -> str:
        return (self.end - timedelta(microseconds=1)).date().isoformat()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _start_of_day(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def resolve_period(kind: PeriodKind) -> PeriodRange:
    now = _utc_now()
    today = now.date()

    if kind == "today":
        return PeriodRange(
            kind="today",
            start=_start_of_day(today),
            end=now,
            label="сегодня",
        )
    if kind == "week":
        start_day = today - timedelta(days=6)
        return PeriodRange(
            kind="week",
            start=_start_of_day(start_day),
            end=now,
            label="7 дней",
        )
    if kind == "month":
        start_day = today - timedelta(days=29)
        return PeriodRange(
            kind="month",
            start=_start_of_day(start_day),
            end=now,
            label="30 дней",
        )
    if kind == "daily":
        yesterday = today - timedelta(days=1)
        return PeriodRange(
            kind="daily",
            start=_start_of_day(yesterday),
            end=_start_of_day(today),
            label=yesterday.strftime("%d.%m.%Y"),
        )
    # weekly
    end_day = today
    start_day = today - timedelta(days=6)
    return PeriodRange(
        kind="weekly",
        start=_start_of_day(start_day),
        end=_start_of_day(end_day + timedelta(days=1)),
        label=f"{start_day.strftime('%d.%m')}–{end_day.strftime('%d.%m.%Y')}",
    )


def previous_period(period: PeriodRange) -> PeriodRange:
    duration = period.end - period.start
    prev_end = period.start
    prev_start = prev_end - duration
    return PeriodRange(
        kind=period.kind,
        start=prev_start,
        end=prev_end,
        label="предыдущий период",
    )


def pct_change(current: int, previous: int) -> str | None:
    if previous == 0:
        return None
    delta = ((current - previous) / previous) * 100
    arrow = "↑" if delta >= 0 else "↓"
    return f"{arrow}{abs(delta):.0f}%"


class AnalyticsAggregator:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def get_stats(self, period: PeriodRange) -> dict:
        stats = self.repository.get_period_stats(period.start_iso, period.end_iso)
        prev = previous_period(period)
        prev_stats = self.repository.get_period_stats(prev.start_iso, prev.end_iso)
        stats["comparison"] = {
            "queries": pct_change(stats["total_queries"], prev_stats["total_queries"]),
            "tokens": pct_change(
                stats["tokens_input"] + stats["tokens_output"],
                prev_stats["tokens_input"] + prev_stats["tokens_output"],
            ),
        }
        stats["period"] = period
        return stats

    def compute_daily_stats(self, stats_date: date) -> dict:
        start = _start_of_day(stats_date)
        end = start + timedelta(days=1)
        stats = self.repository.get_period_stats(start.isoformat(), end.isoformat())
        self.repository.upsert_daily_stats(stats_date.isoformat(), stats)
        return stats

    def backfill_daily_stats(self, days: int) -> int:
        today = _utc_now().date()
        count = 0
        for offset in range(1, days + 1):
            day = today - timedelta(days=offset)
            self.compute_daily_stats(day)
            count += 1
        return count
