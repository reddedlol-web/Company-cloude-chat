"""Build and deliver analytics reports."""

import logging
from dataclasses import dataclass
from typing import Any

from httpx import HTTPError

from src.analytics.aggregator import AnalyticsAggregator, PeriodRange, resolve_period
from src.analytics.anomalies import AnomalyDetector
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
                stats_snapshot=stats,
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
                stats_snapshot=stats,
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
            stats_snapshot=stats,
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

        by_status = period_stats["by_status"]
        status_line = " ".join(
            f"{'✅' if s == 'success' else '❓' if s == 'no_answer' else '🚫' if s == 'rate_limited' else '⚠️'}{by_status[s]}"
            for s in sorted(by_status)
        )
        top = period_stats["top_sources"]
        top_line = "\n".join(f"• {t} ({c})" for t, c in top) if top else "—"

        lines = [
            f"👤 Пользователь {user_id}",
            "",
            f"Сегодня: {today_stats['total_queries']} запросов, "
            f"{today_stats['tokens_input'] + today_stats['tokens_output']} токенов",
            f"За {period.label}: {period_stats['total_queries']} запросов, "
            f"{period_stats['tokens_input'] + period_stats['tokens_output']} токенов",
            "",
            f"Статусы ({period.label}): {status_line or '—'}",
            f"Топ источников:\n{top_line}",
        ]

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
        by_status = stats["by_status"]
        success = by_status.get("success", 0)
        no_answer = by_status.get("no_answer", 0)
        rate_limited = by_status.get("rate_limited", 0)
        errors = by_status.get("error", 0)

        cmp_q = stats.get("comparison", {}).get("queries")
        cmp_suffix = f" ({cmp_q} к прошлому периоду)" if cmp_q else ""

        lines = [
            f"📊 Сводка за {period.label}",
            "",
            f"Запросы: {total}{cmp_suffix}",
            f"Пользователи: {stats['unique_users']} активных",
            f"Токены: {stats['tokens_input']:,} in / {stats['tokens_output']:,} out",
            "",
            "Статусы:",
            f"✅ Ответ из базы: {success} ({self._pct(success, total)})",
            f"❓ Нет в базе: {no_answer} ({self._pct(no_answer, total)})",
            f"🚫 Лимит: {rate_limited} | ⚠️ Ошибки: {errors}",
        ]

        by_cat = stats.get("by_category", {})
        if by_cat.get("off_topic"):
            lines.append(f"💬 Оффтоп: {by_cat['off_topic']}")

        top = stats.get("top_sources", [])[:5]
        if top:
            lines.append("\nТоп источников:")
            for item in top:
                lines.append(f"• {item['title']} — {item['count']}")

        if anomalies:
            lines.append("\n⚠️ Внимание:")
            for a in anomalies[:5]:
                lines.append(f"• {a.description}")

        return "\n".join(lines)

    def _format_stats(self, stats: dict[str, Any], anomalies: list) -> str:
        period: PeriodRange = stats["period"]
        total = stats["total_queries"]
        by_status = stats["by_status"]
        success = by_status.get("success", 0)
        no_answer = by_status.get("no_answer", 0)

        lines = [
            f"📈 Статистика ({period.label})",
            "",
            f"Запросы: {total}",
            f"Активных пользователей: {stats['unique_users']}",
            f"Токены: {stats['tokens_input']:,} in / {stats['tokens_output']:,} out",
            "",
            "По статусам:",
        ]
        for status, cnt in sorted(by_status.items()):
            pct = self._pct(cnt, total)
            icon = {"success": "✅", "no_answer": "❓", "rate_limited": "🚫", "error": "⚠️"}.get(
                status, "•"
            )
            lines.append(f"{icon} {status}: {cnt} ({pct})")

        by_cat = stats.get("by_category", {})
        if by_cat:
            cat_line = " | ".join(f"{k}: {v}" for k, v in sorted(by_cat.items()))
            lines.append(f"\nПо категориям:\n{cat_line}")

        top = stats.get("top_sources", [])[:3]
        if top:
            lines.append("\nТоп источников:")
            for item in top:
                lines.append(f"• {item['title']} — {item['count']}")

        cmp_q = stats.get("comparison", {}).get("queries")
        cmp_t = stats.get("comparison", {}).get("tokens")
        if cmp_q or cmp_t:
            parts = []
            if cmp_q:
                parts.append(f"запросы {cmp_q}")
            if cmp_t:
                parts.append(f"токены {cmp_t}")
            lines.append(f"\nСравнение с прошлым периодом: {', '.join(parts)}")

        if anomalies:
            lines.append("\n⚠️ Внимание:")
            for a in anomalies[:3]:
                lines.append(f"• {a.description}")

        return "\n".join(lines)

    @staticmethod
    def _pct(part: int, total: int) -> str:
        if total == 0:
            return "0%"
        return f"{part * 100 // total}%"


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
