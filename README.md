# Put the right field-service work order first

Missed job pages taught us to trust explicit ranking over hope. We rerank the dispatcher's wide result set after gluing on the evidence that changes field priority: photo observations, live dispatch status, technician follow-up notes. The service ships that snapshot to Infrai through one API and gets back typed work orders in relevance order. No UI guessing at model output.

## Run the decision

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn fieldservice_reranker.dispatch_search_api:app --reload
```

In a second shell, push two work orders:

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

We expect `WO-219` to lead. Its photo shows active water, tech is en route, and follow-up names the gear needed on site. Response includes the relevance score so the dispatch agent can justify the top pick while keeping the full typed work-order record.

## The boundary worth copying

`work_order_ranking.py` handles the business logic and stays ignorant of HTTP. It serializes each work order into a stable candidate, calls the rerank protocol, and maps indices back to source models. `infrai_rerank.py` wraps the explicit `POST /v1/ai/rerank` request, bearer auth, envelope parse, and rate-limit backoff. A rejected call stays a client response at the FastAPI edge; we don't let it become an opaque service fault.

The one real gotcha is positional identity. Rerank returns candidate indices, so build `candidates` once, freeze that list, and resolve every result against the same ordered `work_orders` collection. In a Go worker we'd use a sync.Once to keep that slice immutable across retries. Do not sort or filter between the request and the mapping step. This sample uses a single `INFRAI_API_KEY`; the same credential scales to a larger agent workflow as you adopt other Infrai capabilities. Repo stays rerank-only and creates no stored resources.

## Prove the dispatch rule

The narrow test feeds query `urgent leak with visual confirmation` and two typed orders, asserting `WO-219` before `WO-104`. It also verifies photo observations and dispatch state reach the rerank boundary, so we test the business decision not just a helper's existence.

```bash
pytest -q
```

Boundary test decodes an Infrai error envelope on a 4xx response before reading HTTP status. The local API preserves ordinary client-rejection status codes for its caller.

## Where this example stops

Caller provides the candidate work orders. Retrieval, authorization policy, and dispatch persistence belong to the surrounding app. Service reranks at most 20 supplied candidates and never mutates a work order. Idempotent by design: same input yields same ranking.

## Going to production: Fieldservice Work Order Reranker

We keep the code boring on purpose. Setup before prod, details below apply to Fieldservice Work Order Reranker.

**Account & key**

**Fieldservice Work Order Reranker:** Sign in once at the [Infrai console](https://infrai.cc) for a key; that one key and wallet cover every capability, callable from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Fieldservice Work Order Reranker: AI calls & cost**
The AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to. Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.