# Implementation Plan: Админская аналитика и сводки

**Branch**: `003-admin-analytics` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-admin-analytics/spec.md`

## Summary

Расширение бота аналитикой для администратора: сбор расширенных метрик по каждому запросу, агрегаты по дням, on-demand команды `/stats` и `/report`, автоматические ежедневные/еженедельные сводки в Telegram с LLM-сжатием тем (не каждое сообщение), флаги аномалий для контроля расхода токенов. Опционально — лёгкий HTML-дашборд по секретному токену (P3).

**Рекомендуемый UX для заказчика**: основной канал — Telegram (сводки в служебный чат + команды); дашборд — «nice to have» для просмотра трендов в браузере.

## Technical Context

**Language/Version**: Python 3.11+ (как в 001/002)

**Primary Dependencies**: aiogram 3.x, APScheduler 3.x (расписание сводок), существующие `src/db`, `src/llm`, `src/config`; опционально FastAPI + uvicorn для HTML-дашборда (P3)

**Storage**: SQLite — расширение `query_logs` / новая `query_details`, таблицы `daily_stats`, `analytics_reports`, `anomaly_flags`

**Testing**: pytest — unit (агрегация, anomaly rules, report formatting), integration (report generation end-to-end с mock LLM)

**Target Platform**: Тот же Docker-контейнер; scheduler в процессе бота или sidecar cron через `python -m src.cli report --period daily`

**Project Type**: Расширение single backend service

**Performance Goals**: `/stats` ≤2 с при 5k логов; batch-агрегация daily_stats ≤5 с; LLM-сводка ≤30 с

**Constraints**: Cap токенов на отчёт; retention текстов вопросов; сводки ≤4096 символов на сообщение Telegram

**Scale/Scope**: ≤50 пользователей, ≤500 запросов/день, 1–3 админа, 1–2 сводки/день

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution в template-состоянии. Interim gates из 001/002:

| Gate | Status | Notes |
|---|---|---|
| Simplicity (YAGNI) | ✅ PASS | MVP = Telegram commands + scheduler; дашборд P3 |
| Testability | ✅ PASS | Агрегация и правила аномалий — чистые функции |
| Security | ✅ PASS | Admin-only; дашборд по secret token; retention |
| Observability | ✅ PASS | Сама фича — observability для админа |
| Privacy | ⚠️ JUSTIFIED | Хранение текста вопросов — opt-in config, retention 90d |
| Scope control | ✅ PASS | Не BI-платформа; сжатые сводки, не raw dump |

**Post-design re-check**: Gates pass. Хранение question_text оправдано требованием контроля качества; mitigated retention + admin-only access.

## Project Structure

### Documentation (this feature)

```text
specs/003-admin-analytics/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── telegram-bot.md  # /stats, /report, /userstats
│   └── cli.md           # report, stats, purge-analytics
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (changes to existing layout)

```text
src/
├── analytics/
│   ├── __init__.py
│   ├── aggregator.py      # SQL aggregates → DailyStats
│   ├── anomalies.py       # rule-based flags
│   ├── classifier.py      # off_topic heuristics (+ optional LLM)
│   ├── reporter.py        # build report text, LLM summarize
│   └── scheduler.py       # APScheduler jobs
├── bot/
│   └── handlers/
│       └── analytics.py   # NEW: /stats, /report, /userstats
├── db/
│   ├── models.py          # + analytics tables
│   └── repository.py      # + analytics CRUD/queries
├── config.py              # + ANALYTICS_* settings
├── cli.py                 # + report, stats subcommands
└── dashboard/             # P3 optional
    ├── __init__.py
    └── app.py             # FastAPI read-only HTML

tests/
├── unit/
│   ├── test_analytics_aggregator.py
│   ├── test_analytics_anomalies.py
│   └── test_analytics_reporter.py
└── integration/
    └── test_analytics_report_flow.py
```

**Structure Decision**: Модуль `src/analytics/` изолирует бизнес-логику от handlers; scheduler стартует в `bot/main.py` при `ANALYTICS_SCHEDULE_ENABLED=true`.

## Recommended Approach

### Что видит админ (пример ежедневной сводки)

```text
📊 Сводка за 28.06.2026

Запросы: 47 (↑12% к вчера)
Пользователи: 12 активных
Токены: 18 400 in / 6 200 out (~$0.42)

Статусы:
✅ Ответ из базы: 38 (81%)
❓ Нет в базе: 6 (13%)
🚫 Лимит: 2 | ⚠️ Ошибки: 1

Темы (сгруппировано):
• Отпуск и больничный — 14 вопросов
• Удалёнка и график — 9
• IT / доступы — 7
• Возвраты и компенсации — 5
• Прочее — 3

⚠️ Внимание:
• @ivan: 8 вопросов без ответа в БЗ — возможно, нет документов по теме
• @maria: 19/20 лимита сегодня

💡 Рекомендация: добавить в knowledge FAQ по больничным (6 no_answer).

/stats week — детали | /userstats <id> — по человеку
```

### Почему не «каждое сообщение»

| Подход | Плюсы | Минусы |
|---|---|---|
| Raw dump всех вопросов | Полная детализация | Нечитаемо при 50+ запросах; шум в Telegram |
| **LLM-кластеризация тем (выбрано)** | Сжато, actionable | +1 LLM-вызов/сводку (~$0.01–0.05) |
| Только цифры без LLM | Дёшево | Нет «что спрашивают» |

Детализация доступна через `/userstats` и опциональный HTML-дашборд.

### Почему Telegram-first, дашборд — P3

Согласовано с 002: админ уже в Telegram. Сводка в служебный чат = нулевой порог входа. HTML-дашборд добавляет хостинг порта и auth — делаем после MVP, если заказчику нужны графики.

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Хранение question_text | Админ хочет видеть «что спрашивают» | Только длина вопроса не даёт контроля |
| LLM в сводке | Группировка 50+ вопросов в 5–7 тем | Ручные SQL GROUP BY не работают для NL |
| APScheduler | Авто daily/weekly | Только cron CLI — админ забудет включить |

## Implementation Phases (for /speckit-tasks)

### Phase A: Schema & logging
- Миграция: `query_details`, `daily_stats`, `analytics_reports`, `anomaly_flags`
- Расширить `log_query()` — category, question_text (truncated)
- Classifier: off_topic heuristics (нет chunks + длина, ключевые слова)

### Phase B: Aggregation & anomalies
- `aggregator.py`: roll-up в `daily_stats` (cron или on-demand)
- `anomalies.py`: пороги no_answer%, лимит%, token spike
- Unit tests

### Phase C: Reporter & bot commands
- `reporter.py`: numeric report + optional LLM summary
- Handlers: `/stats`, `/report`, `/userstats`
- Доставка в `ANALYTICS_REPORT_CHAT_ID` или admins

### Phase D: Scheduler & CLI
- APScheduler в bot main
- CLI: `python -m src.cli report --period daily`
- Retention job: purge старых question_text

### Phase E: Dashboard (P3, optional)
- FastAPI `/admin/dashboard?token=`
- Static charts (Chart.js CDN) — 30d daily_stats

## Artifacts Generated

| Artifact | Path | Status |
|---|---|---|
| Feature spec | `specs/003-admin-analytics/spec.md` | ✅ |
| Research | `specs/003-admin-analytics/research.md` | ✅ |
| Data model | `specs/003-admin-analytics/data-model.md` | ✅ |
| Contracts | `specs/003-admin-analytics/contracts/` | ✅ |
| Quickstart | `specs/003-admin-analytics/quickstart.md` | ✅ |
| Tasks | `specs/003-admin-analytics/tasks.md` | ⏳ (/speckit-tasks) |
