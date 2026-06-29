SYSTEM_PROMPT = """You are a corporate knowledge assistant. Answer ONLY based on the provided context.
If the context does not contain the answer, say "В предоставленных документах нет информации по этому вопросу."
Do not invent facts. Respond in the same language as the user's question.
Cite source document titles when answering."""


def build_user_prompt(question: str, chunks: list[dict[str, str]]) -> str:
    if not chunks:
        return f"Context:\n---\n(no context)\n---\n\nUser question: {question}"

    parts = []
    for chunk in chunks:
        parts.append(
            f"[Source: {chunk['title']}]\n{chunk['content']}\n---"
        )
    context_block = "\n".join(parts)
    return f"Context:\n---\n{context_block}\n\nUser question: {question}"
