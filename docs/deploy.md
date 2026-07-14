# Deploy: Company Telegram Knowledge Bot

## Railway

1. Create a new project from GitHub repo `Company-cloude-chat`
2. Add **persistent volume** mounted at `/app/data`
3. Set environment variables from `.env.example`
4. Start command: `python -m src.cli bot run`
5. After deploy, run one-off command: `python -m src.cli db init && python -m src.cli knowledge reindex`

### Required env vars

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `OPENROUTER_API_KEY` | From openrouter.ai |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs |
| `ADMIN_USER_IDS` | Admin IDs for `/reindex`, `/invite`, `/users` |
| `BOT_USERNAME` | Bot @handle for invite links (optional; auto from getMe) |
| `ADMIN_NOTIFY_CHAT_ID` | Chat for new user registration alerts |
| `INVITE_DEFAULT_DAYS` | Invite expiry (default 7) |
| `INVITE_DEFAULT_MAX_USES` | Default max redemptions per invite |
| `KNOWLEDGE_DIR` | `/app/knowledge` (mount or bake into image) |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma` |
| `SQLITE_PATH` | `/app/data/bot.db` |

### Analytics (optional, feature 003)

| Variable | Description |
|---|---|
| `ANALYTICS_STORE_QUESTIONS` | Save truncated question text (default `true`) |
| `ANALYTICS_REPORT_CHAT_ID` | Telegram chat for scheduled reports |
| `ANALYTICS_SCHEDULE_ENABLED` | Enable APScheduler daily/weekly reports |
| `ANALYTICS_DAILY_CRON` | UTC cron, default `0 18 * * *` |
| `ANALYTICS_WEEKLY_CRON` | UTC cron, default `0 9 * * 1` |
| `ANALYTICS_DASHBOARD_ENABLED` | Optional HTML dashboard (`pip install '.[dashboard]'`) |

## Render

1. Create **Background Worker** (not Web Service — bot uses long polling)
2. Build: `pip install .`
3. Start: `python -m src.cli bot run`
4. Add disk at `/app/data` for Chroma + SQLite persistence

## Docker (VPS)

```bash
cp .env.example .env
# fill in secrets

docker compose build
docker compose run --rm bot python -m src.cli db init
docker compose run --rm bot python -m src.cli knowledge reindex
docker compose up -d
```

## Updating knowledge base

### From Boss Free (TOPIX)

1. Set `BOSSFREE_EMAIL` / `BOSSFREE_PASSWORD` in `.env` (see `.env.example`).
2. Sync articles into `knowledge/bossfree/`:

```bash
python -m src.cli knowledge sync-bossfree
# docker:
docker compose run --rm bot python -m src.cli knowledge sync-bossfree
```

3. Reindex:

```bash
python -m src.cli knowledge reindex
```

Details: [specs/004-bossfree-kb-sync/quickstart.md](../specs/004-bossfree-kb-sync/quickstart.md).

### Manual / local files

- **CLI** (recommended): `python -m src.cli knowledge reindex`
- **Telegram** (admin): send `/reindex` to the bot

Mount `knowledge/` as a volume if documents are updated without redeploying the image.

## Health check

```bash
python -m src.cli health
```

All fields should return `"ok"` (OpenRouter requires valid API key and network).

## Analytics maintenance

```bash
# On-demand stats / report
python -m src.cli stats --period week
python -m src.cli report --period daily --dry-run

# Backfill daily aggregates + retention
python -m src.cli aggregate --backfill 7
python -m src.cli purge-analytics
```

Scheduled reports run inside the bot process when `ANALYTICS_SCHEDULE_ENABLED=true`.
