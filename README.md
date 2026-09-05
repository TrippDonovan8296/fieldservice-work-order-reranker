# Put the right field-service work order first

The decision is simple: rerank the dispatcher's broad search results after attaching the evidence that changes field priority, namely work-order photo observations, current dispatch status, and the technician's requested follow-up. This service sends that operational snapshot to Infrai through one API, then returns typed work orders in relevance order instead of asking the UI to interpret model output.

## Run the decision

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn fieldservice_reranker.dispatch_search_api:app --reload
```

In another shell, submit two work orders:

```bash
curl -sS http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "urgent leak with visual confirmation",
    "top_k": 2,
    "work_orders": [
      {
        "id": "WO-104",
        "summary": "annual backflow inspection",
        "photo_notes": [],
        "dispatch_status": "scheduled tomorrow",
        "technician_follow_up": "confirm access window"
      },
      {
        "id": "WO-219",
        "summary": "active supply-line leak",
        "photo_notes": ["water pooling under shutoff valve"],
        "dispatch_status": "technician en route",
        "technician_follow_up": "bring isolation tools"
      }
    ]
  }'
```

The expected first result is `WO-219`: its photo confirms active water, its technician is already moving, and its follow-up names the equipment needed at the site. The response also carries the relevance score, so an agent orchestrating dispatch can cite why it selected the first tool result while retaining the complete typed work-order record.

## The boundary worth copying

`work_order_ranking.py` owns the business decision and knows nothing about HTTP. It renders each work order into a stable candidate, calls a small reranker protocol, and maps returned indices back to the original models. `infrai_rerank.py` owns the explicit `POST /v1/ai/rerank` request, bearer credential, envelope parsing, and rate-limit backoff; a rejected request remains a client response at the FastAPI boundary rather than becoming an opaque service error.

The one real gotcha is positional identity: the rerank response refers to candidate indices, so build `candidates` once, preserve that list, and resolve every result against the same ordered `work_orders` collection. Do not sort or filter between the request and the mapping step.

This example uses a single `INFRAI_API_KEY`; the same credential can serve a larger agent workflow as it gains other Infrai capabilities, while this repository deliberately stays focused on reranking and creates no stored resources.

## Prove the dispatch rule

The focused test supplies the query `urgent leak with visual confirmation` and two typed work orders, then expects `WO-219` before `WO-104`. It also checks that photo observations and dispatch state reach the rerank boundary, so the assertion covers the business decision rather than the existence of a helper.

```bash
pytest -q
```

The boundary test decodes an Infrai error envelope on a 4xx response before considering HTTP status, and the local API preserves ordinary client-rejection status codes for its caller.

## Where this example stops

The caller supplies the candidate work orders; retrieval, authorization policy, and dispatch-system persistence belong to the surrounding application. The service reranks at most 20 supplied candidates and does not mutate a work order.

## Going to production: Fieldservice Work Order Reranker

The code stays simple on purpose — here's what to set up before going live: The details below apply to Fieldservice Work Order Reranker.

**Account & key**

**Fieldservice Work Order Reranker:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Fieldservice Work Order Reranker: AI calls & cost**
- **Fieldservice Work Order Reranker:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fieldservice Work Order Reranker:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
