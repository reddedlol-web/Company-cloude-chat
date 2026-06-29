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
| `ADMIN_USER_IDS` | Admin IDs for `/reindex` |
| `KNOWLEDGE_DIR` | `/app/knowledge` (mount or bake into image) |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma` |
| `SQLITE_PATH` | `/app/data/bot.db` |

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

- **CLI** (recommended): `python -m src.cli knowledge reindex`
- **Telegram** (admin): send `/reindex` to the bot

Mount `knowledge/` as a volume if documents are updated without redeploying the image.

## Health check

```bash
python -m src.cli health
```

All fields should return `"ok"` (OpenRouter requires valid API key and network).
