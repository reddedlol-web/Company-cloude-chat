# Data Model: Админская аналитика

**Feature**: `003-admin-analytics`  
**Date**: 2026-06-29  
**Extends**: `001-company-telegram-bot` (QueryLog, DailyUsage), `002-admin-onboarding` (RegisteredUser)

## Overview

Аналитика строится поверх существующих `query_logs` и `daily_usage`. Новые сущности добавляют детализацию вопросов, дневные агрегаты, сгенерированные отчёты и флаги аномалий.

---

## Entity: QueryDetail (extends QueryLog)

Детализация одного запроса. Связь 1:1 с `query_logs.id`.

| Field | Type | Required | Description |
|---|---|---|---|
| query_log_id | INTEGER | yes | PK, FK → query_logs.id |
| question_text | TEXT | no | Усечённый текст (max 500 chars), если `ANALYTICS_STORE_QUESTIONS` |
| question_hash | TEXT | yes | SHA-256 первых 500 chars — дедуп повторов |
| category | ENUM | yes | `answered`, `no_answer`, `off_topic`, `error`, `rate_limited`, `unauthorized` |
| max_similarity | REAL | no | Лучший score retrieval (0–1) |
| topic_cluster | TEXT | no | Заполняется при batch-отчёте (LLM label) |

**Validation**:
- `question_text` length ≤ 500
- `category` must match `query_logs.status` mapping rules

**Privacy**:
- Purge `question_text` after `ANALYTICS_QUESTION_RETENTION_DAYS` (default 90)
- Keep `question_hash` and aggregates

---

## Entity: DailyStats

Предагрегированные метрики за календарный день (UTC). Заполняется job'ом после полуночи или перед отчётом.

| Field | Type | Required | Description |
|---|---|---|---|
| stats_date | DATE | yes | PK |
| total_queries | INTEGER | yes | |
| unique_users | INTEGER | yes | |
| tokens_input | INTEGER | yes | SUM |
| tokens_output | INTEGER | yes | SUM |
| by_status | TEXT | yes | JSON `{"success":38,"no_answer":6,...}` |
| by_category | TEXT | yes | JSON `{"answered":38,"off_topic":2,...}` |
| top_sources | TEXT | yes | JSON `[{"title":"leave-policy","count":14},...]` top 10 |
| computed_at | TIMESTAMP | yes | UTC |

**Unique constraint**: `stats_date`

---

## Entity: AnalyticsReport

Сохранённая сводка (для истории и идемпотентности scheduler).

| Field | Type | Required | Description |
|---|---|---|---|
| id | INTEGER | yes | PK autoincrement |
| period_type | ENUM | yes | `daily`, `weekly`, `manual` |
| period_start | DATE | yes | Inclusive |
| period_end | DATE | yes | Inclusive |
| generated_at | TIMESTAMP | yes | UTC |
| summary_text | TEXT | yes | Финальный текст для Telegram |
| anomalies_json | TEXT | no | JSON array of AnomalyFlag snapshots |
| stats_snapshot | TEXT | yes | JSON copy of aggregates used |
| llm_tokens_used | INTEGER | no | |
| delivery_status | ENUM | yes | `pending`, `sent`, `failed`, `skipped_empty` |
| delivered_at | TIMESTAMP | no | |

**Index**: `(period_type, period_start)` — prevent duplicate daily reports

---

## Entity: AnomalyFlag

Runtime или batch-обнаруженные аномалии.

| Field | Type | Required | Description |
|---|---|---|---|
| id | INTEGER | yes | PK |
| detected_at | TIMESTAMP | yes | UTC |
| stats_date | DATE | yes | День, к которому относится |
| telegram_user_id | INTEGER | no | NULL = global anomaly |
| anomaly_type | ENUM | yes | `high_no_answer_ratio`, `limit_near`, `token_spike`, `off_topic_spike` |
| severity | ENUM | yes | `info`, `warning`, `critical` |
| description | TEXT | yes | Human-readable RU |
| metadata_json | TEXT | no | Пороги, фактические значения |
| acknowledged | BOOLEAN | yes | default false (future: /anomaly ack) |

**Index**: `(stats_date, telegram_user_id)`

---

## Entity: AnalyticsConfig (environment)

| Variable | Type | Default | Description |
|---|---|---|---|
| ANALYTICS_STORE_QUESTIONS | bool | true | Сохранять текст вопроса |
| ANALYTICS_QUESTION_RETENTION_DAYS | int | 90 | Purge question_text |
| ANALYTICS_REPORT_CHAT_ID | int | — | Чат для сводок (fallback: ADMIN_NOTIFY_CHAT_ID → admins) |
| ANALYTICS_SCHEDULE_ENABLED | bool | true | APScheduler on |
| ANALYTICS_DAILY_CRON | string | `0 18 * * *` | UTC cron |
| ANALYTICS_WEEKLY_CRON | string | `0 9 * * 1` | Понедельник 09:00 UTC |
| ANALYTICS_REPORT_MAX_LLM_TOKENS | int | 4096 | Cap output |
| ANALYTICS_SUMMARY_MODEL | string | same as LLM_MODEL | Модель для сводок |
| ANALYTICS_OFF_TOPIC_SIMILARITY_THRESHOLD | float | 0.35 | Below = likely off_topic |
| ANOMALY_NO_ANSWER_RATIO | float | 0.5 | |
| ANOMALY_NO_ANSWER_COUNT | int | 5 | |
| ANOMALY_LIMIT_USAGE_RATIO | float | 0.9 | |
| ANOMALY_TOKEN_USER_DAILY | int | 10000 | |
| ANALYTICS_DASHBOARD_ENABLED | bool | false | P3 |
| ANALYTICS_DASHBOARD_TOKEN | secret | — | URL token |
| ANALYTICS_DASHBOARD_PORT | int | 8080 | |

---

## Schema SQL (additions)

```sql
CREATE TABLE IF NOT EXISTS query_details (
    query_log_id INTEGER PRIMARY KEY REFERENCES query_logs(id) ON DELETE CASCADE,
    question_text TEXT,
    question_hash TEXT NOT NULL,
    category TEXT NOT NULL,
    max_similarity REAL,
    topic_cluster TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    stats_date TEXT PRIMARY KEY,
    total_queries INTEGER NOT NULL DEFAULT 0,
    unique_users INTEGER NOT NULL DEFAULT 0,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    by_status TEXT NOT NULL DEFAULT '{}',
    by_category TEXT NOT NULL DEFAULT '{}',
    top_sources TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    anomalies_json TEXT,
    stats_snapshot TEXT NOT NULL,
    llm_tokens_used INTEGER,
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    delivered_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_period
    ON analytics_reports (period_type, period_start);

CREATE TABLE IF NOT EXISTS anomaly_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TEXT NOT NULL,
    stats_date TEXT NOT NULL,
    telegram_user_id INTEGER,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata_json TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_anomaly_date_user
    ON anomaly_flags (stats_date, telegram_user_id);
```

---

## Relationships Diagram

```text
query_logs 1 ── 1 query_details
query_logs N ──> daily_stats (aggregated by date)

RegisteredUser 1 ──< query_logs (via telegram_user_id)
RegisteredUser 1 ──< anomaly_flags

daily_stats 1 ──< analytics_reports (snapshot reference)
anomaly_flags N ──> analytics_reports (embedded in anomalies_json)
```

---

## Category Mapping (query_logs.status → category)

| query_logs.status | category | Notes |
|---|---|---|
| success + similarity ≥ threshold | answered | |
| success + similarity < threshold | off_topic | |
| no_answer | no_answer | |
| error | error | |
| rate_limited | rate_limited | |
| unauthorized | unauthorized | |

---

## State: AnalyticsReport.delivery_status

```text
pending → sent | failed | skipped_empty
```

- `skipped_empty`: 0 queries in period
- `failed`: Telegram API or LLM error after retries
