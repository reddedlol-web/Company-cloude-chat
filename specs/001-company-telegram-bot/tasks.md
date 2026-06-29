# Tasks: Company Telegram Knowledge Bot

**Input**: Design documents from `/specs/001-company-telegram-bot/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Не запрошены в spec (TDD не обязателен). Unit/integration тесты — в финальной фазе Polish по plan.md.

**Organization**: Задачи сгруппированы по user story для независимой реализации и проверки.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Можно выполнять параллельно (разные файлы, нет зависимостей от незавершённых задач)
- **[Story]**: US1, US2, US3 — привязка к user story из spec.md
- В описании указан точный путь к файлу

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Инициализация проекта и базовая структура

- [x] T001 Create project directory structure per plan.md (`src/bot/`, `src/rag/`, `src/llm/`, `src/db/`, `tests/unit/`, `tests/integration/`, `knowledge/`, `data/`)
- [x] T002 Create `pyproject.toml` with Python 3.11+, aiogram, chromadb, httpx, pypdf, langchain-text-splitters, pydantic-settings, pytest dependencies
- [x] T003 Create `.env.example` with all BotConfig variables from data-model.md
- [x] T004 [P] Update `.gitignore` to exclude `data/`, `.env`, `.venv/`, `__pycache__/`, `*.pyc`
- [x] T005 [P] Add demo knowledge documents in `knowledge/refund-policy.md` and `knowledge/vacation-policy.md`
- [x] T006 [P] Create `Dockerfile` and `docker-compose.yml` for bot service with persistent `data/` volume

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Инфраструктура, блокирующая все user stories

**⚠️ CRITICAL**: User stories не начинаются, пока Phase 2 не завершена

- [x] T007 Implement pydantic Settings in `src/config.py` (env vars: tokens, whitelist, paths, models, limits)
- [x] T008 Implement SQLite schema for Document, DailyUsage, QueryLog in `src/db/models.py`
- [x] T009 Implement repository CRUD in `src/db/repository.py` (init_db, document metadata, query logs)
- [x] T010 [P] Implement OpenRouter chat + embeddings client in `src/llm/openrouter.py`
- [x] T011 [P] Implement system/user prompt templates per contract in `src/rag/prompts.py`
- [x] T012 Implement document loaders (.md, .txt, .pdf) and text chunking in `src/rag/indexer.py`
- [x] T013 Implement ChromaDB collection init and embedding storage in `src/rag/indexer.py`
- [x] T014 Implement top-K semantic retriever in `src/rag/retriever.py`
- [x] T015 Implement CLI subcommands `db init`, `health`, `knowledge reindex`, `knowledge status` in `src/cli.py`
- [x] T016 Configure structured logging (JSON/text, log level from env) in `src/logging_config.py`

**Checkpoint**: Foundation ready — RAG pipeline и CLI reindex работают; user story implementation can begin

---

## Phase 3: User Story 1 — Задать вопрос и получить ответ (Priority: P1) 🎯 MVP

**Goal**: Сотрудник из whitelist задаёт вопрос в Telegram → RAG + LLM → ответ с источниками; отказ для неавторизованных и при отсутствии данных в базе

**Independent Test**: Загрузить 3–5 документов в `knowledge/`, выполнить `knowledge reindex`, задать вопрос с известным ответом — бот отвечает ≤30 сек с названием источника; неавторизованный пользователь получает отказ

### Implementation for User Story 1

- [x] T017 [US1] Implement whitelist auth middleware in `src/bot/middleware/auth.py`
- [x] T018 [US1] Implement Q&A text message handler (retrieve → LLM → reply) in `src/bot/handlers/messages.py`
- [x] T019 [US1] Implement `/start` and `/help` commands per contract in `src/bot/handlers/commands.py`
- [x] T020 [US1] Wire aiogram Bot, Dispatcher, routers, auth middleware in `src/bot/main.py`
- [x] T021 [US1] Implement `bot run` CLI subcommand with long polling in `src/cli.py`
- [x] T022 [US1] Persist QueryLog entries (status, tokens, sources, latency) in `src/bot/handlers/messages.py`
- [x] T023 [US1] Handle edge cases: message >2000 chars, no chunks found, LLM API error in `src/bot/handlers/messages.py`

**Checkpoint**: User Story 1 fully functional — MVP ready for demo

---

## Phase 4: User Story 2 — Ограничение использования (Priority: P2)

**Goal**: Дневной лимит запросов на сотрудника (default 20/день), команда `/limit`, сообщение при исчерпании

**Independent Test**: Установить `DAILY_QUERY_LIMIT=3`, отправить 4 вопроса — 4-й получает сообщение о лимите; `/limit` показывает used/limit

### Implementation for User Story 2

- [x] T024 [US2] Implement DailyUsage increment and quota check in `src/db/repository.py`
- [x] T025 [US2] Implement rate limit middleware in `src/bot/middleware/rate_limit.py`
- [x] T026 [US2] Register rate limit middleware after auth in `src/bot/main.py`
- [x] T027 [US2] Implement `/limit` command per contract in `src/bot/handlers/commands.py`
- [x] T028 [US2] Update `/start` response to show remaining daily quota in `src/bot/handlers/commands.py`

**Checkpoint**: User Stories 1 AND 2 work independently

---

## Phase 5: User Story 3 — Обновление базы знаний (Priority: P3)

**Goal**: Админ переиндексирует базу через CLI или `/reindex`; новые документы доступны, удалённые — исключены

**Independent Test**: Добавить `knowledge/new-doc.md`, выполнить reindex (CLI или `/reindex`), задать вопрос по новому содержимому — корректный ответ; удалить файл, reindex — старый контент не используется

### Implementation for User Story 3

- [x] T029 [US3] Add `ADMIN_USER_IDS` to `src/config.py` and admin check helper in `src/bot/middleware/auth.py`
- [x] T030 [US3] Implement removal of orphaned Chroma chunks and Document rows on reindex in `src/rag/indexer.py`
- [x] T031 [US3] Implement admin-only `/reindex` command with progress reply in `src/bot/handlers/commands.py`
- [x] T032 [US3] Add per-file error collection and admin notification for failed PDFs in `src/rag/indexer.py`

**Checkpoint**: All user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Тесты, деплой, документация, финальная валидация

- [x] T033 [P] Add unit tests for auth whitelist in `tests/unit/test_auth.py`
- [x] T034 [P] Add unit tests for daily rate limit in `tests/unit/test_rate_limit.py`
- [x] T035 [P] Add unit tests for indexer/retriever in `tests/unit/test_rag.py`
- [x] T036 Add integration test for Q&A flow with mocked OpenRouter in `tests/integration/test_qa_flow.py`
- [x] T037 Add deploy section (Railway/Render, env vars, persistent volume) in `docs/deploy.md`
- [x] T038 Run all scenarios from `specs/001-company-telegram-bot/quickstart.md` and fix gaps
- [x] T039 Update `README.md` with install, configure, reindex, and run instructions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **User Stories (Phase 3–5)**: Depend on Phase 2
  - Recommended order: US1 → US2 → US3
  - US2/US3 can start after US1 checkpoint if staffed in parallel
- **Polish (Phase 6)**: Depends on desired user stories complete (minimum US1 for MVP deploy)

### User Story Dependencies

- **US1 (P1)**: Requires Foundational only — no dependency on US2/US3
- **US2 (P2)**: Requires US1 bot wiring (middleware stack in `main.py`); independently testable via `/limit` and 4th-message scenario
- **US3 (P3)**: Requires Foundational indexer; bot `/reindex` requires US1 bot setup + admin config

### Within Each User Story

- Middleware before handlers that depend on it
- Handlers before CLI `bot run` integration
- Core Q&A before edge-case handling (T018 before T023)

### Parallel Opportunities

**Phase 1** — parallel after T003:
- T004, T005, T006

**Phase 2** — parallel after T009:
- T010, T011 (while T012–T014 proceed sequentially on indexer/retriever)

**Phase 3** — parallel after T020:
- T022, T023 (same file — sequential; T019 parallel with T017 if different devs)

**Phase 6** — parallel:
- T033, T034, T035

---

## Parallel Example: User Story 1

```bash
# After T016 complete, two developers can split:
# Dev A: T017 auth middleware → T020 main.py wiring
# Dev B: T018 messages handler → T019 commands (needs T017 for integration test)

# After T020, sequentially on same handler file:
# T022 QueryLog → T023 edge cases
```

---

## Parallel Example: Foundational

```bash
# Launch together after T009:
Task T010: "Implement OpenRouter client in src/llm/openrouter.py"
Task T011: "Implement prompt templates in src/rag/prompts.py"

# Then sequential RAG chain:
Task T012 → T013 → T014 → T015
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundational (T007–T016)
3. Complete Phase 3: User Story 1 (T017–T023)
4. **STOP and VALIDATE**: quickstart scenarios A, B, C
5. Deploy demo for заказчик

### Incremental Delivery

1. Setup + Foundational → RAG + CLI ready
2. US1 → Q&A MVP → **Deploy/Demo**
3. US2 → rate limits → Deploy
4. US3 → admin reindex → Deploy
5. Polish → tests + production hardening

### Suggested MVP Scope

**Minimum shippable**: Phase 1 + Phase 2 + Phase 3 (T001–T023)

Delivers: Telegram Q&A with auth, sources, anti-hallucination, demo knowledge base.

**Defer to v1.1**: US2 rate limits (if budget not critical for pilot), US3 bot reindex (CLI reindex sufficient for pilot).

---

## Notes

- Commit after each phase checkpoint
- `ALLOWED_USER_IDS` and `OPENROUTER_API_KEY` required before first `bot run`
- Run `python -m src.cli knowledge reindex` before any Q&A test
- Rate limit middleware (US2) intentionally omitted from MVP scope — add before production with 10+ users
