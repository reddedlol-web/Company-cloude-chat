# Research: Company Telegram Knowledge Bot

**Feature**: `001-company-telegram-bot`  
**Date**: 2026-06-26

## Decision 1: Язык и runtime

**Decision**: Python 3.11+

**Rationale**: Богатая экосистема для Telegram (aiogram), RAG (langchain/chroma), быстрая разработка MVP за 1–2 недели. Команда/исполнитель знаком с Python.

**Alternatives considered**:
- Node.js + telegraf — хорош для Telegram, но RAG-экосистема слабее
- Go — быстрее, но дольше разработка MVP

---

## Decision 2: Telegram framework

**Decision**: aiogram 3.x (long polling для MVP; webhook для production)

**Rationale**: Асинхронный, активно поддерживается, удобные middleware для auth и rate limiting.

**Alternatives considered**:
- python-telegram-bot — зрелый, но более verbose API
- Telethon — userbot, не нужен для Bot API

---

## Decision 3: RAG / vector store

**Decision**: ChromaDB (embedded, persistent) + langchain-text-splitters для chunking

**Rationale**: Бесплатно, без отдельного сервера БД, достаточно для ≤100 документов и 10–30 пользователей. Простой деплой на Railway/Render.

**Alternatives considered**:
- Pinecone — managed, но +$70/мес, overkill для MVP
- Supabase pgvector — хорош для масштаба, но лишняя инфраструктура на старте
- FAISS in-memory — теряет данные при рестарте без persistence

---

## Decision 4: Embeddings

**Decision**: OpenRouter → `text-embedding-3-small` (OpenAI-compatible)

**Rationale**: Единый провайдер с LLM, дёшево (~$0.02/1M tokens), хорошее качество для русского/английского.

**Alternatives considered**:
- Local sentence-transformers — бесплатно, но +500MB RAM, медленнее на CPU
- Cohere embed — отдельный API key

---

## Decision 5: LLM

**Decision**: OpenRouter → `openai/gpt-4o-mini` (primary), fallback `anthropic/claude-3-haiku`

**Rationale**: gpt-4o-mini — оптимальное соотношение цена/качество для Q&A (~$0.15/1M input). OpenRouter даёт единый API и fallback.

**Alternatives considered**:
- Claude Sonnet — лучше качество, дороже
- Local Llama — нужен GPU, сложнее ops

---

## Decision 6: Document parsing

**Decision**: `pypdf` для PDF, plain read для `.md`/`.txt`

**Rationale**: Минимальные зависимости, достаточно для v1.

**Alternatives considered**:
- Unstructured.io — мощнее, но тяжелее
- Docling — overkill для MVP

---

## Decision 7: Auth / access control

**Decision**: Whitelist Telegram user IDs в `.env` (`ALLOWED_USER_IDS=123,456,789`)

**Rationale**: Просто, прозрачно, достаточно для 10–30 сотрудников. Админ добавляет ID через env/config.

**Alternatives considered**:
- Telegram group-only access — проще для «все в группе», но сложнее контролировать лимиты per-user
- OAuth / корпоративный SSO — overkill для v1

---

## Decision 8: Rate limiting

**Decision**: In-memory + SQLite daily counter per user (persist across restarts)

**Rationale**: Нужна persistence при рестарте контейнера. SQLite — zero-config.

**Alternatives considered**:
- Redis — overkill для MVP
- Pure in-memory — теряет счётчики при рестарте

---

## Decision 9: Hosting

**Decision**: Railway или Render (Docker container, long polling)

**Rationale**: $5–10/мес, простой деплой из GitHub, persistent volume для Chroma + SQLite.

**Alternatives considered**:
- VPS (Hetzner) — дешевле, но больше ops
- Serverless — плохо для long polling + persistent vector store

---

## Decision 10: Project structure

**Decision**: Single Python package `src/` + `knowledge/` data dir + CLI entry points

**Rationale**: YAGNI — один сервис, без microservices. Соответствует масштабу MVP.

**Alternatives considered**:
- Monorepo backend+admin web — отложить на v2

---

## Resolved clarifications

| Topic | Resolution |
|---|---|
| Auth method | Telegram user ID whitelist |
| Retention | Query logs 30 days; no full question text by default |
| Supported formats v1 | `.md`, `.txt`, `.pdf` |
| Daily limit default | 20 questions/user/day |
| Primary language | Russian |
