# Contract: CLI — Analytics

**Feature**: `003-admin-analytics`  
**Entrypoint**: `python -m src.cli`

## Subcommand: `report`

Generate analytics report (same logic as `/report` bot command).

### Syntax

```bash
python -m src.cli report --period {daily|weekly} [--numeric] [--force] [--dry-run]
```

### Options

| Flag | Description |
|---|---|
| `--period daily` | Report for previous UTC day (default) |
| `--period weekly` | Last 7 days |
| `--numeric` | Skip LLM summarization |
| `--force` | Regenerate even if report exists |
| `--dry-run` | Print to stdout, do not send Telegram / persist delivery |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Configuration error (missing DB, invalid period) |
| 2 | Report generation failed |

### Example output (dry-run)

```text
$ python -m src.cli report --period daily --dry-run
📊 Сводка за 28.06.2026
...
(delivery skipped: dry-run)
```

---

## Subcommand: `stats`

Print aggregated statistics to stdout (for cron/monitoring).

### Syntax

```bash
python -m src.cli stats [--period {today|week|month}] [--json]
```

### Options

| Flag | Description |
|---|---|
| `--period today` | Default |
| `--json` | Machine-readable output |

### JSON schema (example)

```json
{
  "period": "today",
  "total_queries": 23,
  "unique_users": 8,
  "tokens_input": 9100,
  "tokens_output": 3400,
  "by_status": {"success": 18, "no_answer": 3},
  "by_category": {"answered": 18, "off_topic": 2}
}
```

---

## Subcommand: `aggregate`

Roll up `query_logs` into `daily_stats` (maintenance).

### Syntax

```bash
python -m src.cli aggregate [--date YYYY-MM-DD] [--backfill N]
```

| Flag | Description |
|---|---|
| `--date` | Specific UTC date (default: yesterday) |
| `--backfill N` | Recompute last N days |

---

## Subcommand: `purge-analytics`

Delete expired `question_text` per retention policy.

### Syntax

```bash
python -m src.cli purge-analytics [--dry-run]
```

### Behavior

- NULL out `query_details.question_text` where `query_logs.timestamp` older than retention
- Keep `question_hash`, aggregates, reports

---

## Docker / cron integration

```yaml
# docker-compose.yml (example sidecar cron)
services:
  bot:
  analytics-cron:
    image: same as bot
    command: >
      sh -c "while true; do
        python -m src.cli aggregate --backfill 2;
        python -m src.cli purge-analytics;
        sleep 86400;
      done"
```

Or rely on in-process APScheduler (default).

---

## Environment

Requires same `.env` as bot: `SQLITE_PATH`, `TELEGRAM_BOT_TOKEN` (only for `report` delivery), `OPENROUTER_API_KEY` (for LLM summaries).

`report --dry-run` and `stats` work offline without Telegram token.
