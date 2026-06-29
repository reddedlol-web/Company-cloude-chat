# Company-cloude-chat

Корпоративный Telegram-бот с базой знаний компании (RAG + OpenRouter).

**Ветка:** `001-company-telegram-bot`

## Стек

- Python 3.11, aiogram 3, ChromaDB, SQLite, OpenRouter
- Документы: `knowledge/` (`.md`, `.txt`, `.pdf`)

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, ALLOWED_USER_IDS

python -m src.cli db init
python -m src.cli knowledge reindex
python -m src.cli bot run
```

## CLI

| Команда | Описание |
|---|---|
| `python -m src.cli db init` | Инициализация SQLite |
| `python -m src.cli knowledge reindex` | Индексация документов |
| `python -m src.cli knowledge status` | Статус базы |
| `python -m src.cli health` | Проверка зависимостей |
| `python -m src.cli bot run` | Запуск Telegram-бота |

## Telegram-команды

- `/start` — приветствие и лимит
- `/help` — справка
- `/limit` — остаток запросов на сегодня
- `/reindex` — переиндексация (только admin)

## Docker

```bash
docker compose up --build
```

## Документация

- [Feature spec](specs/001-company-telegram-bot/spec.md)
- [Implementation plan](specs/001-company-telegram-bot/plan.md)
- [Quickstart](specs/001-company-telegram-bot/quickstart.md)
- [Deploy](docs/deploy.md)
- [Варианты реализации](docs/implementation-options.md)

## Тесты

```bash
pytest
```
