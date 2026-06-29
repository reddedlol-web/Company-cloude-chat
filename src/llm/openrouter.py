import logging
from dataclasses import dataclass

import httpx

from src.config import Settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


@dataclass
class ChatResult:
    content: str
    tokens_input: int
    tokens_output: int


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/company-cloude-chat",
            "X-Title": "Company Knowledge Bot",
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self.settings.embedding_model, "input": texts}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE}/embeddings",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        items = sorted(data["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]

    async def embed_one(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0]

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        payload: dict = {
            "model": model or self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ChatResult(
            content=choice.strip(),
            tokens_input=int(usage.get("prompt_tokens", 0)),
            tokens_output=int(usage.get("completion_tokens", 0)),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{OPENROUTER_BASE}/models",
                    headers=self.headers,
                )
                return response.status_code == 200
        except httpx.HTTPError:
            logger.exception("OpenRouter health check failed")
            return False
