# Knowledge base

Документы для RAG Telegram-бота (`.md`, `.txt`, `.pdf`).

## Boss Free sync

Выгрузка из корпоративной БЗ Boss Free (tenant TOPIX) пишется в `knowledge/bossfree/`:

```bash
python -m src.cli knowledge sync-bossfree
python -m src.cli knowledge reindex
```

Файлы можно коммитить в private repo или держать только на сервере (volume). Секреты (`BOSSFREE_*`) — только в `.env`, не в Markdown.

См. `specs/004-bossfree-kb-sync/quickstart.md`.
