# Data Model: Company Telegram Knowledge Bot

**Feature**: `001-company-telegram-bot`  
**Date**: 2026-06-26

## Overview

MVP использует два хранилища:
1. **ChromaDB** — embeddings и chunks документов (vector store)
2. **SQLite** — whitelist metadata, rate limits, query logs

Файловая система: `knowledge/` — исходные документы.

---

## Entity: Employee (logical, config + SQLite)

Представляет авторизованного сотрудника. Whitelist задаётся в env; runtime-данные — в SQLite.

| Field | Type | Required | Description |
|---|---|---|---|
| telegram_user_id | INTEGER | yes | PK, Telegram user ID |
| display_name | TEXT | no | Имя из Telegram profile |
| is_active | BOOLEAN | yes | default true |
| daily_limit | INTEGER | yes | default 20 |
| created_at | TIMESTAMP | yes | UTC |

**Validation**:
- `telegram_user_id` > 0
- `daily_limit` ≥ 1 and ≤ 100

---

## Entity: DailyUsage

Счётчик запросов сотрудника за календарный день (UTC).

| Field | Type | Required | Description |
|---|---|---|---|
| telegram_user_id | INTEGER | yes | FK → Employee |
| usage_date | DATE | yes | UTC date |
| query_count | INTEGER | yes | default 0 |

**Unique constraint**: `(telegram_user_id, usage_date)`

**State transitions**:
- New day → new row with `query_count = 0`
- Successful query → `query_count += 1`
- `query_count >= daily_limit` → reject with rate limit message

---

## Entity: Document (filesystem + metadata in SQLite)

| Field | Type | Required | Description |
|---|---|---|---|
| id | TEXT | yes | UUID or hash of path |
| file_path | TEXT | yes | Relative path under `knowledge/` |
| title | TEXT | yes | Display name (filename without ext) |
| format | ENUM | yes | `md`, `txt`, `pdf` |
| file_hash | TEXT | yes | SHA-256 для detect changes |
| chunk_count | INTEGER | yes | After indexing |
| status | ENUM | yes | `active`, `error`, `pending` |
| indexed_at | TIMESTAMP | no | Last successful index |
| error_message | TEXT | no | If status = error |

**Validation**:
- `file_path` must start with `knowledge/` and not contain `..`
- Supported extensions only: `.md`, `.txt`, `.pdf`

**Relationships**:
- Document 1 → N DocumentChunk (in ChromaDB, metadata links `document_id`)

---

## Entity: DocumentChunk (ChromaDB)

| Field | Type | Required | Description |
|---|---|---|---|
| id | TEXT | yes | Chroma document ID |
| document_id | TEXT | yes | FK → Document |
| chunk_index | INTEGER | yes | Order in document |
| content | TEXT | yes | Chunk text (512 tokens target) |
| embedding | VECTOR | yes | 1536-dim (text-embedding-3-small) |

**Metadata stored in Chroma**:
```json
{
  "document_id": "...",
  "document_title": "refund-policy",
  "chunk_index": 0,
  "source_path": "knowledge/refund-policy.md"
}
```

---

## Entity: QueryLog

| Field | Type | Required | Description |
|---|---|---|---|
| id | INTEGER | yes | PK autoincrement |
| telegram_user_id | INTEGER | yes | FK → Employee |
| timestamp | TIMESTAMP | yes | UTC |
| status | ENUM | yes | `success`, `rate_limited`, `unauthorized`, `no_answer`, `error` |
| tokens_input | INTEGER | no | LLM tokens |
| tokens_output | INTEGER | no | LLM tokens |
| sources_cited | TEXT | no | JSON array of document titles |
| latency_ms | INTEGER | no | End-to-end response time |

**Note**: Полный текст вопроса НЕ сохраняется по умолчанию (privacy).

---

## Entity: BotConfig (environment / .env)

| Variable | Type | Default | Description |
|---|---|---|---|
| TELEGRAM_BOT_TOKEN | secret | — | BotFather token |
| OPENROUTER_API_KEY | secret | — | LLM + embeddings |
| ALLOWED_USER_IDS | CSV | — | Whitelist |
| DAILY_QUERY_LIMIT | int | 20 | Global default per user |
| KNOWLEDGE_DIR | path | `./knowledge` | Documents root |
| CHROMA_PERSIST_DIR | path | `./data/chroma` | Vector store |
| SQLITE_PATH | path | `./data/bot.db` | SQLite DB |
| LLM_MODEL | string | `openai/gpt-4o-mini` | Primary model |
| EMBEDDING_MODEL | string | `openai/text-embedding-3-small` | Embeddings |
| TOP_K_CHUNKS | int | 5 | RAG retrieval count |

---

## Relationships Diagram

```text
Employee 1 ──< DailyUsage (per day)
Employee 1 ──< QueryLog

Document 1 ──< DocumentChunk (in ChromaDB)

knowledge/*.md ── indexed into ──> Document + DocumentChunk
```
