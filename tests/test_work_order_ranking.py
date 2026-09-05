import asyncio

import pytest

from fieldservice_reranker.work_order_ranking import (
    RerankResult,
    SearchRequest,
    WorkOrder,
    rank_work_orders,
)


class DispatchAwareStub:
    async def rerank(self, query: str, candidates: list[str], top_k: int) -> list[RerankResult]:
        assert query == "urgent leak with visual confirmation"
        assert "photo observations: water pooling under shutoff valve" in candidates[1]
        assert "dispatch status: technician en route" in candidates[1]
        assert top_k == 2
        return [
            RerankResult(index=1, relevance_score=0.97),
            RerankResult(index=0, relevance_score=0.31),
        ]


def test_dispatch_context_changes_the_visible_work_order_order() -> None:
    request = SearchRequest(
        query="urgent leak with visual confirmation",
        top_k=2,
        work_orders=[
            WorkOrder(
                id="WO-104",
                summary="annual backflow inspection",
                dispatch_status="scheduled tomorrow",
                technician_follow_up="confirm access window",
            ),
            WorkOrder(
                id="WO-219",
                summary="active supply-line leak",
                photo_notes=["water pooling under shutoff valve"],
                dispatch_status="technician en route",
                technician_follow_up="bring isolation tools",
            ),
        ],
    )

    response = asyncio.run(rank_work_orders(request, DispatchAwareStub()))

    assert [item.work_order.id for item in response.results] == ["WO-219", "WO-104"]
    assert response.results[0].relevance_score == pytest.approx(0.97)
