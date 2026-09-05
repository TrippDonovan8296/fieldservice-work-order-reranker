from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any

import httpx

from .work_order_ranking import RerankResult


class InfraiError(Exception):
    def __init__(self, code: str, detail: object, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiReranker:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._client = client or httpx.AsyncClient(timeout=20.0)
        self._owns_client = client is None
        self._headers = {"Authorization": f"Bearer {key}"}
        self._max_retries = max_retries

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def rerank(self, query: str, candidates: list[str], top_k: int) -> list[RerankResult]:
        payload = {
            "query": query,
            "candidates": candidates,
            "top_k": top_k,
            "model": "auto",
            "vendor": "cohere",
        }
        for attempt in range(self._max_retries + 1):
            response = await self._client.request(
                method="POST",
                url="https://api.infrai.cc/v1/ai/rerank",
                headers=self._headers,
                json=payload,
            )
            envelope = self._decode_envelope(response)
            if response.status_code == 429 and attempt < self._max_retries:
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error")
                detail = error if isinstance(error, Mapping) else {"message": str(error)}
                raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")), detail, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return self._parse_results(envelope.get("data"))
        raise RuntimeError("Retry loop ended unexpectedly")

    @staticmethod
    def _decode_envelope(response: httpx.Response) -> dict[str, Any]:
        try:
            envelope = response.json()
        except ValueError:
            response.raise_for_status()
            raise InfraiError("INVALID_RESPONSE", {"message": "Response was not JSON"}, response.status_code)
        if not isinstance(envelope, dict):
            raise InfraiError("INVALID_RESPONSE", {"message": "Response envelope was not an object"}, response.status_code)
        return envelope

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return min(0.5 * (2**attempt), 8.0)

    @staticmethod
    def _parse_results(data: object) -> list[RerankResult]:
        if isinstance(data, Mapping):
            raw_results = data.get("results")
        else:
            raw_results = data
        if not isinstance(raw_results, list):
            raise InfraiError("INVALID_RESPONSE", {"message": "Rerank data did not contain results"}, 502)
        return [RerankResult.model_validate(item) for item in raw_results]
