import logging

import chromadb

from src.config import Settings
from src.llm.openrouter import OpenRouterClient
from src.rag.indexer import COLLECTION_NAME

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    def __init__(self, settings: Settings, llm: OpenRouterClient) -> None:
        self.settings = settings
        self.llm = llm
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
        self.collection = client.get_or_create_collection(name=COLLECTION_NAME)

    async def retrieve(
        self, question: str
    ) -> tuple[list[dict[str, str | float | None]], float | None]:
        if self.collection.count() == 0:
            return [], None

        embedding = await self.llm.embed_one(question)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=self.settings.top_k_chunks,
        )

        chunks: list[dict[str, str | float | None]] = []
        documents = results.get("documents") or [[]]
        metadatas = results.get("metadatas") or [[]]
        distances = results.get("distances") or [[]]

        max_similarity: float | None = None
        for doc, meta, distance in zip(
            documents[0], metadatas[0], distances[0], strict=False
        ):
            if doc is None or meta is None:
                continue
            similarity = (
                max(0.0, 1.0 - float(distance)) if distance is not None else None
            )
            if similarity is not None and (
                max_similarity is None or similarity > max_similarity
            ):
                max_similarity = similarity
            if distance is not None and distance > 0.85:
                continue
            chunks.append(
                {
                    "content": doc,
                    "title": meta.get("document_title", "unknown"),
                    "source_path": meta.get("source_path", ""),
                    "distance": distance,
                    "similarity": similarity,
                }
            )
        return chunks, max_similarity

    @staticmethod
    def max_similarity(chunks: list[dict]) -> float | None:
        sims = [
            float(c["similarity"])
            for c in chunks
            if c.get("similarity") is not None
        ]
        return max(sims) if sims else None
