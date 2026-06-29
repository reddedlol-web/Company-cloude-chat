FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data

VOLUME ["/app/data", "/app/knowledge"]

ENV KNOWLEDGE_DIR=/app/knowledge
ENV CHROMA_PERSIST_DIR=/app/data/chroma
ENV SQLITE_PATH=/app/data/bot.db

CMD ["python", "-m", "src.cli", "bot", "run"]
