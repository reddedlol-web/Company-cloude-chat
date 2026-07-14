# Implementation Plan: Синхронизация Boss Free → локальный RAG

**Branch**: `004-bossfree-kb-sync` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-bossfree-kb-sync/spec.md`

## Summary

Выгрузка статей корпоративной базы знаний Boss Free (`topix.bossfree.pro`) в Markdown под `knowledge/bossfree/`, затем индексация существующим `KnowledgeIndexer` / Chroma. Telegram Q&A не меняется: бот по-прежнему ищет по локальным чанкам. MVP — CLI `knowledge sync-bossfree` (без live API на вопрос и без `/sync_kb`).

## Technical Context

**Language/Version**: Python 3.11+ (как в 001/002/003)

**Primary Dependencies**: существующие `httpx`/`urllib` или `httpx` для HTTP; HTML→text/Markdown (stdlib `html.parser` + лёгкая очистка, либо `markdownify`/`beautifulsoup4` если уже/минимально добавим); существующие Chroma + langchain_text_splitters + aiogram (без изменений в hot path)

**Storage**: файловая система `knowledge/bossfree/**/*.md`; метаданные sync — frontmatter в MD (+ опционально лёгкий `.sync-meta.json` рядом, если нужен для skip без парсинга всех MD); SQLite/Chroma — через существующий reindex

**Testing**: pytest — unit (HTML→MD, безопасные имена файлов, skip empty/unchanged), integration с mock HTTP Boss Free API (не ходить в прод в CI)

**Target Platform**: тот же Docker/VPS, где крутится бот; sync — ручной CLI или позже cron на хосте

**Project Type**: расширение single backend service (CLI + integration module)

**Performance Goals**: полный sync ≤74 статей ~2–3 мин при нормальной сети; повторный sync без изменений — существенно быстрее (только list + compare `updated_at`)

**Constraints**: credentials только в env; не хранить JWT в git/логах; частичные ошибки fetch не откатывают уже записанные файлы; картинки без OCR в MVP

**Scale/Scope**: ~74 статьи сейчас, порядок сотен статей приемлем; 1 tenant (`topix`); 1 service-аккаунт

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution в template-состоянии. Interim gates из 001–003:

| Gate | Status | Notes |
|---|---|---|
| Simplicity (YAGNI) | ✅ PASS | Только sync→files→reindex; no `/sync_kb`, no live retrieval |
| Testability | ✅ PASS | HTML transform + client mockable |
| Security | ✅ PASS | Env secrets; no credentials in MD; JWT не логировать |
| Observability | ✅ PASS | SyncReport JSON на stdout |
| Privacy | ✅ PASS | Корпоративный контент БЗ, уже доступен аккаунту |
| Scope control | ✅ PASS | Не дублируем UI Boss Free; не BI |

**Post-design re-check**: Gates pass. Внешний undocumentated API — риск, mitigated research + mock fixtures + явные контракты эндпоинтов.

## Project Structure

### Documentation (this feature)

```text
specs/004-bossfree-kb-sync/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── cli.md           # sync-bossfree command
└── tasks.md             # Phase 2 (/speckit-tasks) — NOT created here
```

### Source Code (changes to existing layout)

```text
src/
├── config.py                      # + BOSSFREE_* settings
├── cli.py                         # + knowledge sync-bossfree
└── integrations/
    └── bossfree/
        ├── __init__.py
        ├── client.py              # login, list categories/posts, get by slug
        ├── html_to_markdown.py    # content HTML → MD body
        ├── paths.py               # category path + safe filenames
        └── sync.py                # orchestrate write + SyncReport

knowledge/
└── bossfree/                      # generated (gitignored или частично tracked — см. research)
    └── ...

tests/
├── unit/
│   ├── test_bossfree_html_to_markdown.py
│   ├── test_bossfree_paths.py
│   └── test_bossfree_sync.py
└── integration/
    └── test_bossfree_sync_flow.py # mock HTTP

.env.example                       # BOSSFREE_EMAIL, BOSSFREE_PASSWORD, BOSSFREE_BASE_URL
```

**Structure Decision**: новый пакет `src/integrations/bossfree/` рядом с RAG; indexer/retriever/handlers не трогаем в MVP кроме документация quickstart «sync → reindex».

## Complexity Tracking

> Нет нарушений, требующих justification.
