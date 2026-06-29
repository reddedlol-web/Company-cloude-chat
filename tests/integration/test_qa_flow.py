from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import ChatResult


@pytest.mark.asyncio
async def test_qa_flow_retrieve_and_chat(tmp_path):
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        ALLOWED_USER_IDS="1",
        KNOWLEDGE_DIR=tmp_path / "knowledge",
        CHROMA_PERSIST_DIR=tmp_path / "chroma",
        SQLITE_PATH=tmp_path / "bot.db",
    )
    repo = Repository(settings.sqlite_path)
    repo.init_db()

    chunks = [{"title": "vacation-policy", "content": "28 days vacation"}]

    with patch("src.rag.retriever.KnowledgeRetriever.retrieve", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = (chunks, 0.9)
        with patch("src.llm.openrouter.OpenRouterClient.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = ChatResult(
                content="You get 28 days.",
                tokens_input=10,
                tokens_output=5,
            )

            from src.rag.retriever import KnowledgeRetriever
            from src.llm.openrouter import OpenRouterClient

            retriever = MagicMock(spec=KnowledgeRetriever)
            retriever.retrieve = mock_retrieve
            llm = OpenRouterClient(settings)
            llm.chat = mock_chat

            result_chunks, _sim = await retriever.retrieve("сколько отпуска?")
            assert len(result_chunks) == 1
            chat_result = await llm.chat("system", "user")
            assert "28" in chat_result.content

            repo.log_query(
                user_id=1,
                status="success",
                tokens_input=chat_result.tokens_input,
                tokens_output=chat_result.tokens_output,
                sources=["vacation-policy"],
            )
            with repo.connect() as conn:
                row = conn.execute("SELECT status FROM query_logs").fetchone()
            assert row["status"] == "success"
