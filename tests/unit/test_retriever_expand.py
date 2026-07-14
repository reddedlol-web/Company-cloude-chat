from __future__ import annotations

from unittest.mock import MagicMock

from src.config import Settings
from src.rag.retriever import KnowledgeRetriever


def test_expand_same_documents_pulls_all_chunks() -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        TOP_K_CHUNKS=5,
        MAX_EXPAND_DOCS=2,
        MAX_CONTEXT_CHUNKS=12,
    )
    retriever = KnowledgeRetriever.__new__(KnowledgeRetriever)
    retriever.settings = settings
    retriever.llm = MagicMock()

    collection = MagicMock()
    collection.get.return_value = {
        "documents": ["часть 1 ценность 1-3", "часть 2 ценность 4-7"],
        "metadatas": [
            {
                "document_id": "docA",
                "document_title": "Наши ценности",
                "chunk_index": 0,
                "source_path": "knowledge/bossfree/nashi.md",
                "source_url": "https://topix.bossfree.pro/post/nashi-cennosti",
            },
            {
                "document_id": "docA",
                "document_title": "Наши ценности",
                "chunk_index": 1,
                "source_path": "knowledge/bossfree/nashi.md",
                "source_url": "https://topix.bossfree.pro/post/nashi-cennosti",
            },
        ],
    }
    retriever.collection = collection

    seed = [
        {
            "content": "часть 1 ценность 1-3",
            "title": "Наши ценности",
            "document_id": "docA",
            "chunk_index": 0,
            "similarity": 0.9,
            "source_url": "https://topix.bossfree.pro/post/nashi-cennosti",
        }
    ]
    expanded = retriever._expand_same_documents(seed)
    assert len(expanded) == 2
    assert "ценность 4-7" in str(expanded[1]["content"])
    assert expanded[0]["source_url"].startswith("https://")
