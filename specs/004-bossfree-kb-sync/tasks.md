---
description: "Task list for Boss Free knowledge sync feature"
---

# Tasks: Синхронизация Boss Free → локальный RAG

**Input**: Design documents from `/specs/004-bossfree-kb-sync/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit/integration по plan.md (mock HTTP, без прод Boss Free в CI). Не TDD-first, но тесты — часть сдачи feature.

**Organization**: Задачи сгруппированы по user story (US1–US3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Можно выполнять параллельно (разные файлы, нет зависимостей от незавершённых задач)
- **[Story]**: Привязка к user story (US1–US3)

## Path Conventions

- Single project: `src/`, `tests/`, `knowledge/` в корне репозитория

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Зависимости и каркас пакета интеграции

- [x] T001 Add `markdownify` (or bs4+html2text) dependency in `pyproject.toml` (httpx уже есть)
- [x] T002 [P] Create package scaffold `src/integrations/__init__.py` and `src/integrations/bossfree/__init__.py`
- [x] T003 [P] Document `BOSSFREE_EMAIL`, `BOSSFREE_PASSWORD`, `BOSSFREE_BASE_URL`, `BOSSFREE_ORIGIN` in `.env.example` (без секретов)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Конфиг и утилиты, без которых нельзя писать sync/CLI

**⚠️ CRITICAL**: User story work не начинается до завершения этой фазы

- [x] T004 Add Boss Free settings fields (`bossfree_email`, `bossfree_password`, `bossfree_base_url`, `bossfree_origin`) in `src/config.py` (password/email optional at Settings load so bot start without them; required only by sync CLI)
- [x] T005 [P] Implement safe path/slug helpers and category path builder in `src/integrations/bossfree/paths.py`
- [x] T006 [P] Implement HTML→Markdown converter (keep text; images/links as MD URLs; strip scripts) in `src/integrations/bossfree/html_to_markdown.py`
- [x] T007 [P] Define dataclasses / report shape (`SyncReport`, article DTOs) in `src/integrations/bossfree/models.py` per `data-model.md`

**Checkpoint**: Foundation ready — конфиг и чистые функции конвертации/путей доступны

---

## Phase 3: User Story 1 — Оператор выгружает статьи Boss Free (Priority: P1) 🎯 MVP

**Goal**: CLI `knowledge sync-bossfree` логинится в API, качает статьи, пишет Markdown в `knowledge/bossfree/`, печатает JSON SyncReport

**Independent Test**: С валидными credentials команда создаёт ≥1 `.md` и JSON с `written`/`skipped_*`/`errors`; при плохом пароле — exit 1 без порчи файлов

### Implementation for User Story 1

- [x] T008 [US1] Implement Boss Free HTTP client (login with Bearer+cookies, `list_categories`, `list_posts`, `get_post_by_slug`, timeouts, no token logging) in `src/integrations/bossfree/client.py`
- [x] T009 [US1] Implement Markdown file writer with YAML frontmatter (`bossfree_id`, `slug`, `updated_at`, `source_url`, `category_path`) and `# {title}` body in `src/integrations/bossfree/writer.py`
- [x] T010 [US1] Implement sync orchestrator (list → fetch → convert → skip unchanged by `updated_at` unless `--force` → per-article write; collect errors) in `src/integrations/bossfree/sync.py`
- [x] T011 [US1] Wire CLI `knowledge sync-bossfree` with `--force` / `--dry-run`, exit codes 0/1/2, JSON stdout per `contracts/cli.md` in `src/cli.py`
- [x] T012 [P] [US1] Add unit tests for paths + HTML→MD in `tests/unit/test_bossfree_paths.py` and `tests/unit/test_bossfree_html_to_markdown.py`
- [x] T013 [US1] Add unit/integration tests for sync with mocked HTTP (unchanged skip, login failure) in `tests/unit/test_bossfree_sync.py` and/or `tests/integration/test_bossfree_sync_flow.py`

**Checkpoint**: Sync CLI работает independently от бота/reindex

---

## Phase 4: User Story 2 — Индексация и ответ бота по статьям (Priority: P1)

**Goal**: После sync существующий `reindex` подхватывает `knowledge/bossfree/**/*.md`; citations показывают человекочитаемый title статьи

**Independent Test**: Sync тестовой статьи → `knowledge reindex` → retrieve/question по теме даёт чанки с title статьи (не только slug)

### Implementation for User Story 2

- [x] T014 [US2] Ensure `KnowledgeIndexer` discovers nested `knowledge/bossfree/**/*.md` (verify `rglob` in `src/rag/indexer.py`; fix only if broken)
- [x] T015 [US2] Prefer document title from first Markdown `# ` heading (fallback `path.stem`) when indexing in `src/rag/indexer.py`
- [x] T016 [US2] Add unit/regression test for title-from-H1 indexing behavior in `tests/unit/test_indexer_title.py` (or extend existing indexer tests)
- [x] T017 [US2] Update operator notes: sync → reindex sequence in `docs/deploy.md` and/or `specs/004-bossfree-kb-sync/quickstart.md` (коротко, без дублирования secrets)

**Checkpoint**: End-to-end RAG по Boss Free файлам без изменения Telegram handlers

---

## Phase 5: User Story 3 — Пустые и медиа-only статьи (Priority: P2)

**Goal**: Пустые/почти пустые статьи не роняют sync; считаются `skipped_empty`; статьи с текстом+картинками сохраняют текст и MD-ссылки на медиа

**Independent Test**: Mock empty `content` → report `skipped_empty ≥ 1`, остальные written; HTML с `<img>` → MD содержит URL, текст не потерян

### Implementation for User Story 3

- [x] T018 [US3] Enforce empty threshold (`text_plain_len < 50` → `skipped_empty`, no file / no indexer poison) in `src/integrations/bossfree/sync.py` (and helper in `html_to_markdown.py` if needed)
- [x] T019 [US3] Ensure image/iframe/video become markdown links/images without failing convert in `src/integrations/bossfree/html_to_markdown.py`
- [x] T020 [US3] Extend sync tests for empty skip + media HTML fixtures in `tests/unit/test_bossfree_sync.py` and `tests/unit/test_bossfree_html_to_markdown.py`

**Checkpoint**: Sync устойчив к «дырявому» контенту Boss Free

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Документация, безопасность, ручная валидация

- [x] T021 [P] Confirm no credentials/tokens in logged exceptions; redact in `src/integrations/bossfree/client.py` / sync error messages
- [x] T022 [P] Add brief section to `README.md` pointing to Boss Free sync + quickstart
- [x] T023 Run `specs/004-bossfree-kb-sync/quickstart.md` validation manually (sync → reindex → sample Q&A) and fix gaps if found
- [x] T024 [P] Ensure `knowledge/bossfree/` policy documented (commit vs gitignore) in `openclaw/workspace/knowledge/README.md` or `knowledge/` README — one short note

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Старт сразу
- **Foundational (Phase 2)**: После Setup — **блокирует** все user stories
- **US1 (Phase 3)**: После Foundational — MVP
- **US2 (Phase 4)**: После US1 (нужны файлы + indexer title) — можно начинать T014/T015 сразу после того как формат MD из US1 стабилен
- **US3 (Phase 5)**: Логически уточняет sync из US1; можно частично параллельно с US2 после T010
- **Polish (Phase 6)**: После нужных stories

### User Story Dependencies

- **US1 (P1)**: Только Foundational
- **US2 (P1)**: Нужен успешный sync format из US1; не меняет CLI sync
- **US3 (P2)**: Усиливает US1 sync policy; независимо тестируется моками

### Within Each Story

- Client/writer before orchestrator before CLI
- Core behavior before tests that lock it
- Indexer title fix before claiming good citations

### Parallel Opportunities

- T002 ∥ T003
- T005 ∥ T006 ∥ T007 (после T004 или параллельно с ним, если settings не нужны утилитам)
- T012 ∥ частично с T011 после стабилизации API surfaces
- T014–T016 (US2) ∥ T018–T020 (US3) после готовности T010
- T021 ∥ T022 ∥ T024

---

## Parallel Example: User Story 1

```bash
# После T007:
Task: "Implement client in src/integrations/bossfree/client.py"
# затем writer, затем sync (последовательно)

# Параллельно после стабилизации convert/paths:
Task: "Unit tests in tests/unit/test_bossfree_paths.py"
Task: "Unit tests in tests/unit/test_bossfree_html_to_markdown.py"
```

---

## Parallel Example: After US1 core sync

```bash
Task: "Indexer title-from-H1 in src/rag/indexer.py"          # US2
Task: "Empty threshold + media links in sync/html_to_md"    # US3
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundational
3. Phase 3 US1 → **STOP**: проверить `sync-bossfree` на реальном tenant
4. Demo: файлы в `knowledge/bossfree/`

### Incremental Delivery

1. US1 → выгрузка работает
2. US2 → reindex + citations по title → бот отвечает по БЗ
3. US3 → аккуратный skip пустых
4. Polish → docs + quickstart pass

### Suggested MVP scope

**T001–T013 (Setup + Foundational + US1)** — достаточно, чтобы наполнить `knowledge/bossfree/`.  
Для ценности заказчику в Telegram сразу добавить **US2 (T014–T017)** в том же заходе.

---

## Notes

- Не добавлять `/sync_kb` и live Boss Free search (FR-010)
- Не коммитить `.env` с паролем; JWT не писать в MD/логи
- Auto-delete локальных файлов при удалении в Boss Free — out of MVP
- OCR картинок — out of MVP
