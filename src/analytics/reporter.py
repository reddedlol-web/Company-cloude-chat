"""Build and deliver analytics reports."""

import logging
from dataclasses import dataclass
from typing import Any

from httpx import HTTPError

from src.analytics.aggregator import AnalyticsAggregator, PeriodRange, resolve_period
from src.analytics.anomalies import AnomalyDetector
from src.analytics.formatting import (
    format_breakdown_lines,
    format_comparison,
    format_token_usage,
    format_top_sources,
    format_users_questions,
    merge_breakdown,
    pct,
    period_title,
)
from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """Ты аналитик корпоративного Telegram-бота с базой знаний.
Сгруппируй вопросы сотрудников в 3–7 тем (на русском). Дай 1–2 практические рекомендации админу.
Не перечисляй каждый вопрос отдельно. Кратко, по делу."""


@dataclass
class ReportResult:
    messages: list[str]
    report_id: int | None
    llm_tokens_used: int
    skipped_llm: bool


class AnalyticsReporter:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        llm: OpenRouterClient | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.aggregator = AnalyticsAggregator(repository)
        self.anomaly_detector = AnomalyDetector(settings, repository)
        self.llm = llm

    async def generate_report(
        self,
        period_kind: str,
        *,
        numeric_only: bool = False,
        force: bool = False,
    ) -> ReportResult:
        period = resolve_period(period_kind)  # type: ignore[arg-type]
        period_type = "daily" if period.kind == "daily" else "weekly"

        if not force and self.repository.report_exists(period_type, period.start_date):
            existing_msg = (
                f"ℹ️ Сводка за {period.label} уже отправлялась. "
                "Повтор: /report {0} --force".format(period_kind)
            )
            return ReportResult([existing_msg], None, 0, True)

        stats = self.aggregator.get_stats(period)
        total = stats["total_queries"]

        if total == 0:
            text = f"📭 За период ({period.label}) запросов не было."
            report_id = self.repository.save_analytics_report(
                period_type=period_type,
                period_start=period.start_date,
                period_end=period.end_date,
                summary_text=text,
                stats_snapshot=self._stats_snapshot(stats),
                delivery_status="skipped_empty",
            )
            return ReportResult([text], report_id, 0, True)

        if total <= 2:
            text = self._format_numeric_report(stats, anomalies=[])
            report_id = self.repository.save_analytics_report(
                period_type=period_type,
                period_start=period.start_date,
                period_end=period.end_date,
                summary_text=text,
                stats_snapshot=self._stats_snapshot(stats),
                delivery_status="pending",
            )
            return ReportResult(split_telegram_messages(text), report_id, 0, True)

        anomalies = self.anomaly_detector.detect_for_period(
            period.start_iso, period.end_iso, period.end_date
        )
        anomaly_dicts = [a.to_dict() for a in anomalies]
        if anomaly_dicts:
            self.repository.insert_anomaly_flags(anomaly_dicts)

        llm_tokens = 0
        insights = ""
        if not numeric_only and self.llm and total >= 3:
            try:
                insights, llm_tokens = await self._llm_insights(period)
            except HTTPError:
                logger.exception("LLM summary failed; using numeric fallback")
                insights = "\n\n⚠️ Тематический анализ недоступен."

        body = self._format_numeric_report(stats, anomalies)
        if insights:
            body = f"{body}\n\n{insights.strip()}"

        body += "\n\n/stats week — детали | /userstats <id> — по человеку"

        report_id = self.repository.save_analytics_report(
            period_type=period_type,
            period_start=period.start_date,
            period_end=period.end_date,
            summary_text=body,
            stats_snapshot=self._stats_snapshot(stats),
            anomalies=anomaly_dicts,
            llm_tokens_used=llm_tokens,
            delivery_status="pending",
        )
        return ReportResult(
            split_telegram_messages(body),
            report_id,
            llm_tokens,
            numeric_only or self.llm is None,
        )

    async def _llm_insights(self, period: PeriodRange) -> tuple[str, int]:
        questions = self.repository.get_questions_for_period(
            period.start_iso, period.end_iso, limit=50
        )
        lines = []
        for i, q in enumerate(questions, 1):
            text = (q.get("question_text") or "")[:120]
            cat = q.get("category", "")
            lines.append(f"{i}. [{cat}] {text}")

        user_prompt = (
            f"Период: {period.label}\n"
            f"Вопросов: {len(questions)}\n\n"
            "Список вопросов (усечённо):\n"
            + "\n".join(lines)
            + "\n\nСгруппируй в темы и дай рекомендации."
        )
        result = await self.llm.chat(  # type: ignore[union-attr]
            SUMMARY_SYSTEM_PROMPT,
            user_prompt,
            model=self.settings.effective_summary_model,
            max_tokens=self.settings.analytics_report_max_llm_tokens,
        )
        block = (
            "Темы (сгруппировано):\n"
            f"{result.content}\n\n"
            "💡 См. рекомендации выше."
        )
        return block, result.tokens_output

    def format_stats_message(self, period_kind: str) -> str:
        period = resolve_period(period_kind)  # type: ignore[arg-type]
        stats = self.aggregator.get_stats(period)
        if stats["total_queries"] == 0:
            return "📭 За выбранный период запросов не было."

        anomalies = self.anomaly_detector.detect_for_period(
            period.start_iso, period.end_iso, period.end_date
        )
        return self._format_stats(stats, anomalies)

    def format_userstats_message(self, user_id: int, period_kind: str = "week") -> str:
        period = resolve_period(period_kind)  # type: ignore[arg-type]
        today = resolve_period("today")
        today_stats = self.repository.get_user_stats(
            user_id, today.start_iso, today.end_iso
        )
        period_stats = self.repository.get_user_stats(
            user_id, period.start_iso, period.end_iso
        )

        if period_stats["total_queries"] == 0 and today_stats["total_queries"] == 0:
            return "Активности нет за выбранный период."

        period_merged = merge_breakdown(period_stats["by_status"], {})
        breakdown = format_breakdown_lines(
            period_merged, max(period_stats["total_queries"], 1)
        )
        top_lines = format_top_sources(
            [{"title": t, "count": c} for t, c in period_stats["top_sources"]]
        )
        today_tok = today_stats["tokens_input"] + today_stats["tokens_output"]
        period_tok = period_stats["tokens_input"] + period_stats["tokens_output"]

        lines = [
            f"👤 Сотрудник {user_id}",
            "",
            f"Сегодня: {today_stats['total_queries']} вопр. · {today_tok:,} токенов".replace(",", " "),
            f"За {period.label}: {period_stats['total_queries']} вопр. · {period_tok:,} токенов".replace(",", " "),
            "",
            "Как отвечал бот:",
            *breakdown,
        ]

        if top_lines:
            lines.append("")
            lines.extend(top_lines)

        if self.settings.analytics_store_questions:
            recent = self.repository.get_recent_questions(user_id, limit=5)
            if recent:
                lines.append("\nПоследние вопросы:")
                for i, row in enumerate(recent, 1):
                    text = row["question_text"]
                    preview = text[:80] + ("…" if len(text) > 80 else "")
                    lines.append(f"{i}. {preview}")
        else:
            lines.append("\n(Тексты вопросов скрыты: ANALYTICS_STORE_QUESTIONS=false)")

        return "\n".join(lines)

    def _format_numeric_report(
        self, stats: dict[str, Any], anomalies: list
    ) -> str:
        period: PeriodRange = stats["period"]
        total = stats["total_queries"]
        merged = merge_breakdown(stats["by_status"], stats.get("by_category", {}))

        cmp_q = stats.get("comparison", {}).get("queries")
        cmp_suffix = f" ({cmp_q} к прошлому периоду)" if cmp_q else ""

        lines = [
            f"📊 Сводка {period_title(period.label)}",
            "",
            format_users_questions(stats["unique_users"], total) + cmp_suffix,
            format_token_usage(stats["tokens_input"], stats["tokens_output"]),
            "",
            "Как отвечал бот:",
            *format_breakdown_lines(merged, total),
        ]

        top_lines = format_top_sources(stats.get("top_sources", []), limit=5)
        if top_lines:
            lines.append("")
            lines.extend(top_lines)

        if anomalies:
            lines.append("\n⚠️ На что обратить внимание:")
            for a in anomalies[:5]:
                lines.append(f"• {a.description}")

        return "\n".join(lines)

    def _format_stats(self, stats: dict[str, Any], anomalies: list) -> str:
        period: PeriodRange = stats["period"]
        total = stats["total_queries"]
        merged = merge_breakdown(stats["by_status"], stats.get("by_category", {}))

        lines = [
            f"📈 Статистика {period_title(period.label)}",
            "",
            format_users_questions(stats["unique_users"], total),
            format_token_usage(stats["tokens_input"], stats["tokens_output"]),
            "",
            "Как отвечал бот:",
            *format_breakdown_lines(merged, total),
        ]

        top_lines = format_top_sources(stats.get("top_sources", []), limit=5)
        if top_lines:
            lines.append("")
            lines.extend(top_lines)

        cmp_line = format_comparison(
            stats.get("comparison", {}).get("queries"),
            stats.get("comparison", {}).get("tokens"),
        )
        if cmp_line:
            lines.append("")
            lines.append(cmp_line)

        if anomalies:
            lines.append("\n⚠️ На что обратить внимание:")
            for a in anomalies[:3]:
                lines.append(f"• {a.description}")

        return "\n".join(lines)

    @staticmethod
    def _pct(part: int, total: int) -> str:
        return pct(part, total)

    @staticmethod
    def _stats_snapshot(stats: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(stats)
        period = snapshot.pop("period", None)
        if period is not None:
            snapshot["period"] = {
                "kind": period.kind,
                "start": period.start.isoformat(),
                "end": period.end.isoformat(),
                "label": period.label,
            }
        return snapshot


def split_telegram_messages(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                parts.append(current)
            while len(block) > limit:
                parts.append(block[:limit])
                block = block[limit:]
            current = block
    if current:
        parts.append(current)
    return parts[:3]
