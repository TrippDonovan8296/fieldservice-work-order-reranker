import asyncio

import httpx
import pytest

from fieldservice_reranker.infrai_rerank import InfraiError, InfraiReranker


def test_business_rejection_is_decoded_before_http_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            400,
            json={
                "ok": False,
                "data": None,
                "error": {"code": "BAD_QUERY", "message": "Query needs more context"},
                "metadata": {},
            },
        )

    async def exercise_boundary() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            reranker = InfraiReranker("test-key", client=client, max_retries=0)
            await reranker.rerank("leak", ["candidate"], 1)

    with pytest.raises(InfraiError) as caught:
        asyncio.run(exercise_boundary())

    assert caught.value.code == "BAD_QUERY"
    assert caught.value.status_code == 400
