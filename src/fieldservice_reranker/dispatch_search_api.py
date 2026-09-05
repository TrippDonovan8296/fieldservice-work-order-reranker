from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from .infrai_rerank import InfraiError, InfraiReranker
from .work_order_ranking import SearchRequest, SearchResponse, rank_work_orders


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.reranker = InfraiReranker()
    yield
    await app.state.reranker.close()


app = FastAPI(title="Field-service dispatch search", lifespan=lifespan)


@app.post("/search", response_model=SearchResponse)
async def search_work_orders(body: SearchRequest, request: Request) -> SearchResponse:
    try:
        return await rank_work_orders(body, request.app.state.reranker)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
