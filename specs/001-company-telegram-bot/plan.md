# Implementation Plan: Company Telegram Knowledge Bot

**Branch**: `001-company-telegram-bot` | **Date**: 2026-06-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-company-telegram-bot/spec.md`

## Summary

Корпоративный Telegram-бот: сотрудники задают вопросы → RAG-поиск по документам компании → ответ через OpenRouter LLM с указанием источника. Whitelist по Telegram ID, дневные лимиты, CLI для индексации. Python 3.11 + aiogram + ChromaDB + SQLite.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: aiogram 3.x, chromadb, httpx (OpenRouter client), pypdf, langchain-text-splitters, pydantic-settings

**Storage**: ChromaDB (vectors), SQLite (usage/logs), filesystem `knowledge/` (documents)

**Testing**: pytest, pytest-asyncio, pytest-mock

**Target Platform**: Linux container (Railway / Render / Docker)

**Project Type**: Single backend service (Telegram bot + CLI)

**Performance Goals**: ≤30s p95 response time for Q&A with ≤100 documents; support 10 concurrent users

**Constraints**: Budget $50–100/mo (API + hosting); no full question text in logs by default; Russian-primary

**Scale/Scope**: 10–30 employees, ~100 documents, ~200 queries/day max

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is in template state (not yet ratified via `/speckit-constitution`). Interim gates applied from project goals:

| Gate | Status | Notes |
|---|---|---|
| Simplicity (YAGNI) | ✅ PASS | Single Python service, no microservices, no admin web in v1 |
| Testability | ✅ PASS | Unit tests for RAG/auth/rate-limit; integration test with mocked LLM |
| Security | ✅ PASS | Whitelist auth, secrets in env, no question text in logs |
| Observability | ✅ PASS | Structured logging, QueryLog entity, `/health` CLI |
| Scope control | ✅ PASS | Telegram-only v1; `.md/.txt/.pdf` only; no Notion/GDrive sync |

**Post-design re-check**: All gates pass. No complexity violations requiring justification table.

## Project Structure

### Documentation (this feature)

```text
specs/001-company-telegram-bot/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── telegram-bot.md
│   └── cli.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── bot/
│   ├── __init__.py
│   ├── main.py              # aiogram app, polling
│   ├── handlers/
│   │   ├── messages.py      # Q&A handler
│   │   └── commands.py      # /start, /help, /limit, /reindex
│   └── middleware/
│       ├── auth.py          # whitelist check
│       └── rate_limit.py    # daily limit
├── rag/
│   ├── indexer.py           # document load + chunk + embed
│   ├── retriever.py         # semantic search
│   └── prompts.py           # system prompt templates
├── llm/
│   └── openrouter.py        # chat + embeddings client
├── db/
│   ├── models.py            # SQLite schema
│   └── repository.py        # usage + logs CRUD
├── config.py                # pydantic-settings
└── cli.py                   # bot run, knowledge reindex, health

knowledge/                   # company documents (gitignored content in prod)
data/                        # chroma + sqlite (gitignored)
tests/
├── unit/
│   ├── test_auth.py
│   ├── test_rate_limit.py
│   └── test_rag.py
└── integration/
    └── test_qa_flow.py

Dockerfile
docker-compose.yml
pyproject.toml
.env.example
```

**Structure Decision**: Single Python package under `src/`. Bot handlers, RAG, LLM, and DB as separate modules within one deployable service. Matches MVP scale and constitution simplicity gate.

## Complexity Tracking

> No violations — table not required.

## Implementation Phases (for /speckit-tasks)

### Phase A: Foundation
- Project scaffold (`pyproject.toml`, config, Docker)
- SQLite schema + Chroma init
- OpenRouter client (chat + embeddings)

### Phase B: RAG pipeline
- Document loaders (md, txt, pdf)
- Chunking + indexing CLI
- Retriever with top-K

### Phase C: Telegram bot
- aiogram setup, auth middleware, rate limit middleware
- Message handler (Q&A flow)
- Commands: /start, /help, /limit, /reindex

### Phase D: Polish & deploy
- Logging, health check, error handling
- Tests (unit + integration)
- Dockerfile + Railway/Render deploy config
- `.env.example` + quickstart validation

## Artifacts Generated

| Artifact | Path | Status |
|---|---|---|
| Feature spec | `specs/001-company-telegram-bot/spec.md` | ✅ |
| Research | `specs/001-company-telegram-bot/research.md` | ✅ |
| Data model | `specs/001-company-telegram-bot/data-model.md` | ✅ |
| Contracts | `specs/001-company-telegram-bot/contracts/` | ✅ |
| Quickstart | `specs/001-company-telegram-bot/quickstart.md` | ✅ |
| Tasks | `specs/001-company-telegram-bot/tasks.md` | ✅ |
