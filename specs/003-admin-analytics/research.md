# Research: Админская аналитика и сводки

**Feature**: `003-admin-analytics`  
**Date**: 2026-06-29

## Decision 1: Канал доставки сводок

**Decision**: Telegram (команды + автосообщения в `ANALYTICS_REPORT_CHAT_ID` или личка админам); HTML-дашборд — опционально P3.

**Rationale**: Заказчик и админ уже в Telegram (002). Нулевой onboarding. Сводка «раз в день в чат HR» — привычный паттерн. Дашборд не блокирует MVP.

**Alternatives considered**:
- Только веб-дашборд — нужен UI, auth, деплой порта; избыточно для 50 человек
- Email-отчёты — нужен SMTP, чаще попадают в спам
- Slack webhook — у заказчика Telegram как основной канал

---

## Decision 2: Хранение текста вопросов

**Decision**: Опционально `ANALYTICS_STORE_QUESTIONS=true` (default true); хранить усечённый текст (max 500 символов) в `query_details`; retention 90 дней.

**Rationale**: Без текста невозможно понять «что спрашивают» и отличить оффтоп от пробела в базе знаний. 001 изначально не сохранял текст (privacy) — для корпоративного бота с ≤50 сотрудников админский контроль важнее; mitigated retention + admin-only `/userstats`.

**Alternatives considered**:
- Только метаданные (длина, статус, токены) — недостаточно для «норм/не норм»
- Полный текст без retention — риск накопления PII
- Хеш вопроса вместо текста — нельзя прочитать тему

---

## Decision 3: Формат сводки — сжатие через LLM

**Decision**: Двухслойный отчёт: (1) детерминированные SQL-агрегаты; (2) один LLM-вызов для кластеризации тем и рекомендаций по списку усечённых вопросов (max 50 штук за период, остальное — только в цифрах).

**Rationale**: Заказчик явно не хочет «каждое сообщение». LLM хорошо группирует «отпуск», «сколько дней отпуска», «как взять отпуск» в одну тему. Стоимость: ~2–5k input tokens на сводку ≈ копейки на gpt-4o-mini.

**Alternatives considered**:
- Embeddings + k-means кластеризация — сложнее, нужны embeddings API на batch
- Keyword extraction (TF-IDF) — слабо на русском NL вопросах
- Полный dump в файл — неудобно в Telegram

**Fallback**: Если LLM недоступен — только числовой блок + топ источников из `sources_cited`.

---

## Decision 4: Классификация запросов

**Decision**: Правила на этапе логирования + пост-фактум агрегация:

| Category | Условие |
|---|---|
| `answered` | status=success, chunks found |
| `no_answer` | status=no_answer |
| `off_topic` | success но similarity всех chunks < порога ИЛИ эвристика (приветствие, «как дела», мат) |
| `error` | status=error |
| `rate_limited` | status=rate_limited |
| `unauthorized` | status=unauthorized |

**Rationale**: Большинство — без LLM в hot path (дешево). `off_topic` отделяет «болтовню» от «нет документа в БЗ».

**Alternatives considered**:
- LLM-классификация каждого вопроса — дорого при 500 req/day
- Только status из 001 — не различает оффтоп и пробел в knowledge

---

## Decision 5: Расписание автосводок

**Decision**: APScheduler в процессе бота (`AsyncIOScheduler`); env: `ANALYTICS_SCHEDULE_ENABLED`, `ANALYTICS_DAILY_CRON` (default `0 18 * * *` UTC = 21:00 MSK), `ANALYTICS_WEEKLY_CRON` (default `0 9 * * 1`). Дублирование через CLI для cron в Docker: `python -m src.cli report --period daily`.

**Rationale**: Один процесс, без отдельного worker. CLI — fallback если scheduler падает при рестарте.

**Alternatives considered**:
- systemd timer на хосте — не переносимо в Docker
- Celery + Redis — overkill
- Только ручной `/report` — админ забудет

---

## Decision 6: Правила аномалий (defaults)

**Decision**: Конфигурируемые пороги в env:

| Flag | Default | Описание |
|---|---|---|
| `ANOMALY_NO_ANSWER_RATIO` | 0.5 | ≥50% no_answer у user за день |
| `ANOMALY_NO_ANSWER_COUNT` | 5 | и минимум 5 таких запросов |
| `ANOMALY_LIMIT_USAGE_RATIO` | 0.9 | ≥90% дневного лимита |
| `ANOMALY_TOKEN_USER_DAILY` | 10000 | токенов in+out на user/день |

**Rationale**: Прозрачные правила, легко тестировать. Админ видит «кто сливает бюджет» без ML.

**Alternatives considered**:
- ML anomaly detection — нет данных для обучения
- Только глобальные метрики — не видно проблемного пользователя

---

## Decision 7: HTML-дашборд (P3)

**Decision**: FastAPI, один route `GET /admin/dashboard?token=`, данные из `daily_stats`, Chart.js с CDN, bind `127.0.0.1:8080` или за reverse proxy.

**Rationale**: Минимальный UI для трендов (график запросов/токенов за 30 дней). Secret token в URL — достаточно для internal tool за VPN.

**Alternatives considered**:
- Grafana + Prometheus — инфраструктурный оверкилл
- React SPA — долго разрабатывать
- Telegram-only навсегда — заказчик «может» захотеть браузер

---

## Decision 8: Расширение существующей таблицы query_logs

**Decision**: Новая таблица `query_details` (1:1 с `query_logs.id`) вместо ALTER `query_logs` — меньше риска для существующих запросов и миграций.

**Rationale**: 001 уже пишет в `query_logs`. Добавление колонок потребует миграции всех инсталляций. Sidecar table — чище.

**Alternatives considered**:
- JSON column в query_logs — смешивает hot write path
- Отдельная analytics DB — избыточно

---

## Decision 9: Лимит токенов на генерацию отчёта

**Decision**: `ANALYTICS_REPORT_MAX_LLM_TOKENS=4096` output; модель — та же `LLM_MODEL` или отдельная `ANALYTICS_SUMMARY_MODEL` (default gpt-4o-mini).

**Rationale**: Защита бюджета: сводка не должна стоить дороже пары пользовательских вопросов.

**Alternatives considered**:
- Без лимита — риск при большом batch вопросов
- Отдельный дорогой model — не нужен для суммаризации
