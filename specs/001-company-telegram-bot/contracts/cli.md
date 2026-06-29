# Contract: CLI Commands

**Feature**: `001-company-telegram-bot`  
**Version**: 1.0.0

## Entry point

```bash
python -m src.cli <command>
```

Or via `poetry run` / `uv run` after project setup.

---

## `bot run`

Start Telegram bot (long polling).

**Options**:
| Flag | Default | Description |
|---|---|---|
| `--log-level` | `INFO` | Logging level |

**Exit codes**:
- `0` — graceful shutdown
- `1` — config error or fatal startup failure

**Required env**: `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `ALLOWED_USER_IDS`

---

## `knowledge reindex`

Reindex all documents in `KNOWLEDGE_DIR`.

**Options**:
| Flag | Default | Description |
|---|---|---|
| `--force` | false | Reindex even if file hash unchanged |

**Stdout (success)**:
```json
{
  "status": "ok",
  "documents_indexed": 12,
  "chunks_created": 87,
  "errors": []
}
```

**Stdout (partial failure)**:
```json
{
  "status": "partial",
  "documents_indexed": 11,
  "chunks_created": 80,
  "errors": [
    {"file": "knowledge/broken.pdf", "error": "Failed to parse PDF"}
  ]
}
```

**Exit codes**:
- `0` — success or partial with at least one doc indexed
- `1` — no documents indexed or fatal error

---

## `knowledge status`

Show indexing status.

**Stdout**:
```json
{
  "total_documents": 12,
  "active": 11,
  "errors": 1,
  "total_chunks": 87,
  "last_reindex_at": "2026-06-26T10:00:00Z"
}
```

---

## `db init`

Initialize SQLite schema.

**Exit code**: `0` on success (idempotent — safe to run multiple times).

---

## `health`

Check dependencies connectivity.

**Stdout**:
```json
{
  "telegram": "ok",
  "openrouter": "ok",
  "chroma": "ok",
  "sqlite": "ok"
}
```

**Exit codes**:
- `0` — all checks pass
- `1` — one or more checks failed
