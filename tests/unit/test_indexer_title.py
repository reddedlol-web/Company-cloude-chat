from pathlib import Path

from src.rag.indexer import KnowledgeIndexer


def test_title_from_markdown_h1() -> None:
    text = "# Отпуск / отгул за свой счет\n\nТело документа."
    assert (
        KnowledgeIndexer._title_from_markdown(text, fallback="slug")
        == "Отпуск / отгул за свой счет"
    )


def test_title_from_markdown_fallback() -> None:
    text = "Just a paragraph without heading."
    assert KnowledgeIndexer._title_from_markdown(text, fallback="otpusk") == "otpusk"


def test_strip_frontmatter_keeps_body() -> None:
    raw = "---\nslug: \"x\"\n---\n\n# Title\n\nBody"
    stripped = KnowledgeIndexer._strip_yaml_frontmatter(raw)
    assert stripped.lstrip().startswith("# Title")
    assert "slug" not in stripped


def test_discover_nested_bossfree(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    nested = knowledge / "bossfree" / "company" / "policies"
    nested.mkdir(parents=True)
    (nested / "otpusk.md").write_text("# Отпуск\n\nText", encoding="utf-8")
    (knowledge / "root.md").write_text("# Root\n\nText", encoding="utf-8")

    class _Dummy:
        pass

    indexer = KnowledgeIndexer.__new__(KnowledgeIndexer)
    indexer.settings = _Dummy()  # type: ignore[assignment]
    indexer.settings.knowledge_dir = knowledge  # type: ignore[attr-defined]
    files = KnowledgeIndexer._discover_files(indexer)
    rels = {p.relative_to(knowledge).as_posix() for p in files}
    assert "bossfree/company/policies/otpusk.md" in rels
    assert "root.md" in rels
