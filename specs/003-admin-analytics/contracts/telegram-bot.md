# Contract: Telegram Bot — Analytics Commands

**Feature**: `003-admin-analytics`  
**Audience**: Administrators (`ADMIN_USER_IDS`)  
**Transport**: Telegram Bot API (aiogram 3.x)

## Authorization

All commands in this contract require `is_admin(user_id) == true`.  
Non-admins receive: `⛔ Команда доступна только администраторам.`

---

## Command: `/stats`

**Purpose**: On-demand numeric statistics.

### Syntax

```text
/stats              # today (UTC)
/stats today        # alias
/stats week         # last 7 days
/stats month        # last 30 days
```

### Response format (example)

```text
📈 Статистика (сегодня, UTC)

Запросы: 23
Активных пользователей: 8
Токены: 9 100 in / 3 400 out

По статусам:
✅ success: 18 (78%)
❓ no_answer: 3 (13%)
🚫 rate_limited: 1
⚠️ error: 1

По категориям:
answered: 18 | no_answer: 3 | off_topic: 2

Топ источников:
• leave-policy.md — 9
• remote-work.md — 6
• it-support.md — 4

Сравнение с вчера: запросы ↑15%, токены ↓3%
```

### Errors

| Condition | Response |
|---|---|
| No data for period | `📭 За выбранный период запросов не было.` |
| Invalid period arg | `Использование: /stats [today\|week\|month]` |

---

## Command: `/report`

**Purpose**: Generate and send a compressed summary (with optional LLM insights).

### Syntax

```text
/report daily           # yesterday or today (configurable)
/report weekly          # last 7 days
/report daily --numeric # skip LLM, numbers only
```

### Behavior

1. Aggregate stats for period
2. Detect anomalies
3. If not `--numeric` and queries ≥ 3: call LLM for topic clustering
4. Send 1–3 messages to invoking admin (and optionally mirror to report chat)
5. Persist `analytics_reports` row

### Response format

See plan.md example block «Сводка за DD.MM.YYYY».

### Errors

| Condition | Response |
|---|---|
| Duplicate daily report (scheduler sent) | `ℹ️ Сводка за этот день уже отправлялась в HH:MM. Повтор: /report daily --force` |
| LLM failure | Numeric-only fallback + `⚠️ Тематический анализ недоступен` |
| Empty period | `📭 Нет данных за период` |

---

## Command: `/userstats`

**Purpose**: Per-user analytics card.

### Syntax

```text
/userstats <telegram_user_id>
/userstats <telegram_user_id> week
```

### Response format (example)

```text
👤 Пользователь 123456789 (@ivan)

Сегодня: 12 запросов, 4 200 токенов
За неделю: 34 запроса, 11 800 токенов

Статусы (неделя): ✅28 ❓5 🚫1
Топ источников: leave-policy (12), faq/leave (8)

⚠️ 8 запросов без ответа в БЗ за неделю

Последние вопросы:
1. Сколько дней отпуска положено в первый год…
2. Как оформить больничный удалённо…
3. …
```

### Errors

| Condition | Response |
|---|---|
| Invalid user_id | `Укажите числовой Telegram ID: /userstats 123456789` |
| User not found / no activity | `Активности нет за выбранный период` |
| `ANALYTICS_STORE_QUESTIONS=false` | Последние вопросы скрыты; только метрики |

---

## Scheduled delivery (not a user command)

**Trigger**: APScheduler per `ANALYTICS_DAILY_CRON` / `ANALYTICS_WEEKLY_CRON`

**Recipient priority**:
1. `ANALYTICS_REPORT_CHAT_ID`
2. `ADMIN_NOTIFY_CHAT_ID` (from 002)
3. Each `ADMIN_USER_IDS` (DM)

**Idempotency**: One `daily` report per `period_start` unless `--force`.

---

## Message splitting

Telegram limit: 4096 chars per message.

- Split on section boundaries (`\n\n`)
- Max 3 messages per report
- Truncate topic list to 7 items; note `+N тем в /report weekly --full` (future)

---

## Integration with existing handlers

- `messages.py`: after `log_query()`, call `analytics.record_query_detail()`
- Rate limit / auth middleware: unchanged; categories derived from status
