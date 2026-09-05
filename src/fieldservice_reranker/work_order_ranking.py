from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class WorkOrder(BaseModel):
    id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    photo_notes: list[str] = Field(default_factory=list)
    dispatch_status: str = Field(min_length=1)
    technician_follow_up: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    work_orders: list[WorkOrder] = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=20)


class RankedWorkOrder(BaseModel):
    work_order: WorkOrder
    relevance_score: float


class SearchResponse(BaseModel):
    query: str
    results: list[RankedWorkOrder]


class RerankResult(BaseModel):
    index: int
    relevance_score: float


class Reranker(Protocol):
    async def rerank(self, query: str, candidates: list[str], top_k: int) -> list[RerankResult]:
        raise RuntimeError("Reranker protocol methods are supplied by an implementation")


def describe_for_dispatch(order: WorkOrder) -> str:
    photos = "; ".join(order.photo_notes) if order.photo_notes else "none recorded"
    follow_up = order.technician_follow_up or "none recorded"
    return (
        f"work order {order.id}\n"
        f"problem: {order.summary}\n"
        f"photo observations: {photos}\n"
        f"dispatch status: {order.dispatch_status}\n"
        f"technician follow-up: {follow_up}"
    )


async def rank_work_orders(request: SearchRequest, reranker: Reranker) -> SearchResponse:
    candidates = [describe_for_dispatch(order) for order in request.work_orders]
    ranked = await reranker.rerank(request.query, candidates, min(request.top_k, len(candidates)))

    results: list[RankedWorkOrder] = []
    for item in ranked:
        if not 0 <= item.index < len(request.work_orders):
            raise ValueError("Rerank response referred to an unknown candidate index")
        results.append(
            RankedWorkOrder(
                work_order=request.work_orders[item.index],
                relevance_score=item.relevance_score,
            )
        )
    return SearchResponse(query=request.query, results=results)
