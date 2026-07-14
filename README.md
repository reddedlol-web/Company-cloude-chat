# Company-cloude-chat

Корпоративный Telegram-бот с базой знаний компании (RAG + OpenRouter).

**Ветка:** `004-bossfree-kb-sync`

## Стек

- Python 3.11, aiogram 3, ChromaDB, SQLite, OpenRouter
- Документы: `knowledge/` (`.md`, `.txt`, `.pdf`), в т.ч. выгрузка Boss Free → `knowledge/bossfree/`

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, ALLOWED_USER_IDS
# Для sync из Boss Free: BOSSFREE_EMAIL, BOSSFREE_PASSWORD

python -m src.cli db init
# опционально: выгрузка статей из Boss Free
python -m src.cli knowledge sync-bossfree
python -m src.cli knowledge reindex
python -m src.cli bot run
```

## CLI

| Команда | Описание |
|---|---|
| `python -m src.cli db init` | Инициализация SQLite |
| `python -m src.cli knowledge sync-bossfree [--force] [--dry-run]` | Выгрузка статей Boss Free в `knowledge/bossfree/` |
| `python -m src.cli knowledge reindex` | Индексация документов |
| `python -m src.cli knowledge status` | Статус базы |
| `python -m src.cli health` | Проверка зависимостей |
| `python -m src.cli bot run` | Запуск Telegram-бота |
| `python -m src.cli stats [--period today\|week\|month] [--json]` | Статистика использования |
| `python -m src.cli report --period daily\|weekly [--numeric] [--dry-run]` | Сводка для админа |
| `python -m src.cli aggregate [--backfill N]` | Агрегация daily_stats |
| `python -m src.cli purge-analytics` | Очистка текстов вопросов по retention |

## Telegram-команды

- `/start` — приветствие и лимит
- `/help` — справка
- `/limit` — остаток запросов на сегодня
- `/reindex` — переиндексация (только admin)
- `/invite` — создать приглашение (admin); опционально `label=... password=... days=7 uses=5`
- `/invites` — список приглашений с кнопками отзыва (admin)
- `/users`, `/user <id>`, `/user block|unblock <id>` — пользователи (admin)
- `/stats` — статистика (admin): `/stats week`, `/stats month`
- `/report` — сводка (admin): `/report daily`, `/report weekly --numeric`
- `/userstats <telegram_id>` — аналитика по пользователю (admin)

## Docker

```bash
docker compose up --build
```

## Документация

- [Feature spec (001)](specs/001-company-telegram-bot/spec.md)
- [Onboarding spec (002)](specs/002-admin-onboarding/spec.md)
- [Analytics spec (003)](specs/003-admin-analytics/spec.md)
- [Boss Free sync (004)](specs/004-bossfree-kb-sync/spec.md)
- [Boss Free sync quickstart](specs/004-bossfree-kb-sync/quickstart.md)
- [Implementation plan](specs/004-bossfree-kb-sync/plan.md)
- [Analytics quickstart](specs/003-admin-analytics/quickstart.md)
- [Quickstart](specs/001-company-telegram-bot/quickstart.md)
- [Deploy](docs/deploy.md)
- [Варианты реализации](docs/implementation-options.md)

## Тесты

```bash
pytest
```
