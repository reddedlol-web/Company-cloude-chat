# Quickstart: Boss Free → RAG

**Feature**: `004-bossfree-kb-sync`  
**Date**: 2026-07-14

## Goal

Проверить end-to-end: статьи из Boss Free → Markdown → reindex → ответ бота по теме из БЗ.

## Prerequisites

- Python env проекта (как для 001)
- Аккаунт Boss Free с доступом к статьям (роль Пользователь ок)
- Telegram-бот и LLM ключи уже настроены (001)

## Setup

1. В `.env`:

```env
BOSSFREE_EMAIL=...
BOSSFREE_PASSWORD=...
# optional:
# BOSSFREE_BASE_URL=https://topix.bossfree.pro/api
# BOSSFREE_ORIGIN=https://topix.bossfree.pro
KNOWLEDGE_DIR=./knowledge
```

2. Имена переменных без значений — в `.env.example`.

## Sync

```bash
python -m src.cli knowledge sync-bossfree
```

Expected: exit 0, JSON со `written` > 0 (или `skipped_unchanged` на повторном прогоне), файлы в `knowledge/bossfree/**/*.md`.

Повтор без изменений:

```bash
python -m src.cli knowledge sync-bossfree
# skipped_unchanged ≈ числу ранее выгруженных
```

Force:

```bash
python -m src.cli knowledge sync-bossfree --force
```

## Index

```bash
python -m src.cli knowledge reindex
```

Expected: `documents_indexed` включает bossfree-файлы, `chunks_created` > 0 для новых/изменённых.

## Validate Q&A

1. Запустить бота как обычно.
2. Задать вопрос по известной статье, например отпуск / корпоративная почта / 1С карта клиента.
3. Ожидание: ответ по сути статьи + источник (title/slug документа).

## Failure checks

| Case | Expect |
|---|---|
| Неверный пароль | exit 1, понятная ошибка, файлы не стёрты |
| Нет сети | errors / exit non-zero, частичные writes ок |
| Пустая статья | `skipped_empty`, остальной sync продолжается |

## Tests (dev)

```bash
pytest tests/unit/test_bossfree_html_to_markdown.py tests/unit/test_bossfree_paths.py tests/unit/test_bossfree_sync.py -q
pytest tests/integration/test_bossfree_sync_flow.py -q
```

Не бить прод Boss Free из CI: только mocks.
