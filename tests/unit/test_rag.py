from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag.prompts import build_user_prompt, format_sources_html


def test_build_user_prompt_includes_sources() -> None:
    chunks = [
        {"title": "refund-policy", "content": "14 days return window"},
    ]
    prompt = build_user_prompt("How long to return?", chunks)
    assert "refund-policy" in prompt
    assert "14 days" in prompt
    assert "How long to return?" in prompt


def test_build_user_prompt_includes_source_url() -> None:
    chunks = [
        {
            "title": "Наши ценности",
            "source_url": "https://topix.bossfree.pro/post/nashi-cennosti",
            "content": "1. Трушность",
        }
    ]
    prompt = build_user_prompt("ценности?", chunks)
    assert "https://topix.bossfree.pro/post/nashi-cennosti" in prompt


def test_format_sources_html_links() -> None:
    chunks = [
        {
            "title": "Наши ценности",
            "source_url": "https://topix.bossfree.pro/post/nashi-cennosti",
        },
        {
            "title": "Наши ценности",
            "source_url": "https://topix.bossfree.pro/post/nashi-cennosti",
        },
        {"title": "О компании", "source_url": ""},
    ]
    line = format_sources_html(chunks)
    assert 'href="https://topix.bossfree.pro/post/nashi-cennosti"' in line
    assert ">Наши ценности</a>" in line
    assert "О компании" in line


def test_build_user_prompt_empty_context() -> None:
    prompt = build_user_prompt("test?", [])
    assert "no context" in prompt


def test_chunking_splits_long_text() -> None:
    splitter = RecursiveCharacterTextSplitter(chunk_size=50, chunk_overlap=10)
    text = "word " * 100
    chunks = splitter.split_text(text)
    assert len(chunks) > 1


def test_knowledge_dir_discovery(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "a.md").write_text("# Test\nHello", encoding="utf-8")
    (knowledge / "b.txt").write_text("Plain text", encoding="utf-8")
    files = list(knowledge.rglob("*"))
    supported = [f for f in files if f.suffix in {".md", ".txt", ".pdf"}]
    assert len(supported) == 2
