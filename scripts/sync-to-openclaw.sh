#!/usr/bin/env bash
# Синхронизация workspace и конфига из репозитория в ~/.openclaw/
# Использование: ./scripts/sync-to-openclaw.sh
# Для AutoClaw: загрузи содержимое openclaw/workspace/ через их UI / SSH (см. docs)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
SRC="$REPO_ROOT/openclaw"

echo "→ OpenClaw home: $OPENCLAW_HOME"

mkdir -p "$OPENCLAW_HOME/workspace"

# Workspace (knowledge, SOUL, AGENTS)
rsync -av --delete \
  "$SRC/workspace/" \
  "$OPENCLAW_HOME/workspace/"

# Конфиг — только если ещё нет (не перезаписываем прод)
if [[ ! -f "$OPENCLAW_HOME/openclaw.json" ]]; then
  cp "$SRC/openclaw.json.example" "$OPENCLAW_HOME/openclaw.json"
  echo "✓ Создан $OPENCLAW_HOME/openclaw.json из шаблона — отредактируй allowFrom и groups"
else
  echo "• openclaw.json уже есть — не трогаем (сравни с openclaw.json.example вручную)"
fi

# .env
if [[ ! -f "$OPENCLAW_HOME/.env" ]]; then
  cp "$SRC/.env.example" "$OPENCLAW_HOME/.env"
  echo "✓ Создан $OPENCLAW_HOME/.env — вставь TELEGRAM_BOT_TOKEN и OPENROUTER_API_KEY"
else
  echo "• .env уже есть — не трогаем"
fi

echo ""
echo "Готово. Дальше:"
echo "  1. Отредактируй $OPENCLAW_HOME/.env"
echo "  2. Отредактируй $OPENCLAW_HOME/openclaw.json (allowFrom, groups)"
echo "  3. openclaw gateway"
echo "  4. Напиши боту в Telegram и проверь ответы по knowledge/"
