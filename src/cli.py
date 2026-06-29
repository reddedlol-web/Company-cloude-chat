import argparse
import asyncio
import json
import logging
import sys

from src.analytics.aggregator import AnalyticsAggregator
from src.analytics.reporter import AnalyticsReporter
from src.bot.main import main_sync
from src.config import get_settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient
from src.logging_config import setup_logging
from src.rag.indexer import KnowledgeIndexer

logger = logging.getLogger(__name__)


def cmd_db_init(_: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    print(json.dumps({"status": "ok", "sqlite": str(settings.sqlite_path)}))
    return 0


async def cmd_health_async(_: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    llm = OpenRouterClient(settings)

    result = {
        "telegram": "ok" if settings.telegram_bot_token else "error",
        "openrouter": "ok" if await llm.health_check() else "error",
        "chroma": "ok",
        "sqlite": "ok",
    }

    try:
        repository.init_db()
        with repository.connect() as conn:
            conn.execute("SELECT 1")
    except Exception:
        result["sqlite"] = "error"

    try:
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        result["chroma"] = "error"

    print(json.dumps(result, ensure_ascii=False))
    return 0 if all(v == "ok" for v in result.values()) else 1


async def cmd_reindex_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    llm = OpenRouterClient(settings)
    indexer = KnowledgeIndexer(settings, repository, llm)
    result = await indexer.reindex(force=args.force)

    payload = {
        "status": result.status,
        "documents_indexed": result.documents_indexed,
        "chunks_created": result.chunks_created,
        "errors": result.errors,
        "removed_documents": result.removed_documents,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if result.documents_indexed == 0 and result.errors:
        return 1
    return 0


def cmd_knowledge_status(_: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    status = repository.get_index_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


async def cmd_report_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    llm = OpenRouterClient(settings)
    reporter = AnalyticsReporter(settings, repository, llm)

    try:
        result = await reporter.generate_report(
            args.period,
            numeric_only=args.numeric,
            force=args.force,
        )
    except Exception:
        logger.exception("Report generation failed")
        return 2

    for msg in result.messages:
        print(msg)
        print("---")

    if args.dry_run:
        print("(delivery skipped: dry-run)")
        return 0

    if not settings.telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN required for delivery", file=sys.stderr)
        return 1

    from aiogram import Bot
    from src.analytics.delivery import deliver_report

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await deliver_report(bot, settings, result.messages)
        if result.report_id:
            repository.mark_report_sent(result.report_id)
    finally:
        await bot.session.close()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    reporter = AnalyticsReporter(settings, repository)

    period = args.period or "today"
    if args.json:
        from src.analytics.aggregator import resolve_period

        agg = AnalyticsAggregator(repository)
        stats = agg.get_stats(resolve_period(period))  # type: ignore[arg-type]
        payload = {
            "period": period,
            "total_queries": stats["total_queries"],
            "unique_users": stats["unique_users"],
            "tokens_input": stats["tokens_input"],
            "tokens_output": stats["tokens_output"],
            "by_status": stats["by_status"],
            "by_category": stats.get("by_category", {}),
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(reporter.format_stats_message(period))
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    agg = AnalyticsAggregator(repository)

    if args.backfill:
        count = agg.backfill_daily_stats(args.backfill)
        print(json.dumps({"backfilled_days": count}))
        return 0

    from datetime import UTC, date, datetime, timedelta

    if args.date:
        day = date.fromisoformat(args.date)
    else:
        day = datetime.now(UTC).date() - timedelta(days=1)

    stats = agg.compute_daily_stats(day)
    print(json.dumps({"date": day.isoformat(), **stats}, ensure_ascii=False))
    return 0


def cmd_purge_analytics(args: argparse.Namespace) -> int:
    settings = get_settings()
    repository = Repository(settings.sqlite_path)
    repository.init_db()
    if args.dry_run:
        print(json.dumps({"dry_run": True, "would_purge": "question_text"}))
        return 0
    count = repository.purge_expired_question_text(
        settings.analytics_question_retention_days
    )
    print(json.dumps({"purged_rows": count}))
    return 0


def cmd_bot_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    setup_logging(settings)
    logging.getLogger().setLevel(
        getattr(logging, args.log_level.upper(), logging.INFO)
    )
    try:
        main_sync(settings)
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    db = sub.add_parser("db", help="Database commands")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init", help="Initialize SQLite schema")

    sub.add_parser("health", help="Check dependencies")

    knowledge = sub.add_parser("knowledge", help="Knowledge base commands")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    reindex = knowledge_sub.add_parser("reindex", help="Reindex knowledge base")
    reindex.add_argument("--force", action="store_true")
    knowledge_sub.add_parser("status", help="Indexing status")

    report = sub.add_parser("report", help="Generate analytics report")
    report.add_argument("--period", choices=["daily", "weekly"], default="daily")
    report.add_argument("--numeric", action="store_true")
    report.add_argument("--force", action="store_true")
    report.add_argument("--dry-run", action="store_true")

    stats = sub.add_parser("stats", help="Print analytics statistics")
    stats.add_argument("--period", choices=["today", "week", "month"], default="today")
    stats.add_argument("--json", action="store_true")

    aggregate = sub.add_parser("aggregate", help="Roll up daily_stats")
    aggregate.add_argument("--date", help="YYYY-MM-DD (default: yesterday UTC)")
    aggregate.add_argument("--backfill", type=int, metavar="N", help="Backfill N days")

    purge = sub.add_parser("purge-analytics", help="Purge expired question texts")
    purge.add_argument("--dry-run", action="store_true")

    bot = sub.add_parser("bot", help="Bot commands")
    bot_sub = bot.add_subparsers(dest="bot_command", required=True)
    bot_run = bot_sub.add_parser("run", help="Run Telegram bot")
    bot_run.add_argument("--log-level", default="INFO")

    args = parser.parse_args()

    if args.command == "db" and args.db_command == "init":
        sys.exit(cmd_db_init(args))
    if args.command == "health":
        sys.exit(asyncio.run(cmd_health_async(args)))
    if args.command == "knowledge" and args.knowledge_command == "reindex":
        sys.exit(asyncio.run(cmd_reindex_async(args)))
    if args.command == "knowledge" and args.knowledge_command == "status":
        sys.exit(cmd_knowledge_status(args))
    if args.command == "report":
        sys.exit(asyncio.run(cmd_report_async(args)))
    if args.command == "stats":
        sys.exit(cmd_stats(args))
    if args.command == "aggregate":
        sys.exit(cmd_aggregate(args))
    if args.command == "purge-analytics":
        sys.exit(cmd_purge_analytics(args))
    if args.command == "bot" and args.bot_command == "run":
        sys.exit(cmd_bot_run(args))

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
