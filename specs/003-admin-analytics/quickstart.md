# Quickstart: Проверка админской аналитики

**Feature**: `003-admin-analytics`  
**Prerequisites**: Работающий бот из `001` + желательно `002` (см. quickstart в тех фичах)

## 1. Конфигурация

Добавьте в `.env`:

```bash
# Существующие
ADMIN_USER_IDS=<ваш_telegram_id>
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
SQLITE_PATH=./data/bot.db

# Новые для 003
ANALYTICS_STORE_QUESTIONS=true
ANALYTICS_QUESTION_RETENTION_DAYS=90
ANALYTICS_REPORT_CHAT_ID=-1001234567890   # служебный чат (опционально)
ANALYTICS_SCHEDULE_ENABLED=true
ANALYTICS_DAILY_CRON=0 18 * * *           # 21:00 MSK
ANALYTICS_WEEKLY_CRON=0 9 * * 1
ANALYTICS_REPORT_MAX_LLM_TOKENS=4096

# Пороги аномалий (опционально, defaults ок)
ANOMALY_NO_ANSWER_RATIO=0.5
ANOMALY_NO_ANSWER_COUNT=5

# P3: дашборд (опционально)
ANALYTICS_DASHBOARD_ENABLED=false
ANALYTICS_DASHBOARD_TOKEN=change-me-long-random
```

## 2. Миграция БД

После реализации (Phase A):

```bash
python -m src.cli health    # старт бота создаёт новые таблицы
```

## 3. Накопить тестовые данные

От 2–3 тестовых аккаунтов задайте 10–15 вопросов, включая:
- вопросы по документам в `knowledge/` (→ `answered`)
- вопросы вне базы (→ `no_answer`)
- «привет как дела» (→ `off_topic`)
- превышение лимита (→ `rate_limited`)

## 4. Сценарий: статистика по запросу

1. От аккаунта админа: `/stats`
2. **Ожидание**: цифры за сегодня, разбивка статусов, топ источников
3. `/stats week` — агрегат за 7 дней с сравнением

## 5. Сценарий: ручная сводка

1. `/report daily`
2. **Ожидание**: сжатое сообщение с темами (не каждый вопрос отдельно)
3. Блок `⚠️ Внимание` при симулированных аномалиях

CLI-эквивалент:

```bash
python -m src.cli report --period daily --dry-run
```

## 6. Сценарий: статистика по пользователю

1. Узнайте `telegram_id` тестового пользователя
2. `/userstats <id>`
3. **Ожидание**: метрики + 5 последних усечённых вопросов

## 7. Сценарий: автосводка

1. Убедитесь `ANALYTICS_SCHEDULE_ENABLED=true`
2. Дождитесь cron или временно выставьте `ANALYTICS_DAILY_CRON` на ближайшую минуту
3. **Ожидание**: сообщение в `ANALYTICS_REPORT_CHAT_ID` или личку админам

## 8. Сценарий: fallback без LLM

1. `/report daily --numeric` (или отключите API key)
2. **Ожидание**: только цифры и топ источников, без тематических кластеров

## 9. Сценарий: retention (после Phase D)

```bash
python -m src.cli purge-analytics --dry-run
```

**Ожидание**: список записей старше 90 дней с обнулением `question_text`

## 10. P3: HTML-дашборд (опционально)

```bash
ANALYTICS_DASHBOARD_ENABLED=true python -m src.cli bot
# откройте http://127.0.0.1:8080/admin/dashboard?token=<ANALYTICS_DASHBOARD_TOKEN>
```

**Ожидание**: график запросов/токенов за 30 дней

## Troubleshooting

| Проблема | Решение |
|---|---|
| `/stats` пустой | Проверьте `query_logs` в SQLite; задайте тестовые вопросы |
| Нет тем в сводке | Мало запросов (<3) или `--numeric`; проверьте OpenRouter |
| Дубликат daily report | `/report daily --force` |
| Не-админ видит команды | Проверьте `ADMIN_USER_IDS` |

## Ссылки

- Команды бота: [contracts/telegram-bot.md](./contracts/telegram-bot.md)
- CLI: [contracts/cli.md](./contracts/cli.md)
- Модель данных: [data-model.md](./data-model.md)
