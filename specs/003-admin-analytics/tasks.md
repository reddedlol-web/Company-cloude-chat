---
description: "Task list for admin analytics feature implementation"
---

# Tasks: Админская аналитика и сводки

**Input**: Design documents from `/specs/003-admin-analytics/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit и integration тесты включены согласно plan.md (агрегация, аномалии, report flow).

**Organization**: Задачи сгруппированы по user story для независимой реализации и проверки.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Можно выполнять параллельно (разные файлы, нет зависимостей от незавершённых задач)
- **[Story]**: Привязка к user story (US1–US5)

## Path Conventions

- Single project: `src/`, `tests/` в корне репозитория

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Зависимости и структура модуля аналитики

- [x] T001 Add APScheduler dependency in pyproject.toml
- [x] T002 [P] Create analytics package scaffold in src/analytics/__init__.py
- [x] T003 [P] Add ANALYTICS_* and ANOMALY_* variables to .env.example

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Схема БД, конфиг, классификация и запись метрик — блокирует все user stories

**⚠️ CRITICAL**: User story work не начинается до завершения этой фазы

- [x] T004 Add analytics tables SQL (query_details, daily_stats, analytics_reports, anomaly_flags) in src/db/models.py
- [x] T005 Add analytics CRUD and query methods in src/db/repository.py (record_query_detail, get_period_stats, save_report, etc.)
- [x] T006 Add AnalyticsConfig settings fields in src/config.py per data-model.md
- [x] T007 Implement query category classifier in src/analytics/classifier.py (answered, no_answer, off_topic, error, rate_limited, unauthorized)
- [x] T008 Extend log_query flow to persist query_details in src/bot/handlers/messages.py (question_text truncated, category, max_similarity from retriever)
- [x] T009 Implement daily/period aggregation roll-up in src/analytics/aggregator.py (compute_daily_stats, get_stats_for_period)

**Checkpoint**: Foundation ready — метрики пишутся, агрегаты считаются

---

## Phase 3: User Story 1 — Сводка за период (Priority: P1) 🎯 MVP

**Goal**: Админ получает сжатую сводку `/report daily|weekly` и автоматически по расписанию в Telegram

**Independent Test**: 20+ тестовых запросов → `/report daily` → сводка с цифрами, 3–7 темами, блоком аномалий (если есть), ≤3 сообщений

### Implementation for User Story 1

- [x] T010 [US1] Implement numeric + LLM summary report builder in src/analytics/reporter.py (format_report, llm_topic_clustering, split_telegram_messages)
- [x] T011 [US1] Implement report persistence and idempotency in src/analytics/reporter.py using src/db/repository.py (analytics_reports)
- [x] T012 [US1] Implement Telegram report delivery in src/analytics/delivery.py (ANALYTICS_REPORT_CHAT_ID → ADMIN_NOTIFY_CHAT_ID → ADMIN_USER_IDS fallback)
- [x] T013 [US1] Create admin analytics router with /report command in src/bot/handlers/analytics.py
- [x] T014 [US1] Register analytics router and admin guard in src/bot/main.py
- [x] T015 [US1] Implement APScheduler jobs for daily/weekly reports in src/analytics/scheduler.py
- [x] T016 [US1] Wire scheduler startup/shutdown in src/bot/main.py when ANALYTICS_SCHEDULE_ENABLED=true
- [x] T017 [US1] Add `report` CLI subcommand in src/cli.py per contracts/cli.md (--period, --numeric, --force, --dry-run)

**Checkpoint**: `/report daily` и автосводка работают независимо от /stats

---

## Phase 4: User Story 2 — Статистика по запросу (Priority: P1)

**Goal**: Админ запрашивает `/stats`, `/stats week`, `/stats month` с цифрами и сравнением периодов

**Independent Test**: После 10 запросов `/stats` показывает корректные счётчики, % success vs no_answer, топ-3 источника

### Implementation for User Story 2

- [x] T018 [US2] Implement stats formatter with period comparison in src/analytics/reporter.py (format_stats_message)
- [x] T019 [US2] Add /stats handler with today|week|month parsing in src/bot/handlers/analytics.py
- [x] T020 [US2] Add `stats` CLI subcommand with --json output in src/cli.py
- [x] T021 [P] [US2] Add unit tests for aggregator period queries in tests/unit/test_analytics_aggregator.py

**Checkpoint**: `/stats` и `/stats week` работают; не-админ получает отказ

---

## Phase 5: User Story 3 — Выявление «ненормального» использования (Priority: P2)

**Goal**: Система флагует аномалии (no_answer spike, лимит, token spike, off_topic) в сводках и /stats

**Independent Test**: 15 no_answer от одного user_id → в `/report daily` блок «⚠️ Внимание» с user_id и описанием

### Implementation for User Story 3

- [x] T022 [US3] Implement rule-based anomaly detection in src/analytics/anomalies.py (detect_anomalies, AnomalyFlag dataclass)
- [x] T023 [US3] Persist anomaly_flags and embed in report in src/analytics/reporter.py
- [x] T024 [US3] Show anomaly warnings in /stats and /report output in src/bot/handlers/analytics.py
- [x] T025 [P] [US3] Add unit tests for anomaly thresholds in tests/unit/test_analytics_anomalies.py

**Checkpoint**: Аномалии видны в сводке и on-demand статистике

---

## Phase 6: User Story 4 — Детализация по пользователю (Priority: P2)

**Goal**: Админ смотрит `/userstats <telegram_id>` — метрики и последние 5 вопросов (усечённо)

**Independent Test**: `/userstats 123456` показывает запросы/токены за день и неделю + последние вопросы

### Implementation for User Story 4

- [x] T026 [US4] Add per-user analytics queries in src/db/repository.py (get_user_stats, get_recent_questions)
- [x] T027 [US4] Implement user stats card formatter in src/analytics/reporter.py (format_userstats_message)
- [x] T028 [US4] Add /userstats handler in src/bot/handlers/analytics.py

**Checkpoint**: `/userstats <id>` работает; при ANALYTICS_STORE_QUESTIONS=false скрыты тексты вопросов

---

## Phase 7: User Story 5 — Мини-дашборд HTML (Priority: P3)

**Goal**: Read-only HTML-страница с KPI и графиком за 30 дней по секретному токену

**Independent Test**: GET `/admin/dashboard?token=...` → HTML с таблицей daily_stats; неверный токен → 401

### Implementation for User Story 5

- [x] T029 [P] [US5] Add optional fastapi and uvicorn dependencies in pyproject.toml
- [x] T030 [US5] Implement read-only dashboard app in src/dashboard/app.py (token auth, 30d daily_stats, Chart.js CDN)
- [x] T031 [US5] Start dashboard HTTP server alongside bot in src/bot/main.py when ANALYTICS_DASHBOARD_ENABLED=true

**Checkpoint**: Дашборд опционален; MVP (US1+US2) не зависит от этой фазы

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: CLI maintenance, тесты, документация, retention

- [x] T032 Add `aggregate` and `purge-analytics` CLI subcommands in src/cli.py
- [x] T033 [P] Add integration test for report generation flow in tests/integration/test_analytics_report_flow.py
- [x] T034 [P] Add unit tests for report formatting and LLM fallback in tests/unit/test_analytics_reporter.py
- [x] T035 Update docs/deploy.md with ANALYTICS_* env vars and scheduler notes
- [x] T036 [P] Update README.md with admin analytics commands section
- [x] T037 Validate all scenarios in specs/003-admin-analytics/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Нет зависимостей
- **Foundational (Phase 2)**: Зависит от Setup — **блокирует все user stories**
- **US1 (Phase 3)**: Зависит от Phase 2
- **US2 (Phase 4)**: Зависит от Phase 2; может идти параллельно с US1 после T009
- **US3 (Phase 5)**: Зависит от US1 reporter (T010–T011); интегрируется в сводки и /stats
- **US4 (Phase 6)**: Зависит от Phase 2 (query_details); независима от US3
- **US5 (Phase 7)**: Зависит от daily_stats (T009); опциональна
- **Polish (Phase 8)**: После желаемых user stories

### User Story Dependencies

```text
Phase 2 (Foundation)
    ├── US1 (P1) Reports + Scheduler  ──┐
    ├── US2 (P1) /stats                 ──┼── MVP core
    ├── US4 (P2) /userstats             ──┘ (parallel after Phase 2)
    ├── US3 (P2) Anomalies → extends US1 + US2
    └── US5 (P3) Dashboard → uses daily_stats only
```

### Parallel Opportunities

- **Phase 1**: T002, T003 параллельно
- **После Phase 2**: US1 (T010–T017) и US2 (T018–T021) — разные части reporter/handlers, координация через aggregator
- **После US1**: US4 (T026–T028) параллельно с US3 (T022–T025)
- **Phase 8**: T033, T034, T036 параллельно

---

## Parallel Example: User Story 2

```bash
# После Phase 2 — stats можно делать параллельно с report delivery:
Task T018: "Implement stats formatter in src/analytics/reporter.py"
Task T019: "Add /stats handler in src/bot/handlers/analytics.py"
Task T021: "Unit tests in tests/unit/test_analytics_aggregator.py"
```

---

## Parallel Example: User Story 1

```bash
# Внутри US1 — delivery и scheduler независимы от CLI:
Task T012: "Implement delivery in src/analytics/delivery.py"
Task T015: "Implement scheduler in src/analytics/scheduler.py"
Task T017: "Add report CLI in src/cli.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL**)
3. Complete Phase 3: US1 — сводки и автодоставка
4. Complete Phase 4: US2 — `/stats` on-demand
5. **STOP and VALIDATE**: quickstart сценарии 4–7
6. Deploy/demo

### Incremental Delivery

1. Foundation → метрики пишутся
2. US1 → `/report` + scheduler → **основная ценность для заказчика**
3. US2 → `/stats` → быстрый контроль «всё ли норм»
4. US3 → аномалии в сводках
5. US4 → `/userstats` для разбора по человеку
6. US5 → HTML-дашборд (если нужен заказчику)

### Suggested MVP Scope

- **Обязательно**: Phase 1–2 + US1 + US2 (T001–T021)
- **Следующий инкремент**: US3 + US4 (T022–T028)
- **Опционально**: US5 (T029–T031)

---

## Notes

- Все admin-команды: только `ADMIN_USER_IDS` (см. contracts/telegram-bot.md)
- LLM в сводке: cap `ANALYTICS_REPORT_MAX_LLM_TOKENS`; fallback на numeric-only при ошибке API
- Retention: `purge-analytics` обнуляет question_text, не трогает агрегаты
- Зависимость от 002: username в карточках — из `registered_users` если есть, иначе только telegram_id
