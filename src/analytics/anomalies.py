"""Rule-based anomaly detection for admin analytics."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.config import Settings
from src.db.repository import Repository


@dataclass
class AnomalyFlag:
    stats_date: str
    telegram_user_id: int | None
    anomaly_type: str
    severity: str
    description: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stats_date": self.stats_date,
            "telegram_user_id": self.telegram_user_id,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "metadata": self.metadata,
            "detected_at": datetime.now(UTC).isoformat(),
        }


class AnomalyDetector:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    def detect_for_period(
        self, start_iso: str, end_iso: str, stats_date: str
    ) -> list[AnomalyFlag]:
        flags: list[AnomalyFlag] = []
        breakdown = self.repository.get_user_period_breakdown(start_iso, end_iso)

        for row in breakdown:
            user_id = int(row["telegram_user_id"])
            total = int(row["total"])
            if total == 0:
                continue

            no_answer = int(row["no_answer_count"])
            off_topic = int(row["off_topic_count"])
            tokens = int(row["tokens_input"]) + int(row["tokens_output"])

            if (
                no_answer >= self.settings.anomaly_no_answer_count
                and no_answer / total >= self.settings.anomaly_no_answer_ratio
            ):
                flags.append(
                    AnomalyFlag(
                        stats_date=stats_date,
                        telegram_user_id=user_id,
                        anomaly_type="high_no_answer_ratio",
                        severity="warning",
                        description=(
                            f"Пользователь {user_id}: {no_answer} вопросов без ответа в БЗ "
                            f"({no_answer * 100 // total}%)"
                        ),
                        metadata={
                            "no_answer": no_answer,
                            "total": total,
                            "ratio": no_answer / total,
                        },
                    )
                )

            used = self.repository.get_usage(user_id, datetime.strptime(stats_date, "%Y-%m-%d").date())
            limit = self.settings.daily_query_limit
            if limit > 0 and used / limit >= self.settings.anomaly_limit_usage_ratio:
                flags.append(
                    AnomalyFlag(
                        stats_date=stats_date,
                        telegram_user_id=user_id,
                        anomaly_type="limit_near",
                        severity="info",
                        description=f"Пользователь {user_id}: {used}/{limit} лимита сегодня",
                        metadata={"used": used, "limit": limit},
                    )
                )

            if tokens >= self.settings.anomaly_token_user_daily:
                flags.append(
                    AnomalyFlag(
                        stats_date=stats_date,
                        telegram_user_id=user_id,
                        anomaly_type="token_spike",
                        severity="warning",
                        description=(
                            f"Пользователь {user_id}: высокий расход токенов ({tokens})"
                        ),
                        metadata={"tokens": tokens},
                    )
                )

            if off_topic >= 5 and off_topic / total >= 0.5:
                flags.append(
                    AnomalyFlag(
                        stats_date=stats_date,
                        telegram_user_id=user_id,
                        anomaly_type="off_topic_spike",
                        severity="info",
                        description=(
                            f"Пользователь {user_id}: {off_topic} оффтоп-запросов"
                        ),
                        metadata={"off_topic": off_topic, "total": total},
                    )
                )

        return flags
