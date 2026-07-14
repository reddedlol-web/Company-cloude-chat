import logging
from collections import defaultdict

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

        seed_chunks: list[dict[str, str | float | None]] = []
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
            seed_chunks.append(self._chunk_dict(doc, meta, distance, similarity))

        if not seed_chunks:
            return [], max_similarity

        expanded = self._expand_same_documents(seed_chunks)
        return expanded, max_similarity

    def _chunk_dict(
        self,
        doc: str,
        meta: dict,
        distance: float | None,
        similarity: float | None,
    ) -> dict[str, str | float | None]:
        return {
            "content": doc,
            "title": meta.get("document_title", "unknown"),
            "source_path": meta.get("source_path", ""),
            "source_url": meta.get("source_url") or "",
            "document_id": meta.get("document_id", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "distance": distance,
            "similarity": similarity,
        }

    def _expand_same_documents(
        self, seed_chunks: list[dict[str, str | float | None]]
    ) -> list[dict[str, str | float | None]]:
        """Pull neighboring/all chunks from the best-matching source documents."""
        best_sim: dict[str, float] = {}
        for chunk in seed_chunks:
            doc_id = str(chunk.get("document_id") or "")
            if not doc_id:
                continue
            sim = float(chunk.get("similarity") or 0.0)
            if doc_id not in best_sim or sim > best_sim[doc_id]:
                best_sim[doc_id] = sim

        ranked_doc_ids = sorted(
            best_sim.keys(), key=lambda d: best_sim[d], reverse=True
        )[: self.settings.max_expand_docs]

        by_doc: dict[str, list[dict[str, str | float | None]]] = defaultdict(list)
        for doc_id in ranked_doc_ids:
            try:
                got = self.collection.get(where={"document_id": doc_id})
            except Exception:
                logger.exception("Failed expanding document_id=%s", doc_id)
                continue
            docs = got.get("documents") or []
            metas = got.get("metadatas") or []
            for doc, meta in zip(docs, metas, strict=False):
                if doc is None or meta is None:
                    continue
                by_doc[doc_id].append(
                    self._chunk_dict(
                        doc,
                        meta,
                        distance=None,
                        similarity=best_sim.get(doc_id),
                    )
                )

        for doc_id in by_doc:
            by_doc[doc_id].sort(
                key=lambda c: int(c.get("chunk_index") or 0)  # type: ignore[arg-type]
            )

        expanded: list[dict[str, str | float | None]] = []
        for doc_id in ranked_doc_ids:
            for chunk in by_doc.get(doc_id, []):
                expanded.append(chunk)
                if len(expanded) >= self.settings.max_context_chunks:
                    return expanded

        # Fallback: if expand failed, return seeds
        return expanded or seed_chunks

    @staticmethod
    def max_similarity(chunks: list[dict]) -> float | None:
        sims = [
            float(c["similarity"])
            for c in chunks
            if c.get("similarity") is not None
        ]
        return max(sims) if sims else None
