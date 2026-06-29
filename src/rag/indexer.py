import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}
COLLECTION_NAME = "company_knowledge"


@dataclass
class ReindexResult:
    status: str
    documents_indexed: int
    chunks_created: int
    errors: list[dict[str, str]] = field(default_factory=list)
    removed_documents: list[str] = field(default_factory=list)


class KnowledgeIndexer:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        llm: OpenRouterClient,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.llm = llm
        self.settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def _doc_id(self, rel_path: str) -> str:
        return hashlib.sha256(rel_path.encode()).hexdigest()[:16]

    def _file_hash(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _load_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            return path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        raise ValueError(f"Unsupported format: {suffix}")

    def _discover_files(self) -> list[Path]:
        root = self.settings.knowledge_dir
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
            return []
        files: list[Path] = []
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
        return files

    def _rel_path(self, path: Path) -> str:
        rel = path.relative_to(self.settings.knowledge_dir)
        return f"knowledge/{rel.as_posix()}"

    async def reindex(self, force: bool = False) -> ReindexResult:
        files = self._discover_files()
        seen_paths: set[str] = set()
        chunks_created = 0
        documents_indexed = 0
        errors: list[dict[str, str]] = []

        for path in files:
            rel_path = self._rel_path(path)
            seen_paths.add(rel_path)
            doc_id = self._doc_id(rel_path)
            title = path.stem

            try:
                file_hash = self._file_hash(path)
                with self.repository.connect() as conn:
                    row = conn.execute(
                        "SELECT file_hash, status FROM documents WHERE id = ?",
                        (doc_id,),
                    ).fetchone()
                if (
                    not force
                    and row
                    and row["file_hash"] == file_hash
                    and row["status"] == "active"
                ):
                    documents_indexed += 1
                    continue

                text = self._load_text(path).strip()
                if not text:
                    raise ValueError("Document is empty")

                chunks = self.splitter.split_text(text)
                if not chunks:
                    raise ValueError("No chunks produced")

                # Remove old chunks for this document
                self._delete_document_chunks(doc_id)

                embeddings = await self.llm.embed(chunks)
                ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
                metadatas = [
                    {
                        "document_id": doc_id,
                        "document_title": title,
                        "chunk_index": i,
                        "source_path": rel_path,
                    }
                    for i in range(len(chunks))
                ]
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=chunks,
                    metadatas=metadatas,
                )

                self.repository.upsert_document(
                    doc_id=doc_id,
                    file_path=rel_path,
                    title=title,
                    fmt=path.suffix.lower().lstrip("."),
                    file_hash=file_hash,
                    chunk_count=len(chunks),
                    status="active",
                )
                documents_indexed += 1
                chunks_created += len(chunks)
            except Exception as exc:
                logger.exception("Failed to index %s", rel_path)
                errors.append({"file": rel_path, "error": str(exc)})
                self.repository.upsert_document(
                    doc_id=doc_id,
                    file_path=rel_path,
                    title=title,
                    fmt=path.suffix.lower().lstrip("."),
                    file_hash="",
                    chunk_count=0,
                    status="error",
                    error_message=str(exc),
                )

        removed = await self._remove_orphans(seen_paths)

        status = "ok"
        if errors and documents_indexed == 0:
            status = "error"
        elif errors:
            status = "partial"

        return ReindexResult(
            status=status,
            documents_indexed=documents_indexed,
            chunks_created=chunks_created,
            errors=errors,
            removed_documents=removed,
        )

    async def _remove_orphans(self, seen_paths: set[str]) -> list[str]:
        removed_paths = self.repository.delete_documents_not_in(seen_paths)
        for rel_path in removed_paths:
            doc_id = self._doc_id(rel_path)
            self._delete_document_chunks(doc_id)
        return removed_paths

    def _delete_document_chunks(self, doc_id: str) -> None:
        try:
            existing = self.collection.get(where={"document_id": doc_id})
            if existing["ids"]:
                self.collection.delete(ids=existing["ids"])
        except Exception:
            logger.exception("Failed deleting chunks for %s", doc_id)
