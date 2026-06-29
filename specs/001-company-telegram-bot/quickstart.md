# Quickstart: Company Telegram Knowledge Bot

**Feature**: `001-company-telegram-bot`

Пошаговая проверка, что фича работает end-to-end. Детали контрактов: [telegram-bot.md](./contracts/telegram-bot.md), [cli.md](./contracts/cli.md). Модель данных: [data-model.md](./data-model.md).

---

## Prerequisites

- Python 3.11+
- Telegram account
- OpenRouter API key ([openrouter.ai](https://openrouter.ai))
- Bot token from [@BotFather](https://t.me/BotFather)

---

## 1. Setup

```bash
cd /Users/philipp_nahornyi/Projects/Company-cloude-chat

# Create venv and install (after implementation)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env:
#   TELEGRAM_BOT_TOKEN=...
#   OPENROUTER_API_KEY=...
#   ALLOWED_USER_IDS=<your_telegram_user_id>
#   ADMIN_USER_IDS=<your_telegram_user_id>
```

**Get your Telegram user ID**: напишите [@userinfobot](https://t.me/userinfobot) в Telegram.

---

## 2. Add test documents

```bash
mkdir -p knowledge

cat > knowledge/refund-policy.md << 'EOF'
# Политика возврата

Возврат товара возможен в течение 14 дней с момента покупки.
Для возврата обратитесь в отдел продаж: sales@company.com.
EOF

cat > knowledge/vacation-policy.md << 'EOF'
# Отпуск

Минимальный отпуск — 28 календарных дней в год.
Заявление подаётся за 2 недели до начала отпуска через HR.
EOF
```

---

## 3. Initialize and index

```bash
python -m src.cli db init
python -m src.cli knowledge reindex
python -m src.cli knowledge status
```

**Expected**: JSON с `documents_indexed: 2`, `chunks_created` > 0.

---

## 4. Health check

```bash
python -m src.cli health
```

**Expected**: все поля `"ok"`.

---

## 5. Run bot

```bash
python -m src.cli bot run
```

---

## 6. Manual validation scenarios

### Scenario A: Authorized Q&A (P1)

1. Откройте бота в Telegram, отправьте `/start`
2. **Expected**: приветствие + лимит
3. Спросите: «Сколько дней на возврат товара?»
4. **Expected**: ответ «14 дней», источник `refund-policy`

### Scenario B: No answer (P1)

1. Спросите: «Какой курс доллара сегодня?`
2. **Expected**: сообщение, что в базе нет информации

### Scenario C: Unauthorized (P1)

1. Попросите коллегу (не в whitelist) написать боту
2. **Expected**: «У вас нет доступа»

### Scenario D: Rate limit (P2)

1. Установите `DAILY_QUERY_LIMIT=3` в `.env`, перезапустите бота
2. Отправьте 4 вопроса подряд
3. **Expected**: 4-й ответ — сообщение о лимите

### Scenario E: Reindex (P3)

1. Добавьте `knowledge/new-doc.md` с новым содержимым
2. Отправьте `/reindex` (admin)
3. Задайте вопрос по новому документу
4. **Expected**: корректный ответ из нового файла

---

## 7. Deploy smoke test (production)

После деплоя на Railway/Render:

```bash
curl -f https://<your-app>/health || python -m src.cli health
```

Отправьте `/start` боту — должен ответить в течение 5 секунd.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Bot не отвечает | `TELEGRAM_BOT_TOKEN`, процесс `bot run` запущен |
| «Нет доступа» | Ваш ID в `ALLOWED_USER_IDS` |
| Пустые ответы | `knowledge reindex`, файлы в `knowledge/` |
| API errors | `OPENROUTER_API_KEY`, баланс на OpenRouter |
| Медленные ответы | Размер базы, модель LLM |
