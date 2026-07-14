import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from src.db.models import SCHEMA_SQL


class Repository:
    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def upsert_document(
        self,
        *,
        doc_id: str,
        file_path: str,
        title: str,
        fmt: str,
        file_hash: str,
        chunk_count: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, file_path, title, format, file_hash, chunk_count,
                    status, indexed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    file_path=excluded.file_path,
                    title=excluded.title,
                    format=excluded.format,
                    file_hash=excluded.file_hash,
                    chunk_count=excluded.chunk_count,
                    status=excluded.status,
                    indexed_at=excluded.indexed_at,
                    error_message=excluded.error_message
                """,
                (
                    doc_id,
                    file_path,
                    title,
                    fmt,
                    file_hash,
                    chunk_count,
                    status,
                    now if status == "active" else None,
                    error_message,
                ),
            )

    def list_document_paths(self) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT file_path FROM documents").fetchall()
        return {row["file_path"] for row in rows}

    def delete_documents_not_in(self, paths: set[str]) -> list[str]:
        existing = self.list_document_paths()
        to_delete = existing - paths
        if not to_delete:
            return []
        with self.connect() as conn:
            conn.executemany(
                "DELETE FROM documents WHERE file_path = ?",
                [(path,) for path in to_delete],
            )
        return sorted(to_delete)

    def get_index_status(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_documents,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
                    COALESCE(SUM(chunk_count), 0) AS total_chunks,
                    MAX(indexed_at) AS last_reindex_at
                FROM documents
                """
            ).fetchone()
        return dict(row) if row else {}

    def get_usage(self, user_id: int, usage_date: date | None = None) -> int:
        day = (usage_date or datetime.now(UTC).date()).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT query_count FROM daily_usage
                WHERE telegram_user_id = ? AND usage_date = ?
                """,
                (user_id, day),
            ).fetchone()
        return int(row["query_count"]) if row else 0

    def increment_usage(self, user_id: int) -> int:
        day = datetime.now(UTC).date().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_usage (telegram_user_id, usage_date, query_count)
                VALUES (?, ?, 1)
                ON CONFLICT(telegram_user_id, usage_date) DO UPDATE SET
                    query_count = query_count + 1
                """,
                (user_id, day),
            )
            row = conn.execute(
                """
                SELECT query_count FROM daily_usage
                WHERE telegram_user_id = ? AND usage_date = ?
                """,
                (user_id, day),
            ).fetchone()
        return int(row["query_count"])

    def check_quota(self, user_id: int, limit: int) -> tuple[bool, int, int]:
        used = self.get_usage(user_id)
        remaining = max(0, limit - used)
        return used < limit, used, remaining

    def log_query(
        self,
        *,
        user_id: int,
        status: str,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        sources: list[str] | None = None,
        latency_ms: int | None = None,
        question_length: int | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO query_logs (
                    telegram_user_id, timestamp, status, tokens_input, tokens_output,
                    sources_cited, latency_ms, question_length
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    datetime.now(UTC).isoformat(),
                    status,
                    tokens_input,
                    tokens_output,
                    json.dumps(sources or [], ensure_ascii=False),
                    latency_ms,
                    question_length,
                ),
            )
            return int(cursor.lastrowid)

    def record_query_detail(
        self,
        *,
        query_log_id: int,
        question_text: str | None,
        question_hash: str,
        category: str,
        max_similarity: float | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO query_details (
                    query_log_id, question_text, question_hash, category, max_similarity
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(query_log_id) DO UPDATE SET
                    question_text=excluded.question_text,
                    question_hash=excluded.question_hash,
                    category=excluded.category,
                    max_similarity=excluded.max_similarity
                """,
                (query_log_id, question_text, question_hash, category, max_similarity),
            )

    def get_period_stats(
        self, start_iso: str, end_iso: str
    ) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT ql.status, ql.tokens_input, ql.tokens_output,
                       ql.sources_cited, ql.telegram_user_id,
                       COALESCE(qd.category, ql.status) AS category
                FROM query_logs ql
                LEFT JOIN query_details qd ON qd.query_log_id = ql.id
                WHERE ql.timestamp >= ? AND ql.timestamp < ?
                """,
                (start_iso, end_iso),
            ).fetchall()

        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        user_ids: set[int] = set()
        tokens_input = 0
        tokens_output = 0

        for row in rows:
            status = row["status"]
            category = row["category"]
            by_status[status] = by_status.get(status, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
            user_ids.add(int(row["telegram_user_id"]))
            tokens_input += int(row["tokens_input"] or 0)
            tokens_output += int(row["tokens_output"] or 0)
            try:
                sources = json.loads(row["sources_cited"] or "[]")
            except json.JSONDecodeError:
                sources = []
            for source in sources:
                source_counts[str(source)] = source_counts.get(str(source), 0) + 1

        top_sources = sorted(
            [{"title": k, "count": v} for k, v in source_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:10]

        return {
            "total_queries": len(rows),
            "unique_users": len(user_ids),
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "by_status": by_status,
            "by_category": by_category,
            "top_sources": top_sources,
        }

    def get_user_period_breakdown(
        self, start_iso: str, end_iso: str
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT ql.telegram_user_id,
                       COUNT(*) AS total,
                       SUM(CASE WHEN COALESCE(qd.category, ql.status) = 'no_answer'
                           THEN 1 ELSE 0 END) AS no_answer_count,
                       SUM(CASE WHEN COALESCE(qd.category, ql.status) = 'off_topic'
                           THEN 1 ELSE 0 END) AS off_topic_count,
                       COALESCE(SUM(ql.tokens_input), 0) AS tokens_input,
                       COALESCE(SUM(ql.tokens_output), 0) AS tokens_output
                FROM query_logs ql
                LEFT JOIN query_details qd ON qd.query_log_id = ql.id
                WHERE ql.timestamp >= ? AND ql.timestamp < ?
                GROUP BY ql.telegram_user_id
                """,
                (start_iso, end_iso),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_daily_stats(self, stats_date: str, stats: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_stats (
                    stats_date, total_queries, unique_users, tokens_input, tokens_output,
                    by_status, by_category, top_sources, computed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stats_date) DO UPDATE SET
                    total_queries=excluded.total_queries,
                    unique_users=excluded.unique_users,
                    tokens_input=excluded.tokens_input,
                    tokens_output=excluded.tokens_output,
                    by_status=excluded.by_status,
                    by_category=excluded.by_category,
                    top_sources=excluded.top_sources,
                    computed_at=excluded.computed_at
                """,
                (
                    stats_date,
                    stats["total_queries"],
                    stats["unique_users"],
                    stats["tokens_input"],
                    stats["tokens_output"],
                    json.dumps(stats["by_status"], ensure_ascii=False),
                    json.dumps(stats["by_category"], ensure_ascii=False),
                    json.dumps(stats["top_sources"], ensure_ascii=False),
                    now,
                ),
            )

    def get_daily_stats_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM daily_stats
                WHERE stats_date >= ? AND stats_date <= ?
                ORDER BY stats_date
                """,
                (start_date, end_date),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["by_status"] = json.loads(item["by_status"])
            item["by_category"] = json.loads(item["by_category"])
            item["top_sources"] = json.loads(item["top_sources"])
            result.append(item)
        return result

    def report_exists(self, period_type: str, period_start: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM analytics_reports
                WHERE period_type = ? AND period_start = ? AND delivery_status = 'sent'
                """,
                (period_type, period_start),
            ).fetchone()
        return row is not None

    def save_analytics_report(
        self,
        *,
        period_type: str,
        period_start: str,
        period_end: str,
        summary_text: str,
        stats_snapshot: dict[str, Any],
        anomalies: list[dict[str, Any]] | None = None,
        llm_tokens_used: int | None = None,
        delivery_status: str = "pending",
    ) -> int:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analytics_reports (
                    period_type, period_start, period_end, generated_at,
                    summary_text, anomalies_json, stats_snapshot, llm_tokens_used,
                    delivery_status, delivered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    period_type,
                    period_start,
                    period_end,
                    now,
                    summary_text,
                    json.dumps(anomalies or [], ensure_ascii=False),
                    json.dumps(stats_snapshot, ensure_ascii=False),
                    llm_tokens_used,
                    delivery_status,
                    now if delivery_status == "sent" else None,
                ),
            )
            return int(cursor.lastrowid)

    def mark_report_sent(self, report_id: int) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE analytics_reports
                SET delivery_status = 'sent', delivered_at = ?
                WHERE id = ?
                """,
                (now, report_id),
            )

    def insert_anomaly_flags(self, flags: list[dict[str, Any]]) -> None:
        if not flags:
            return
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO anomaly_flags (
                    detected_at, stats_date, telegram_user_id, anomaly_type,
                    severity, description, metadata_json, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                [
                    (
                        flag.get("detected_at", now),
                        flag["stats_date"],
                        flag.get("telegram_user_id"),
                        flag["anomaly_type"],
                        flag["severity"],
                        flag["description"],
                        json.dumps(flag.get("metadata", {}), ensure_ascii=False),
                    )
                    for flag in flags
                ],
            )

    def get_anomalies_for_period(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM anomaly_flags
                WHERE stats_date >= ? AND stats_date <= ?
                ORDER BY detected_at DESC
                """,
                (start_date, end_date),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_questions_for_period(
        self, start_iso: str, end_iso: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT ql.telegram_user_id, qd.question_text, qd.category, ql.timestamp
                FROM query_logs ql
                JOIN query_details qd ON qd.query_log_id = ql.id
                WHERE ql.timestamp >= ? AND ql.timestamp < ?
                  AND qd.question_text IS NOT NULL
                ORDER BY ql.timestamp DESC
                LIMIT ?
                """,
                (start_iso, end_iso, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_user_stats(
        self, user_id: int, start_iso: str, end_iso: str
    ) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(ql.tokens_input), 0) AS tokens_input,
                       COALESCE(SUM(ql.tokens_output), 0) AS tokens_output
                FROM query_logs ql
                WHERE ql.telegram_user_id = ? AND ql.timestamp >= ? AND ql.timestamp < ?
                """,
                (user_id, start_iso, end_iso),
            ).fetchone()
            status_rows = conn.execute(
                """
                SELECT ql.status, COUNT(*) AS cnt
                FROM query_logs ql
                WHERE ql.telegram_user_id = ? AND ql.timestamp >= ? AND ql.timestamp < ?
                GROUP BY ql.status
                """,
                (user_id, start_iso, end_iso),
            ).fetchall()
            source_rows = conn.execute(
                """
                SELECT ql.sources_cited
                FROM query_logs ql
                WHERE ql.telegram_user_id = ? AND ql.timestamp >= ? AND ql.timestamp < ?
                  AND ql.sources_cited IS NOT NULL
                """,
                (user_id, start_iso, end_iso),
            ).fetchall()

        by_status = {r["status"]: int(r["cnt"]) for r in status_rows}
        source_counts: dict[str, int] = {}
        for source_row in source_rows:
            try:
                sources = json.loads(source_row["sources_cited"] or "[]")
            except json.JSONDecodeError:
                sources = []
            for source in sources:
                source_counts[str(source)] = source_counts.get(str(source), 0) + 1

        top_sources = sorted(
            source_counts.items(), key=lambda item: item[1], reverse=True
        )[:5]

        return {
            "total_queries": int(row["total"]) if row else 0,
            "tokens_input": int(row["tokens_input"]) if row else 0,
            "tokens_output": int(row["tokens_output"]) if row else 0,
            "by_status": by_status,
            "top_sources": top_sources,
        }

    def get_recent_questions(
        self, user_id: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT qd.question_text, ql.timestamp, qd.category
                FROM query_logs ql
                JOIN query_details qd ON qd.query_log_id = ql.id
                WHERE ql.telegram_user_id = ? AND qd.question_text IS NOT NULL
                ORDER BY ql.timestamp DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def purge_expired_question_text(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff_iso = (cutoff - timedelta(days=retention_days)).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE query_details
                SET question_text = NULL
                WHERE query_log_id IN (
                    SELECT id FROM query_logs WHERE timestamp < ?
                ) AND question_text IS NOT NULL
                """,
                (cutoff_iso,),
            )
            return int(cursor.rowcount)

    # --- Onboarding (002) ---

    def create_invite(
        self,
        *,
        invite_id: str,
        token: str,
        password_hash: str | None,
        label: str | None,
        created_by: int,
        max_uses: int,
        expires_at: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO invites (
                    id, token, password_hash, label, created_by,
                    max_uses, use_count, expires_at, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'active', ?)
                """,
                (
                    invite_id,
                    token,
                    password_hash,
                    label,
                    created_by,
                    max_uses,
                    expires_at,
                    now,
                ),
            )

    def get_invite_by_token(self, token: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM invites WHERE token = ?", (token,)
            ).fetchone()
        return dict(row) if row else None

    def list_active_invites(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM invites
                WHERE status = 'active'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_invite_status(self, invite_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE invites SET status = ? WHERE id = ?",
                (status, invite_id),
            )

    def revoke_invite_by_token(self, token: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute(
                "UPDATE invites SET status = 'revoked' WHERE token = ? AND status = 'active'",
                (token,),
            )
            return cursor.rowcount > 0

    def increment_invite_use_count(self, invite_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE invites SET use_count = use_count + 1 WHERE id = ?",
                (invite_id,),
            )

    def count_invite_redemptions(self, invite_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM invite_redemptions WHERE invite_id = ?",
                (invite_id,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def sync_invite_use_count(self, invite_id: str, use_count: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE invites SET use_count = ? WHERE id = ?",
                (use_count, invite_id),
            )

    def record_invite_redemption(self, invite_id: str, user_id: int) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO invite_redemptions (
                    invite_id, telegram_user_id, redeemed_at
                ) VALUES (?, ?, ?)
                """,
                (invite_id, user_id, now),
            )

    def is_registered_active(self, user_id: int) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM registered_users
                WHERE telegram_user_id = ? AND is_active = 1 AND blocked_at IS NULL
                """,
                (user_id,),
            ).fetchone()
        return row is not None

    def is_user_blocked(self, user_id: int) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM registered_users
                WHERE telegram_user_id = ? AND (is_active = 0 OR blocked_at IS NOT NULL)
                """,
                (user_id,),
            ).fetchone()
        return row is not None

    def register_user(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        display_name: str,
        invite_id: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO registered_users (
                    telegram_user_id, username, display_name, invite_id,
                    registered_at, is_active
                ) VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username=excluded.username,
                    display_name=excluded.display_name,
                    invite_id=excluded.invite_id,
                    is_active=1,
                    blocked_at=NULL,
                    blocked_by=NULL
                """,
                (telegram_user_id, username, display_name, invite_id, now),
            )

    def list_registered_users(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT ru.*, i.label AS invite_label
                FROM registered_users ru
                LEFT JOIN invites i ON i.id = ru.invite_id
                ORDER BY ru.registered_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_registered_users(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM registered_users").fetchone()
        return int(row["cnt"]) if row else 0

    def get_registered_user(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT ru.*, i.label AS invite_label
                FROM registered_users ru
                LEFT JOIN invites i ON i.id = ru.invite_id
                WHERE ru.telegram_user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def block_user(self, user_id: int, blocked_by: int) -> bool:
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE registered_users
                SET is_active = 0, blocked_at = ?, blocked_by = ?
                WHERE telegram_user_id = ?
                """,
                (now, blocked_by, user_id),
            )
            return cursor.rowcount > 0

    def unblock_user(self, user_id: int) -> bool:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE registered_users
                SET is_active = 1, blocked_at = NULL, blocked_by = NULL
                WHERE telegram_user_id = ?
                """,
                (user_id,),
            )
            return cursor.rowcount > 0

    def count_user_queries(self, user_id: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM query_logs WHERE telegram_user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def get_last_query_time(self, user_id: int) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT timestamp FROM query_logs
                WHERE telegram_user_id = ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return row["timestamp"] if row else None

    def get_password_attempts(
        self, user_id: int, invite_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM password_attempts
                WHERE telegram_user_id = ? AND invite_id = ?
                """,
                (user_id, invite_id),
            ).fetchone()
        return dict(row) if row else None

    def record_password_attempt(self, user_id: int, invite_id: str) -> int:
        limit = 3
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT attempt_count, window_start FROM password_attempts
                WHERE telegram_user_id = ? AND invite_id = ?
                """,
                (user_id, invite_id),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO password_attempts (
                        telegram_user_id, invite_id, attempt_count, window_start
                    ) VALUES (?, ?, 1, ?)
                    """,
                    (user_id, invite_id, now),
                )
                return limit - 1

            window_start = datetime.fromisoformat(row["window_start"])
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=UTC)
            if datetime.now(UTC) - window_start > timedelta(minutes=15):
                conn.execute(
                    """
                    UPDATE password_attempts
                    SET attempt_count = 1, window_start = ?
                    WHERE telegram_user_id = ? AND invite_id = ?
                    """,
                    (now, user_id, invite_id),
                )
                return limit - 1

            new_count = int(row["attempt_count"]) + 1
            conn.execute(
                """
                UPDATE password_attempts SET attempt_count = ?
                WHERE telegram_user_id = ? AND invite_id = ?
                """,
                (new_count, user_id, invite_id),
            )
            return max(0, limit - new_count)

    def reset_password_attempts(self, user_id: int, invite_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM password_attempts
                WHERE telegram_user_id = ? AND invite_id = ?
                """,
                (user_id, invite_id),
            )
