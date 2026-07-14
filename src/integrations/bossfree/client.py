from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from src.integrations.bossfree.models import BossFreeArticleFull, BossFreeArticleListItem

logger = logging.getLogger(__name__)


class BossFreeAuthError(Exception):
    """Login failed or credentials missing."""


class BossFreeClient:
    """HTTP client for Boss Free common/* endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        password: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._timeout = timeout
        self._client: httpx.Client | None = None
        self._access_token: str = ""

    def __enter__(self) -> BossFreeClient:
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "company-cloude-chat-bossfree-sync/0.1",
            },
        )
        return self

    def __exit__(self, *args: object) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("BossFreeClient must be used as a context manager")
        return self._client

    def login(self) -> None:
        client = self._http()
        try:
            response = client.post(
                "/login",
                json={"login": self.email, "password": self.password},
                headers={"Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise BossFreeAuthError(f"Boss Free login request failed: {exc}") from exc

        if response.status_code >= 400:
            raise BossFreeAuthError(
                f"Boss Free login failed (HTTP {response.status_code})"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise BossFreeAuthError("Boss Free login returned non-JSON") from exc

        access = data.get("accessToken") or ""
        refresh = data.get("refreshToken") or ""
        if not access:
            raise BossFreeAuthError("Boss Free login missing accessToken")

        self._access_token = access
        client.cookies.set("accessToken", access)
        if refresh:
            client.cookies.set("refreshToken", refresh)
        logger.info("Boss Free login ok (user_id=%s)", (data.get("user") or {}).get("id"))

    def _auth_headers(self) -> dict[str, str]:
        if not self._access_token:
            raise BossFreeAuthError("Not authenticated")
        return {"Authorization": f"Bearer {self._access_token}"}

    def _get_json(self, path: str) -> Any:
        client = self._http()
        response = client.get(path, headers=self._auth_headers())
        response.raise_for_status()
        return response.json()

    def list_categories(self) -> list[dict[str, Any]]:
        data = self._get_json("/common/category")
        if not isinstance(data, list):
            raise RuntimeError("Unexpected /common/category payload")
        return data

    def list_posts(self) -> list[BossFreeArticleListItem]:
        data = self._get_json("/common/posts")
        if not isinstance(data, list):
            raise RuntimeError("Unexpected /common/posts payload")
        items: list[BossFreeArticleListItem] = []
        for raw in data:
            items.append(
                BossFreeArticleListItem(
                    id=int(raw["id"]),
                    title=str(raw.get("title") or ""),
                    slug=str(raw.get("slug") or ""),
                    category_id=int(raw.get("category_id") or 0),
                    sort=int(raw.get("sort") or 0),
                )
            )
        return items

    def get_post_by_slug(self, slug: str) -> BossFreeArticleFull:
        # Slugs are URL-safe transliterations; quote for safety.
        encoded = quote(slug, safe="-_.~")
        data = self._get_json(f"/common/posts/{encoded}")
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected post payload for slug={slug!r}")
        category = data.get("category") or []
        if not isinstance(category, list):
            category = []
        return BossFreeArticleFull(
            id=int(data["id"]),
            title=str(data.get("title") or ""),
            slug=str(data.get("slug") or slug),
            category_id=int(data.get("category_id") or 0),
            content=str(data.get("content") or ""),
            updated_at=str(data.get("updated_at") or ""),
            category=category,
        )
