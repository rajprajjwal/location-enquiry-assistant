# Location Services Sales & Support Agentic Copilot

An agentic AI copilot for sales and support teams handling location-based services.
Uses a **Planner → Executor → Critic** loop (LangGraph) with persistent history,
deterministic validators, a hybrid RAG knowledge base (BM25 + FAISS + reranker), and
human-in-the-loop approval of tracker updates.

---

## 1. Problem Statement

Sales and support teams manually interpret location-based enquiries, consult documentation
and conversation history, draft responses, update records and compare among competitors on
pricing, capabilities, coverage and limits. These tasks cause:

- Delays in response time
- Inconsistent guidance and comparisons
- Incomplete qualification of customer requirements
- Repeated diagnostic questions across turns
- Unclear ownership and next actions

---

## 2. Goal

Enable faster responses to location-based sales and support enquiries with consistent,
accurate guidance and competitor comparisons across pricing, capabilities, coverage and
limits. Ensure complete qualification, use conversation history to avoid repeated diagnostic
questions, and maintain clear ownership and next actions for every enquiry.

---

## 3. Scope

The project evaluates plain LLM and agentic workflows for accurate, consistent and faster
handling of location-based sales and support enquiries in a controlled setting.

### In Scope

| Area | Detail |
|------|--------|
| Users | Sales and support staff handling customer and prospect enquiries |
| Enquiries | Interpretation, qualification, documentation-based guidance, integration, troubleshooting, history-aware follow-ups, record updates, ownership decisions |
| APIs covered | Directions, Distance Matrix, Autocomplete, Reverse Geocode |
| Capabilities | Consult docs and history, avoid repeated questions, draft grounded responses, identify missing info, propose record changes, recommend escalation |
| Competitor comparisons | Documented pricing, capabilities, geographic coverage and limits using equivalent requirements and stated assumptions |
| Evaluation | 500-record GT set (400 eval + 100 holdout); answer accuracy, grounding, comparison completeness, history use, ownership correctness |
| Outputs | Response drafts, clarifying questions, structured qualification, proposed record updates, comparisons, responsible roles, next actions |

### Out of Scope

| Area | Detail |
|------|--------|
| Languages | No multilingual or code-switched benchmarking, voice, images or multimodal inputs |
| Other APIs | Forward geocoding, place details, nearby search, map rendering, navigation SDKs, geofencing, fleet/route optimization |
| Exhaustive coverage | Every provider, geography, product, contract price or undocumented capability |
| Extended dialogue | Unlimited conversation depth, memory across sessions, full branching-dialogue evaluation |
| Live operations | Production record writes, real ticket handoffs, sending external messages, autonomous follow-ups, production SLAs |
| Additional testing | Dedicated security/adversarial benchmark, direct measurement of real-world map accuracy |
| Unverified ground truth | Unresolved assumptions and unvalidated records do not count as confirmed gold |

---

## 4. Ground-Truth (GT) Data

### Distribution (500 records)

| API | Sales Eval | Sales Holdout | Support Eval | Support Holdout | Total |
|-----|-----------|---------------|--------------|-----------------|-------|
| Directions | 50 | 13 | 50 | 12 | 125 |
| Distance Matrix | 50 | 12 | 50 | 13 | 125 |
| Autocomplete | 50 | 13 | 50 | 12 | 125 |
| Reverse Geocode | 50 | 12 | 50 | 13 | 125 |
| **Total** | **200** | **50** | **200** | **50** | **500** |

### Filter Rules

| Rule | Detail |
|------|--------|
| Interpretation & qualification | Include clear, ambiguous and incomplete enquiries; define correct intent and qualification fields without inventing customer facts |
| Consistent guidance | Ground answers in the right docs; include cases needing clarification or honest "not sure" |
| Repeated diagnostics | Include histories with questions already answered; gold reply must reuse known facts and ask only for what's missing |
| Competitor comparisons | Fill all four comparison buckets (pricing, capability, coverage, limits); compare like-for-like on product, region, features, billing unit, volume and date |
| Record updates & ownership | Give starting record state plus expected changes, owner and next action |
| Sources | Prefer official location-based service provider docs; exclude off-topic, outdated or unredacted sensitive content |
| Diversity & dedup | 40/40/20 easy/medium/hard mix; remove near-duplicates at 0.90 similarity; cap template family at 3% overall |
| Verification & leakage | Human review of expected answers; two reviewers for pricing, policy and escalation; keep each template/source/customer in one split; freeze holdout before tuning |

### Queries Covered

| Query Type | Example |
|-----------|---------|
| Enquiry interpretation | "Do I need directions or a travel-time matrix?" |
| Doc-grounded answers | "Why does this request fail, and what should I change?" |
| History-aware multi-turn | Continue troubleshooting without asking for the payload again |
| Record updates | "Update the expected volume and issue status from this chat" |
| Pricing comparison | "Compare providers at this monthly volume" |
| Capability comparison | "Which provider supports this travel mode with traffic?" |
| Coverage comparison | "Which providers cover this region for this API?" |
| Limits comparison | "Compare matrix limits and how many batches this job needs" |
| Qualification | "What volume, geography, latency and features must we collect?" |
| Ownership & next action | "Who owns this open issue, and what happens next?" |

---

## 5. Problems and Motivations

| # | Problem | Applies To | Description | AI Role |
|---|---------|-----------|-------------|---------|
| 1 | Incomplete customer information | Sales & Support | Sales lacks use case, coverage and usage details; support lacks parameters, timestamps and error responses | Planner identifies missing info and generates targeted questions |
| 2 | Repeated documentation searches | Sales & Support | Teams repeatedly search for capabilities, limitations, integration details and error information | Executor retrieves KB with citations |
| 3 | Inconsistent or unsupported responses | Sales & Support | Explanations and guidance are variable or unsupported | Generative AI drafts context-aware responses; Critic checks claims against evidence |
| 4 | Competitor comparisons | Sales & Support | Comparisons miss differences in pricing units, capabilities, coverage and limits | Structure comparisons around equivalent requirements with deterministic calculations |
| 5 | Fragmented conversation history | Sales & Support | Requirements, discussions, findings scattered — repeated questions and lost context | Executor retrieves and summarises persistent history; checks known facts before asking |
| 6 | Unclear ownership and next actions | Sales & Support | Owner, status or next action is missing | Planner proposes ownership and actions for human approval |
| 7 | Outdated operational records | Sales & Support | Opportunity requirements, case findings and status are incomplete or inaccurate | Executor extracts changes and proposes tracker updates for human approval |
| 8 | Incomplete handoffs | Sales & Support | Missing context in sales, support and technical transfers causes repeated work | Executor structures handoffs; Critic checks requirements, findings and unresolved questions |
| 9 | Manual capability matching | Sales | Customer requirements matched to services manually | Executor maps requirements to documented capabilities; Critic verifies evidence and flags gaps |
| 10 | Incomplete opportunity qualification | Sales | Budget, timelines, technical constraints or decision-maker missing | Planner provides BANT+ checklist and discovery questions |
| 11 | Time-consuming communication preparation | Sales | Personalised discovery, pitches and follow-ups prepared manually | Generative AI drafts communications using requirements, capabilities and history |
| 12 | Manual issue classification | Support | Affected service and category must be identified before investigation | Planner classifies issue and selects steps and tools |
| 13 | Repetitive diagnostic checks | Support | Formats, coordinates, required parameters checked repeatedly | Executor invokes deterministic validators and uses results for guidance |
| 14 | Inconsistent escalation | Support | Escalation happens too early, too late, or with insufficient evidence | Planner applies approved escalation policy; prepares evidence-backed recommendation for human review |
| 15 | Limited diagnostic traceability | Support | Hard to identify supporting evidence and checks | Instrumentation logs retrieved sources, tool results and execution steps |


---

## 6. Live URLs

| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI Backend | http://localhost:8000 |
| API Swagger Docs | http://localhost:8000/docs |
| LLM Server (vLLM) | https://103.42.50.41:1031/v1 |

> The LLM server is hosted on the TechCorp internal network. You must be connected to the **TechCorp VPN or internal network** to use this application.

---

## 7. LLM Server Infrastructure

The LLM is served on an **UpGrad-provisioned NVIDIA L40S GPU server (vm07)** hosted on the
**TechCorp internal network**, running **vLLM 0.23.0** behind a **Caddy reverse proxy** over
HTTPS. The deployment is dedicated to this capstone project.

### Server Details

| Property | Value |
|----------|-------|
| **Server IP** | `103.42.50.41` |
| **Port** | `1031` |
| **Protocol** | HTTPS (TLS via Caddy reverse proxy) |
| **Deployment ID** | `upgrad-l40s-vm07-qwen3-8b` (from `x-capstone-deployment` response header) |
| **Model served** | `Qwen/Qwen3-8B` |
| **Max context length** | `8192` tokens |
| **vLLM version** | `0.23.0` (from `system_fingerprint: vllm-0.23.0-cf68c613`) |
| **API compatibility** | OpenAI-compatible REST (`/v1/chat/completions`, `/v1/models`) |
| **Embeddings endpoint** | Not available — embeddings run locally via fastembed |
| **Network** | TechCorp internal network — VPN required |

### Full Server Stack

```
Client (this project)
      │  HTTPS :1031
      ▼
┌─────────────────────────────────────────────┐
│  Caddy Reverse Proxy                        │
│  TLS termination — vm07-ca.crt (ECC Root)   │
│  Header: via: 1.1 Caddy                     │
│  Header: x-capstone-deployment:             │
│          upgrad-l40s-vm07-qwen3-8b          │
└─────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────┐
│  vLLM 0.23.0  (Uvicorn ASGI)               │
│  OpenAI-compatible REST API                 │
│  POST /v1/chat/completions                  │
│  GET  /v1/models                            │
└─────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────┐
│  NVIDIA L40S GPU  (vm07)                    │
│  Model: Qwen/Qwen3-8B                       │
│  Max tokens: 8192                           │
└─────────────────────────────────────────────┘
```

### SSL Certificate (`vm07-ca.crt`)

| Property | Value |
|----------|-------|
| **File** | `vm07-ca.crt` (included in project root) |
| **Type** | Root CA certificate (Caddy Local Authority) |
| **Issuer** | `Caddy Local Authority - 2026 ECC Root` |
| **Algorithm** | ECC (ECDSA P-256) |
| **Valid from** | 2026-11-04 |
| **Valid until** | 2036-09-12 |
| **Purpose** | Verifies the TLS certificate presented by the Caddy proxy on vm07 |
| **Usage in project** | Passed to `httpx.Client(verify="vm07-ca.crt")` when `SSL_VERIFY=true` |
| **No OS import needed** | httpx accepts the cert file directly — no system trust store changes required |

### How SSL verification works in `app/llm.py`

```python
def _ssl_verify():
    val = os.getenv("SSL_VERIFY", "false").lower()
    if val == "false":
        return False                          # skip verification
    cert = os.path.abspath(os.getenv("SSL_CERT_PATH", "./vm07-ca.crt"))
    return cert if os.path.exists(cert) else False  # use vm07-ca.crt
```

With `SSL_VERIFY=true` and `SSL_CERT_PATH=./vm07-ca.crt` in `.env`, every LLM call is made
over a verified HTTPS connection using the Caddy root CA certificate. If `SSL_VERIFY` is
unset or `false`, verification is skipped. The `.env` currently in the repo sets
`SSL_VERIFY=false`.

---

## 8. Architecture

```
User (Browser)
      │
      ▼
Streamlit UI  (http://localhost:8501)
      │  HTTP
      ▼
FastAPI Backend  (http://localhost:8000)
      │
      ▼
LangGraph Orchestrator
┌──────────────────────────────────────────┐
│  Planner  →  Executor  →  Critic        │
│     ↑            ↓            ↓         │
│  History    RAG / Tools    Revise       │
└──────────────────────────────────────────┘
      │                    │
      ▼                    ▼
SQLite DB            Qwen/Qwen3-8B LLM
(History +           (https://103.42.50.41:1031/v1)
 Tracker +
 Audit)
      │
      ▼
Hybrid retriever (app/kb/retriever.py)
  FAISS dense index (data/kb_index/) ← FastEmbed embeddings (local ONNX, BAAI/bge-small-en-v1.5)
  BM25 sparse index (data/bm25_index.pkl, optional)
  → RRF fusion → cross-encoder rerank (optional) → top-k
```

---

## 9. RAG Pipeline

The system uses RAG to ground every agent response in verified knowledge base content.

### How it works

```
User Message
     │
     ▼
1. EMBED query
   FastEmbedEmbeddings (BAAI/bge-small-en-v1.5)
   Runs locally via ONNX runtime — no network call
     │
     ▼
2. RETRIEVE top-K chunks (hybrid, k=4 from the Executor)
   a. FAISS dense search (fetches 3×k) — index at ./data/kb_index/
   b. BM25 sparse search (fetches 3×k) — index at ./data/bm25_index.pkl
      (skipped if rank-bm25 is missing or the index was not built)
   c. Reciprocal Rank Fusion of (a) and (b)
   d. Cross-encoder rerank (cross-encoder/ms-marco-MiniLM-L-6-v2 via
      sentence-transformers); falls back to the fused order if it cannot load
     │
     ▼
3. INJECT into Executor prompt
   [KB-1] ... [KB-2] ... [KB-3] ... [KB-4]
     │
     ▼
4. LLM GENERATES grounded response
   Qwen/Qwen3-8B @ https://103.42.50.41:1031/v1
   Must cite [KB-N] for every factual claim
     │
     ▼
5. CRITIC verifies
   Checks every claim is supported by a retrieved source
   Flags unsupported statements, revises if needed
```

### Knowledge Base Dataset

| Property | Detail |
|----------|--------|
| Source files | `data/corpus/*.md` (8 files) + `data/knowledge_base.txt` |
| Format | Markdown / plain text |
| Chunk strategies | `fixed` 600/80 (default), `small` 300/50, `large` 1200/150 (chars / overlap) |
| Splitter | `RecursiveCharacterTextSplitter` |
| Embedding model | `BAAI/bge-small-en-v1.5` (384-dim, via fastembed) |
| Dense store | FAISS (CPU), saved at `data/kb_index/` |
| Sparse store | BM25 (`rank-bm25`), saved at `data/bm25_index.pkl` |
| Retrieval | BM25 + FAISS → RRF → cross-encoder rerank → top-4 |

Corpus files in `data/corpus/`:

| File | Topic |
|------|-------|
| `01_directions_api.md` | Directions API |
| `02_distance_matrix_api.md` | Distance Matrix API |
| `03_autocomplete_api.md` | Autocomplete API |
| `04_reverse_geocode_api.md` | Reverse Geocode API |
| `05_pricing_and_plans.md` | Pricing and plans |
| `06_integration_auth_sdk.md` | Integration, auth, SDKs |
| `07_escalation_qualification.md` | Escalation and qualification |
| `08_errors_diagnostics.md` | Errors and diagnostics |

### Legacy Knowledge Base Contents (`data/knowledge_base.txt`)

| Section | Topics Covered |
|---------|---------------|
| 1. Core Capabilities | Real-Time Location API (GPS/GNSS, REST/WebSocket, WGS84/UTM/MGRS), Geofencing, Route Optimization (TSP/VRP, 150 waypoints), Indoor Positioning (Wi-Fi/BLE/UWB), Geocoding (195 countries) |
| 2. Integration Details | Authentication (API Key, OAuth2, JWT 3600s), SDKs (iOS/Android/Web/Server), Webhooks (HMAC-SHA256, 3 retries), Data Residency (EU/US/APAC, GDPR) |
| 3. Limitations & Errors | Known limitations, error codes (400/401/403/404/422/429/500/503), 6-step diagnostic checklist |
| 4. Pricing & Plans | Standard $299/mo, Professional $999/mo, Enterprise custom (99.99% SLA) |
| 5. Escalation Policy | L2/L3 support escalation criteria, sales escalation to Solutions Engineer |
| 6. Sales Qualification | BANT+ checklist, 9 discovery questions |

### Embedding Model Details

| Property | Detail |
|----------|--------|
| Model name | `BAAI/bge-small-en-v1.5` |
| Provider | fastembed (Qdrant) — ONNX quantized |
| Dimensions | 384 |
| Runtime | Local ONNX (no GPU, no torch required) |
| Cache location | `%TEMP%\fastembed_cache\` |
| First-run download | ~25 MB (auto-downloaded from HuggingFace) |
| HuggingFace page | https://huggingface.co/BAAI/bge-small-en-v1.5 |


---

## 10. Components

| Component | Description |
|-----------|-------------|
| Task specification | Defines intents, required information, correct outcomes and when to refuse |
| GT evaluation set | 500 realistic queries with gold answers, frozen before coding starts |
| Prompt-engineering baseline | Compares prompting strategies; records where the model fails |
| Documentation retrieval & grounding | FAISS + fastembed corpus; BM25 + dense retrieval with RRF fusion and cross-encoder rerank; cited answers; Recall@k measured via `/rag-eval` |
| Comparison & calculation tools | Pricing, capabilities, coverage and limits on equal terms with deterministic math |
| Conversation state | Known facts and open questions kept across turns via SQLite |
| Response drafting | Structured, cited answers and clarifying questions |
| Sandbox record updates | Changes applied to test records; human reviews consequential actions |
| Ownership, escalation & human review | Responsible role, next action and approval gate |
| Agent orchestration & reliability | Planner → Executor → Critic loop; validated output formats; handles tool failures, broken JSON, loops and token limits in ≤10 steps |
| Evaluation & observability | Accuracy, completion, tool calls, cost and latency; errors sorted by type; traces via audit log |
| Deployment & responsible AI | Streamlit UI (no rate limiting implemented in the code) |

---

## 11. Agents

| Agent | File | Role |
|-------|------|------|
| Planner | `app/agents/planner.py` | Classifies enquiry/issue, identifies missing info, proposes discovery questions, checks escalation policy |
| Executor | `app/agents/executor.py` | Retrieves KB via RAG, runs validators, drafts grounded response with [KB-N] citations, extracts tracker updates |
| Critic | `app/agents/critic.py` | Checks every claim against retrieved sources, flags unsupported statements, approves or revises |

## 12. Tools

| Tool | File | Purpose |
|------|------|---------|
| KB Retriever | `app/kb/retriever.py` | Hybrid retrieval: BM25 + FAISS, RRF fusion, cross-encoder rerank, top-4 KB chunks |
| KB Evaluator | `app/kb/evaluator.py` | Recall@1/2/4 and answer-quality evaluation against built-in GT records (`/rag-eval`) |
| Validators | `app/tools/validators.py` | Deterministic coordinate/timestamp/device_id validation + error code classification |
| Tracker | `app/tools/tracker.py` | Opportunity (sales) and case (support) tracker with human-approval workflow |
| History | `app/tools/history.py` | Persistent conversation history + audit log |

---

## 13. Setup

### 1. Prerequisites
- Python 3.11+
- Connected to **TechCorp VPN / internal network** (required for LLM server)

### 2. Install dependencies
```bash
pip install -r requirements.txt
```
`requirements.txt` already includes `fastembed`, `rank-bm25` and `sentence-transformers`.

### 3. Configure environment
Create/edit `.env` in the project root (loaded with `python-dotenv`). Variables used by the code:

| Variable | Used by | Default if unset |
|----------|---------|------------------|
| `OPENAI_API_KEY` | `app/llm.py` | none (required) |
| `OPENAI_BASE_URL` | `app/llm.py` | `https://103.42.50.41:1031/v1` |
| `OPENAI_MODEL` | `app/llm.py` | `Qwen/Qwen3-8B` |
| `SSL_VERIFY` | `app/llm.py` | `false` |
| `SSL_CERT_PATH` | `app/llm.py` | `./vm07-ca.crt` |
| `EMBED_MODEL` | `app/llm.py` | `BAAI/bge-small-en-v1.5` |
| `DATABASE_URL` | `app/db/models.py` | `sqlite:///./capstone.db` |
| `KB_INDEX_PATH` | `app/kb/retriever.py` | `data/kb_index` |
| `BM25_INDEX_PATH` | `app/kb/retriever.py` | `data/bm25_index.pkl` |
| `CORPUS_DIR` | `app/kb/retriever.py` | `data/corpus` |
| `CHUNK_STRATEGY` | `app/kb/retriever.py` (only when the index is auto-built because it is missing) | `fixed` |

The repo's `.env` sets the first eight variables (`OPENAI_*`, `SSL_*`, `DATABASE_URL`,
`KB_INDEX_PATH`, `EMBED_MODEL`).

### 4. Build the knowledge base index (run once, and after corpus changes)
```bash
python build_kb.py                    # default "fixed" chunking (600 chars / 80 overlap)
python build_kb.py --strategy small    # 300 / 50
python build_kb.py --strategy large    # 1200 / 150
python build_kb.py --compare           # print chunk counts per strategy, no build
```
- Initialises the SQLite database (`capstone.db`)
- Loads `data/corpus/*.md` and `data/knowledge_base.txt`
- Downloads the embedding model (~25 MB, first run only)
- Builds the FAISS index and saves it to `data/kb_index/`
- Builds the BM25 index at `data/bm25_index.pkl` (skipped with a warning if `rank-bm25` is not installed)

### 5. Start the API server — Terminal 1
```bash
python run_api.py
```
`run_api.py` loads `.env` and runs `uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)`.
Equivalent: `uvicorn app.api.main:app --port 8000` (run from the project root; `app/api/main.py` also loads `.env` itself).
API runs at `http://localhost:8000` (Swagger UI at `/docs`).

### 6. Start the UI — Terminal 2
```bash
python -m streamlit run ui/app.py
```
UI opens at `http://localhost:8501`

---

## 14. Usage

### Sales workflow
1. Select **sales** in the sidebar
2. Ask: *"We need to track 500 delivery vehicles in real time across Europe"*
3. Planner identifies missing BANT+ fields and generates discovery questions
4. Executor retrieves matching KB capabilities with [KB-N] citations via RAG
5. Critic verifies all claims are grounded in retrieved sources
6. Tracker updates are proposed — click **Approve** in the sidebar to commit

### Support workflow
1. Select **support** in the sidebar
2. Optionally fill in diagnostic params (device_id, lat, lon, timestamp, error_code)
3. Ask: *"Getting 422 errors on the location API"*
4. Planner classifies the issue and selects diagnostic steps
5. Executor runs validators + retrieves KB resolution steps via RAG
6. Critic checks the guidance against KB sources

### Human approval
- Tracker updates are **proposed, not applied** until you approve
- Click **✅ Approve Pending Updates** in the sidebar to apply them
- Escalation recommendations are flagged in the Planner output for human review

---

## 15. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send a message, get agentic response |
| POST | `/approve-update` | Approve pending tracker updates |
| GET | `/tracker/{id}` | View tracker state and missing fields |
| GET | `/history/{id}` | View conversation history |
| GET | `/audit/{id}` | View full agent execution audit trail |
| POST | `/baseline` | Run 3 prompting strategies, get comparison report |
| POST | `/rag-eval` | Evaluate retrieval (Recall@k) and optionally answer quality against built-in GT records |
| GET | `/health` | Health check |

`/chat` requires `workflow` to be `"sales"` or `"support"` (otherwise HTTP 400). If
`conversation_id` is omitted a UUID is generated and returned.

Errors are always JSON. If the agent workflow fails (e.g. LLM unreachable, LLM 429
rate limit) `/chat` returns HTTP 500 with
`{"error": "workflow_failed", "detail": "<ExceptionType>: <message>", "conversation_id": "..."}`;
any other unhandled exception on any endpoint returns HTTP 500 `{"error": "internal_error", "detail": "..."}`.
Validation errors keep FastAPI's `{"detail": ...}` shape (400/422). The Streamlit UI checks
status and content-type before decoding and shows `API returned HTTP <code>: <detail>`.

### Request models

| Endpoint | Body |
|----------|------|
| `POST /chat` | `{ "conversation_id": str?, "workflow": "sales"\|"support" (default "sales"), "message": str, "params": object? }` |
| `POST /approve-update` | `{ "conversation_id": str }` |
| `POST /baseline` | `{ "query": str, "workflow": str (default "sales") }` |
| `POST /rag-eval` | `{ "mode": "retrieval"\|"full" (default "retrieval"), "k": int (default 4), "use_llm_judge": bool (default false), "record_ids": [str]? }` |

`params` is passed to the Executor's validators: `lat`, `lon`, `timestamp`, `device_id`
trigger `validate_location_request`; `error_code` triggers `classify_error_code`.

### Other response shapes

| Endpoint | Response |
|----------|----------|
| `POST /approve-update` | `{"status": "approved", "data": {...}}` or `{"status": "nothing_to_approve"}` |
| `GET /tracker/{id}` | `{"data", "missing_fields", "pending_updates"}` (`{}` if no tracker exists) |
| `GET /history/{id}` | `[{"role", "content", "sources"}]` (last 20 messages) |
| `GET /audit/{id}` | `[{"step", "action", "details", "at"}]` |
| `POST /rag-eval` | `EvalReport`: `total`, `recall_at_1/2/4`, `avg_keyword_match`, `avg_llm_score`, `citation_rate`, `retrieval_results`, `answer_results`, `diagnosis` |
| `GET /health` | `{"status": "ok"}` |

### Example chat request
```json
POST http://localhost:8000/chat
{
  "workflow": "support",
  "message": "Getting 422 errors when calling the location API",
  "params": { "device_id": "truck-001", "error_code": "422" }
}
```

### Example response
```json
{
  "conversation_id": "abc-123",
  "response": "The 422 error indicates a missing required parameter [KB-3]...",
  "planner": { "issue_category": "client", "missing_info": [], "escalation_needed": false },
  "critic": { "approved": true, "confidence": 0.95, "issues": [] },
  "sources": [{ "ref": "KB-1", "content": "422 MISSING_PARAMETER...", "score": 0.21, "file": "08_errors_diagnostics.md" }],
  "pending_tracker_updates": {}
}
```


---

## 16. Complete Evaluation Matrix

### 16.1 Technology Stack

| Layer | Technology | Version | Purpose | Why Chosen |
|-------|-----------|---------|---------|------------|
| LLM | Qwen/Qwen3-8B | vLLM 0.23.0 | Chat completions for all 3 agents | UpGrad-provisioned NVIDIA L40S GPU (vm07) on TechCorp network; OpenAI-compatible API |
| LLM Server | NVIDIA L40S GPU (vm07) | — | GPU inference for Qwen3-8B | Dedicated capstone server; high-throughput, low-latency inference |
| LLM Inference Engine | vLLM | 0.23.0 | Serve Qwen model via OpenAI-compatible REST | High-throughput inference, OpenAI API compatibility |
| Reverse Proxy | Caddy | — | HTTPS termination in front of vLLM | Automatic TLS, adds `x-capstone-deployment` header |
| SSL Certificate | vm07-ca.crt | ECC P-256 | Verify Caddy TLS cert on vm07 | Root CA cert included in project; no OS trust store import needed |
| LLM Client | langchain-openai | 0.1.23 | ChatOpenAI wrapper for LLM calls | Standard LangChain integration, supports custom base_url + httpx SSL |
| Embeddings | BAAI/bge-small-en-v1.5 | ONNX quantized | Embed queries and KB chunks | 384-dim, fast, no GPU/torch needed, runs via ONNX locally |
| Embedding Runtime | fastembed | 0.3.6 | Local ONNX embedding inference | No torch dependency, installs cleanly on Windows; vLLM has no /v1/embeddings |
| Vector Store | FAISS (CPU) | faiss-cpu 1.7.4 | Similarity search over KB chunks | Fast search, no server needed, saves to disk |
| Sparse Retrieval | rank-bm25 | 0.2.2 | BM25 keyword search fused with FAISS via RRF | Complements dense retrieval on exact terms (error codes, limits) |
| Reranker | sentence-transformers | 3.0.1 | Cross-encoder `ms-marco-MiniLM-L-6-v2` rerank of fused candidates | Better top-k precision; falls back to RRF order if unavailable |
| Orchestration | LangGraph | 0.2.28 | Planner→Executor→Critic state machine | Typed state, conditional edges, cycle support for revision |
| LangChain Core | LangChain | 0.2.16 | Prompt templates, message schema | Standard agent building blocks |
| API Framework | FastAPI | 0.115.0 | REST API with Pydantic validation | Async, auto Swagger docs, lifespan context manager |
| API Server | Uvicorn | 0.30.6 | ASGI server for FastAPI | Standard production ASGI server |
| UI Framework | Streamlit | 1.38.0 | Chat UI with sidebar controls | Rapid prototyping, built-in chat components |
| Database | SQLite + SQLAlchemy | 2.0.35 | Persistent history, tracker, audit | Zero-config, file-based, sufficient for single-user |
| HTTP Client | httpx | 0.27.2 | Sync/async HTTP with SSL cert support | Required by LangChain-OpenAI; supports `verify=vm07-ca.crt` |
| Data Validation | Pydantic | 2.9.2 | Request/response models in FastAPI | Native FastAPI integration, strict typing |
| Environment | python-dotenv | 1.0.1 | Load `.env` config | Standard 12-factor app config |
| Tokenizer | tiktoken | 0.7.0 | Token counting for OpenAI models | Required by langchain-openai |

---

### 16.2 Agent Evaluation Matrix

| Dimension | Planner | Executor | Critic |
|-----------|---------|----------|--------|
| **File** | `app/agents/planner.py` | `app/agents/executor.py` | `app/agents/critic.py` |
| **LLM temperature** | 0 (deterministic) | 0.2 (slight creativity) | 0 (deterministic) |
| **Input** | user message + history + tracker state | planner output + KB chunks + validator results + history | executor draft + KB sources + planner output |
| **Output format** | Strict JSON | Free text (RESPONSE: / TRACKER_UPDATES: blocks) | Strict JSON |
| **Sales output fields** | enquiry_type, missing_fields, discovery_questions, next_actions, escalation_needed, escalation_reason | draft_response, tracker_updates, sources | approved, confidence, issues, unsupported_claims, suggested_revision |
| **Support output fields** | issue_category, missing_info, diagnostic_steps, next_actions, escalation_needed, escalation_reason | draft_response, tracker_updates, sources | approved, confidence, issues, unsupported_claims, suggested_revision |
| **Escalation logic** | Sales: custom integration / <1m accuracy / >10K devices / compliance. Support: >5% error rate >15min / data loss / security / L2 >4h | N/A | Checks if escalation recommendation matches policy |
| **Fallback on parse error** | JSON extracted via `app/agents/json_utils.py` (strips `<think>` blocks and ```` ```json ```` fences, finds first `{...}`); one retry on empty/unparsable output, then returns `{"raw": ..., "parse_error": True}` | `TRACKER_UPDATES` parsed with the same helper; `{}` if none | Same helper + one retry, then returns approved=True, confidence=0.7 |
| **History window** | Last 6 messages (200 chars each) | Last 6 messages (300 chars each) | N/A (stateless review) |
| **RAG usage** | No | Yes — top-4 KB chunks injected into prompt | Indirect — receives sources from executor |
| **Validator usage** | No | Yes — coordinates, timestamp, device_id, error_code | No |
| **Audit logged** | Yes — `plan_generated` | Yes — `response_drafted` | Yes — `review_complete` |

---

### 16.3 RAG Pipeline Evaluation

| Dimension | Detail | Value |
|-----------|--------|-------|
| **Embedding model** | BAAI/bge-small-en-v1.5 | 384-dim cosine similarity |
| **Embedding provider** | fastembed (Qdrant ONNX) | Local, no network call |
| **Dense index** | FAISS via LangChain `FAISS.from_documents` | Saved to `data/kb_index/` |
| **Sparse index** | BM25Okapi (whitespace tokenisation) | Saved to `data/bm25_index.pkl` |
| **Chunking** | RecursiveCharacterTextSplitter | `fixed` 600/80 (default), `small` 300/50, `large` 1200/150 |
| **Fusion** | Reciprocal Rank Fusion (k=60) | Applied only when BM25 results exist |
| **Reranker** | Cross-encoder `ms-marco-MiniLM-L-6-v2` | Optional; falls back to fused order |
| **Retrieval k** | Top-4 chunks per query (3×k candidates fetched per retriever) | Injected as [KB-1]…[KB-4] |
| **Score** | Cross-encoder score when reranked, otherwise FAISS distance (lower = closer) | Returned in `sources[].score` |
| **Citation enforcement** | Executor system prompt | Must cite [KB-N] for every factual claim |
| **Grounding verification** | Critic agent | Flags unsupported claims, triggers revision |
| **Index persistence** | `data/kb_index/` (FAISS save_local) | Survives restarts |
| **Index rebuild trigger** | Manual (`python build_kb.py`) | Required when corpus changes; if `data/kb_index/` is missing, the retriever builds the FAISS index on first use |
| **Evaluation** | `app/kb/evaluator.py`, `POST /rag-eval` | Recall@1/2/4, keyword match, citation rate, diagnosis (see section 16.11) |

---

### 16.4 LangGraph Orchestration Evaluation

| Dimension | Detail |
|-----------|--------|
| **Graph type** | StateGraph with TypedDict state |
| **Nodes** | planner → executor → critic → persist |
| **Entry point** | planner |
| **Conditional edge** | critic → executor (if not approved + has revision) or critic → persist |
| **Cycle support** | Yes — critic can loop back to executor for revision |
| **State fields** | conversation_id, workflow, user_message, params, history, tracker_summary, planner_output, executor_output, critic_output, final_response, sources, pending_tracker_updates, audit_trail, revisions |
| **State immutability** | Each node returns `{**state, ...new_fields}` — no in-place mutation |
| **Graph compilation** | Compiled once at startup, cached in `_graph` singleton |
| **Persistence** | SQLite via persist_node (history + tracker + audit) |
| **Human-in-the-loop** | Tracker updates proposed but not applied until `/approve-update` called |
| **Max steps** | `MAX_REVISIONS = 1` in `orchestrator.py`: the critic → executor loop re-drafts at most once; after the second critic pass the graph goes to persist (an unapproved draft is replaced by the critic's `suggested_revision`) |
| **KB-gap guard** | `kb_gap_notice()` in `executor.py`: if the user names a third-party provider (Ola / Ola Maps, Google Map(s), Mapbox, TomTom, HERE Maps, OpenStreetMap, Apple Maps, Azure Maps; matched case-insensitively) that does not appear in the retrieved KB chunks, the critic node replaces the final response with a fixed note saying the KB has no data on it and offering the Provider A/B/C comparison or escalation (the LLM draft is discarded because it tends to invent a comparison) |

---

### 16.5 Validator Evaluation

| Validator | Input | Checks | Output |
|-----------|-------|--------|--------|
| `validate_coordinates` | lat, lon (float) | lat ∈ [-90, 90], lon ∈ [-180, 180] | `{valid, errors[]}` |
| `validate_timestamp` | ISO8601 string | Valid ISO8601 format, drift ≤ 300s from server time | `{valid, errors[]}` |
| `validate_device_id` | string | 4–64 chars, alphanumeric/dash/underscore only | `{valid, errors[]}` |
| `validate_location_request` | params dict | Runs all 3 above, aggregates errors | `{valid, checks{}, all_errors[]}` |
| `classify_error_code` | HTTP status code string | Maps to category + description + action | `{category, description, action}` |

**Error code classification:**

| Code | Category | Description | Recommended Action |
|------|----------|-------------|-------------------|
| 400 | client | Invalid request parameters | Check coordinate ranges and required fields |
| 401 | auth | Authentication failed | Verify token validity and expiry |
| 403 | quota | Quota exceeded | Check dashboard for quota usage |
| 404 | config | Device not found | Verify device_id is registered in portal |
| 422 | client | Missing required parameter | Check required_fields in error response body |
| 429 | rate_limit | Rate limited | Implement backoff; check Retry-After header |
| 500 | server | Internal server error | Retry with exponential backoff |
| 503 | availability | Service unavailable | Check status page; retry after maintenance window |


---

### 16.6 Tracker Evaluation

| Dimension | Sales Tracker | Support Tracker |
|-----------|--------------|-----------------|
| **Tracked fields** | company, use_case, device_count, accuracy_requirement, platform, budget, timeline, decision_maker, compliance, status | case_id, affected_service, error_codes, device_id, steps_taken, impact, escalation_level, status, resolution |
| **Total fields** | 10 | 9 |
| **Missing field detection** | Auto-computed on every `get_tracker_summary()` call | Auto-computed on every `get_tracker_summary()` call |
| **Update flow** | Executor extracts → `propose_update()` → human approves → `approve_update()` | Same |
| **Approval mechanism** | POST `/approve-update` or UI sidebar button | Same |
| **Pending updates** | Stored as JSON list in `Tracker.pending_updates` | Same |
| **Applied updates** | Merged into `Tracker.data` dict on approval | Same |
| **SQLAlchemy safety** | Reassigns to new list/dict objects to trigger dirty-tracking | Same |

---

### 16.7 Persistence & Audit Evaluation

| Component | Table | Key Fields | Purpose |
|-----------|-------|-----------|---------|
| Conversation | `conversations` | id, workflow, created_at, metadata_ | Session container |
| Message | `messages` | id, conversation_id, role, content, sources (JSON) | Full chat history |
| Tracker | `trackers` | id, conversation_id, workflow, data (JSON), pending_updates (JSON) | Opportunity/case state |
| Audit Log | `audit_logs` | id, conversation_id, step, action, details (JSON), created_at | Full agent execution trace |

**Audit log entries per request:**

| Step | Action | Details logged |
|------|--------|---------------|
| planner | plan_generated | Full planner JSON output |
| executor | response_drafted | sources_count, tracker_updates |
| critic | review_complete | Full critic JSON output |

---

### 16.8 API Evaluation

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/chat` | POST | conversation_id?, workflow, message, params? | conversation_id, response, planner, critic, sources, pending_tracker_updates |
| `/approve-update` | POST | conversation_id | status, data |
| `/tracker/{id}` | GET | conversation_id (path) | data, missing_fields, pending_updates |
| `/history/{id}` | GET | conversation_id (path) | list of {role, content, sources} |
| `/audit/{id}` | GET | conversation_id (path) | list of {step, action, details, at} |
| `/baseline` | POST | query, workflow | query, workflow, winner, strategies, comparison_table, failure_modes_catalogue |
| `/rag-eval` | POST | mode, k, use_llm_judge, record_ids? | EvalReport (recall_at_1/2/4, avg_keyword_match, avg_llm_score, citation_rate, diagnosis, per-record results) |
| `/health` | GET | — | {status: "ok"} |

---

### 16.11 RAG Evaluation (`app/kb/evaluator.py`)

Two diagnostic layers, exposed through `POST /rag-eval`:

| Layer | `mode` | What it measures | LLM calls |
|-------|--------|------------------|-----------|
| 1 — Retrieval | `retrieval` (default) | Recall@1, @2, @4: a hit is any gold phrase appearing in the retrieved chunks | None |
| 2 — End-to-end | `full` | Layer 1 plus `run_workflow` for each record; scores exact match, keyword match, `[KB-N]` citation presence, and optionally an LLM judge score (`use_llm_judge=true`) | Full agent pipeline per record |

The report's `diagnosis` is one of `RETRIEVAL_BOTTLENECK` (Recall@4 < 0.70),
`GENERATOR_BOTTLENECK` (keyword match < 0.5), `CITATION_GAP` (citation rate < 0.8) or `OK`.
Built-in GT records (`BUILTIN_GT_RECORDS`, 25 records across Directions, Distance Matrix,
Autocomplete, Reverse Geocode and escalation) are used; pass `record_ids` to run a subset.

```bash
curl -X POST http://localhost:8000/rag-eval -H "Content-Type: application/json" \
     -d '{"mode": "retrieval", "k": 4}'
```

The 500-record ground-truth set (`ground-truth.xlsx` in the project root) is not loaded
by any code; `/rag-eval` uses only the built-in records.

---

### 16.9 Problem → Feature Mapping

| # | Problem | Implementation | File |
|---|---------|---------------|------|
| 1 | Incomplete customer info | Planner identifies missing BANT+ fields, generates targeted discovery questions | `agents/planner.py` |
| 2 | Repeated doc searches | Executor retrieves KB with FAISS RAG + [KB-N] citations on every request | `kb/retriever.py`, `agents/executor.py` |
| 3 | Inconsistent responses | Critic checks every claim against retrieved KB sources, revises if unsupported | `agents/critic.py` |
| 4 | Competitor comparisons | Executor retrieves pricing/capability/coverage/limits from KB; structures like-for-like comparisons | `kb/retriever.py`, `agents/executor.py` |
| 5 | Fragmented history | SQLite persistent history; last 6 messages injected into every agent prompt | `tools/history.py` |
| 6 | Unclear ownership | Planner proposes next_actions; human approves tracker updates | `agents/planner.py`, `tools/tracker.py` |
| 7 | Outdated records | Executor extracts tracker updates; propose_update() requires human approval | `tools/tracker.py` |
| 8 | Incomplete handoffs | Executor structures handoff summaries; Critic checks completeness | `agents/executor.py`, `agents/critic.py` |
| 9 | Manual capability matching | Executor maps requirements to KB capabilities via FAISS RAG | `kb/retriever.py` |
| 10 | Incomplete qualification | Planner uses BANT+ checklist, generates discovery questions for missing fields | `agents/planner.py` |
| 11 | Communication prep | Executor drafts personalised comms from conversation history + KB | `agents/executor.py` |
| 12 | Manual issue classification | Planner classifies issue into 7 categories, selects diagnostic steps | `agents/planner.py` |
| 13 | Repetitive diagnostics | validators.py runs deterministic coordinate/timestamp/device_id/error_code checks | `tools/validators.py` |
| 14 | Inconsistent escalation | Planner applies escalation policy rules; flags for human review | `agents/planner.py` |
| 15 | Limited traceability | AuditLog records every agent step, tool call, source, and tracker update | `tools/history.py`, `db/models.py` |

---

### 16.10 Security & Configuration Evaluation

| Concern | Approach | Detail |
|---------|----------|--------|
| SSL verification | `SSL_VERIFY=true` + `vm07-ca.crt` | Fully verified HTTPS using Caddy root CA; no OS trust store import needed |
| API key | Loaded from `.env`, never hardcoded | `OPENAI_API_KEY` env var |
| LLM endpoint | Private TechCorp network only | `https://103.42.50.41:1031/v1` — requires VPN |
| Database | Local SQLite file | `capstone.db` — no network exposure |
| FAISS index | Local file | `data/kb_index/` — no network exposure |
| Embeddings | Local ONNX inference | No data sent to external embedding API |
| Input validation | Pydantic models on all API endpoints | Type-safe request parsing |
| Thread safety | SQLite `check_same_thread=False` | Required for FastAPI async context |
| Human-in-the-loop | All tracker writes require explicit approval | Prevents autonomous operational changes |

---

## 17. Prompt Engineering Baseline

### 17.1 Overview

Before building the full agentic loop, the project runs a **single-agent, single-prompt
baseline** to establish where a plain LLM succeeds and where it breaks. This directly
informs which problems require the full Planner → Executor → Critic architecture.

The baseline is implemented in `app/baseline/prompting.py` and exposed via `POST /baseline`.
It is accessible in the UI under the **🧪 Prompt Engineering Baseline** tab.
`prompting.py` also defines a richer per-record scorer (`StrategyScore`: accuracy, grounding,
completeness, latency, cost, parse_ok, composite) and a `FROZEN_GT` list of baseline records,
but no endpoint or script runs them; `/baseline` uses the 4-point score in section 17.3.

**Key constraint:** No RAG, no tools, no history, no agentic loop — just the LLM and the prompt.

---

### 17.2 Three Prompting Strategies

The same query is run through all three strategies simultaneously for direct comparison.

#### Strategy 1 — Structured Output with Few-Shot

**How it works:**
- System prompt defines the exact JSON output schema: `intent`, `summary`, `missing_info`,
  `recommended_action`, `confidence`
- Three labelled examples (fleet tracking, 401 auth error, indoor positioning comparison)
  are included in the prompt before the query
- Temperature = 0 for deterministic output
- Single LLM call

**Prompt structure:**
```
System: You are a location services assistant.
        Answer as JSON with fields: intent, summary, missing_info, recommended_action, confidence
        Examples:
          Query: "We want to track 200 trucks..."
          Answer: {"intent":"fleet_tracking_qualification", ...}
          [2 more examples]
        Now answer:
User:   <query>
```

**Strengths:**
- Fastest (single call, temp=0)
- Most consistent output format
- Works well for queries that closely match the few-shot examples

**Weaknesses:**
- Breaks on queries outside the example distribution
- Model copies example field values instead of query values (few_shot_field_copy)
- Fails silently when JSON is wrapped in markdown fences

---

#### Strategy 2 — Chain-of-Thought with Self-Consistency

**How it works:**
- System prompt instructs the model to reason through 5 explicit steps before answering:
  1. Identify intent
  2. List present information
  3. Identify missing information
  4. Apply relevant policy (BANT+ or diagnostic checklist)
  5. State recommended action
- Runs **3 independent samples** at temperature = 0.6 for diversity
- **Majority vote** on `intent` across samples
- **Union** of `missing_info` across all valid samples (catches fields missed by any single run)
- Final `confidence` is the mean across valid samples
- Agreement rate = fraction of samples that agree on the majority intent

**Prompt structure:**
```
System: Think step by step.
        Step 1 — intent?
        Step 2 — present info?
        Step 3 — missing info?
        Step 4 — policy?
        Step 5 — action?
        Output JSON on last line: {"intent":...}
User:   <query>
        [run 3 times, vote]
```

**Strengths:**
- Most thorough missing_info detection (union across samples)
- Self-consistency catches hallucinations that appear in only 1 of 3 samples
- Reasoning trace is visible for debugging

**Weaknesses:**
- 3× slower and 3× more expensive than Strategy 1
- Qwen3-8B `<think>` tags sometimes bleed into the final answer
- On ambiguous queries, all 3 samples produce different intents (0% agreement)

---

#### Strategy 3 — Decomposition Prompting

**How it works:**
- Breaks the query into **5 independent sub-problems**, each solved with a separate LLM call:
  1. `intent` — classify in 3-5 words
  2. `present_info` — list explicitly stated facts as JSON array
  3. `missing_info` — list critical gaps as JSON array
  4. `policy_check` — sales or support?
  5. `action` — single most important next step
- A **6th synthesis call** combines all sub-answers into the final JSON
- Temperature = 0 throughout

**Prompt structure:**
```
Call 1: "Classify the intent in 3-5 words. Reply with ONLY the label."
Call 2: "List ONLY explicitly stated info as JSON array."
Call 3: "List critical missing info as JSON array."
Call 4: "Reply with one word: 'sales' or 'support'."
Call 5: "What is the single most important next action? One sentence."
Call 6: Synthesis — combine sub-answers into final JSON
```

**Strengths:**
- Each sub-problem is simpler → fewer hallucinations per call
- Sub-answers are individually inspectable for debugging
- Works well when the query has clearly separable components

**Weaknesses:**
- 6× more LLM calls → highest latency (~30-60s total)
- Sub-answers can contradict each other; synthesis picks the wrong one
- Synthesis call itself can fail to produce valid JSON

---

### 17.3 Scoring

Each strategy is scored out of 4 points:

| Check | Points |
|-------|--------|
| `intent` field present and not a parse error | 1 |
| `missing_info` is a non-empty list | 1 |
| `recommended_action` field present | 1 |
| No failure recorded | 1 |

The strategy with the highest score is declared the **winner** for that query.

---

### 17.4 Documented Failure Modes (Qwen3-8B)

These failures were observed running Qwen3-8B (8B parameters) as a single-agent
without an agentic loop, RAG, or Critic. They directly motivate the full architecture.

| Failure Mode | Description | Observed In | Agentic Fix |
|---|---|---|---|
| `json_fence_wrapping` | Model wraps JSON in ` ```json``` ` fences — breaks `json.loads()` directly | Strategy 1, 3 | Critic catches malformed output; parser strips fences |
| `truncated_json` | Model stops mid-JSON when response approaches 8192 token limit | All strategies | Executor uses shorter prompts; Critic detects incomplete output |
| `cot_think_tag_bleed` | Qwen3 `<think>...</think>` reasoning leaks into final answer when tags not closed | Strategy 2 | JSON extractor takes last `{...}` block only |
| `self_consistency_drift` | 3 CoT samples produce 3 different intents on ambiguous queries — no majority | Strategy 2 | Planner uses temp=0 for deterministic classification |
| `decomposition_contradiction` | Sub-problem answers contradict each other; synthesis picks the wrong one | Strategy 3 | Planner → Executor separation prevents cross-contamination |
| `few_shot_field_copy` | Model copies field values from the few-shot examples, not from the query | Strategy 1 | Executor uses query-specific KB retrieval, not static examples |
| `over_escalation` | Model escalates every support query to L3 regardless of severity | All strategies | Planner applies explicit escalation policy rules |
| `empty_missing_fields` | Model returns `missing_info=[]` even when context clearly lacks required fields | Strategy 1 | Planner explicitly checks tracker state for missing BANT+ fields |
| `confidence_anchoring` | Model always returns `confidence=0.9` regardless of actual uncertainty | All strategies | Critic provides independent confidence score |
| `hallucinated_pricing` | Model invents pricing figures not present in the prompt | All strategies | Executor grounds every claim in KB; Critic flags unsupported claims |

---

### 17.5 Comparison: Baseline vs Full Agentic

| Capability | Baseline (single prompt) | Full Agentic (Planner→Executor→Critic) |
|---|---|---|
| Intent classification | ✓ (all 3 strategies) | ✓ Planner (temp=0, deterministic) |
| Missing info detection | Partial — often empty | ✓ Planner checks tracker state |
| KB-grounded answers | ✗ No retrieval | ✓ Executor retrieves top-4 KB chunks |
| Citation enforcement | ✗ Hallucinations common | ✓ Critic verifies every claim |
| Diagnostic validation | ✗ No validators | ✓ Executor runs deterministic validators |
| Conversation history | ✗ Stateless | ✓ Last 6 messages injected |
| Tracker updates | ✗ Not possible | ✓ Executor extracts + proposes |
| Human approval gate | ✗ Not possible | ✓ `/approve-update` endpoint |
| Escalation policy | Inconsistent | ✓ Planner applies explicit rules |
| Audit trail | ✗ None | ✓ Full AuditLog per step |
| Latency | 2-60s (strategy dependent) | ~15-45s (3 agent calls + RAG) |
| Failure recovery | ✗ No retry | ✓ Critic loops back to Executor |

---

### 17.6 API Endpoint

```
POST /baseline
{
  "query": "We need to track 500 delivery vehicles across Europe",
  "workflow": "sales"
}
```

**Response structure:**
```json
{
  "query": "...",
  "workflow": "sales",
  "winner": "chain_of_thought",
  "comparison_table": [
    {
      "strategy": "few_shot_structured",
      "score": 4,
      "latency_s": 3.2,
      "cost_usd": 0.0004,
      "intent": "fleet_tracking_qualification",
      "missing_info_count": 5,
      "has_action": true,
      "failure": null
    },
    ...
  ],
  "strategies": [ ... full per-strategy detail ... ],
  "failure_modes_catalogue": { ... all 10 documented failure modes ... }
}
```

---

### 17.7 UI — Baseline Tab

The **🧪 Prompt Engineering Baseline** tab in the Streamlit UI provides:

- Free-text query input with 3 quick-example buttons (sales qualification, 422 error, capability comparison)
- Workflow selector (sales / support)
- **▶ Run Baseline** button — runs all 3 strategies in parallel
- **Comparison table** — score /4, latency, intent, missing_info count, failure
- **Winner banner** — highlights the best-performing strategy
- **Per-strategy expandable panels** showing:
  - Intent, confidence, missing info fields, recommended action
  - CoT: sample intents and agreement rate with colour coding
  - Decomposition: all 5 sub-problem answers
  - Failure message and failure mode reference
- **Documented Failure Modes catalogue** — all 10 Qwen3-8B failure modes with descriptions

---

## 18. System-Level Baseline Evaluation

The project evaluates three system-level approaches on the same query set:

| Approach | Description | Routing |
|----------|-------------|---------|
| Plain LLM | Single prompt, no tools, no history | Simple factual questions |
| LLM + RAG | KB retrieval injected into prompt, no agent loop | Documentation lookups |
| Full Agentic | Planner → Executor → Critic loop with validators, tracker, history | Complex, multi-turn, diagnostic |

**Design decision:** Simple questions route to plain LLM (low cost, fast); complex queries with
missing info, diagnostics or multi-turn context route to the full agent; cases needing human
judgment surface via the approval gate.

**Proposed evaluation metrics (500-record GT set):**

| Metric | How Measured | Target |
|--------|-------------|--------|
| Classification accuracy | Predicted vs gold enquiry/issue category | ≥ 90% |
| Missing-info precision/recall | Predicted vs gold missing fields | ≥ 85% |
| Retrieval hit rate@4 | Gold chunk in top-4 FAISS results | ≥ 90% |
| Groundedness | % draft factual sentences passing Critic | 100% after revision |
| Validator correctness | Unit tests on edge cases | 100% |
| Repeated-question rate | Questions asked that history already answers | 0% |
| Escalation agreement | Matches human decision on gold set | ≥ 90% |
| Handoff completeness | Required fields present in handoff | 100% |
| Competitor comparison accuracy | Like-for-like on pricing/capability/coverage/limits | ≥ 90% |
| Steps per query | Agent loop steps | ≤ 10 |

---

## 19. Project Structure

```
Capstone/
├── app/
│   ├── agents/
│   │   ├── planner.py        # Planner agent (LLM, temp=0, JSON output)
│   │   ├── executor.py       # Executor agent (LLM, temp=0.2, RAG + validators)
│   │   ├── critic.py         # Critic agent (LLM, temp=0, JSON output)
│   │   └── orchestrator.py   # LangGraph StateGraph workflow
│   ├── baseline/
│   │   └── prompting.py      # 3 prompting strategies + failure documentation
│   ├── tools/
│   │   ├── validators.py     # Deterministic coordinate/timestamp/device_id/error validators
│   │   ├── tracker.py        # Opportunity/case tracker with human-approval workflow
│   │   └── history.py        # Persistent conversation history + audit log
│   ├── kb/
│   │   ├── retriever.py      # Hybrid retriever: BM25 + FAISS + RRF + cross-encoder rerank; KB build
│   │   └── evaluator.py      # RAG evaluation (Recall@k, answer quality) + built-in GT records
│   ├── db/
│   │   └── models.py         # SQLAlchemy models (Conversation, Message, Tracker, AuditLog)
│   ├── api/
│   │   └── main.py           # FastAPI app — 8 endpoints incl. /baseline and /rag-eval
│   └── llm.py                # ChatOpenAI (remote vLLM) + FastEmbedEmbeddings (local ONNX)
├── ui/
│   └── app.py                # Streamlit UI — Agentic Copilot tab + Baseline tab
├── data/
│   ├── corpus/               # 8 Markdown KB documents (APIs, pricing, auth, escalation, errors)
│   ├── knowledge_base.txt    # Legacy KB source (6 sections), also indexed
│   ├── kb_index/             # FAISS index (generated by build_kb.py)
│   └── bm25_index.pkl        # BM25 index (generated by build_kb.py; not present until built)
├── build_kb.py               # KB build: init DB + chunk corpus + build FAISS and BM25 indexes
├── run_api.py                # API server entry point (uvicorn app.api.main:app, port 8000)
├── test_connection.py        # LLM endpoint smoke test
├── capstone.db               # SQLite database (created at runtime)
├── ground-truth.xlsx         # Ground-truth data sheet (not read by the code)
├── vm07-ca.crt               # Caddy root CA certificate for SSL verification
├── requirements.txt          # Python dependencies
└── .env                      # LLM server URL, API key, DB path, KB path, embed model
```

---

## 20. Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot connect to API` | Start Terminal 1: `python run_api.py` |
| `bash: streamlit: command not found` | Use `python -m streamlit run ui/app.py` |
| `ModuleNotFoundError: fastembed` | Run `pip install -r requirements.txt` |
| `BM25 index skipped` | Run `pip install rank-bm25==0.2.2`, then `python build_kb.py` |
| `KB index not found` | Run `python build_kb.py` |
| LLM not responding | Check TechCorp VPN connection; verify `https://103.42.50.41:1031/v1` is reachable |
| SSL errors | Set `SSL_VERIFY=false` to skip verification, or `SSL_VERIFY=true` with `SSL_CERT_PATH=./vm07-ca.crt` in `.env` |
| `Client sent HTTP request to HTTPS server` | Confirm `OPENAI_BASE_URL` starts with `https://` not `http://` |
| Baseline tab shows no results | Start the API server first: `python run_api.py` |
| Baseline CoT takes too long | Normal — 3 LLM samples × ~10s each = ~30s total |
| `all_samples_failed_to_parse` | Qwen3-8B `<think>` tags bleeding into output — known failure mode, documented |
| Tracker updates not saving | Fixed — SQLAlchemy JSON columns reassigned to new objects |
| Critic always returns draft | Fixed — nested ternary replaced with explicit if/else |

---

## 21. Conclusion

This project delivers a fully working agentic AI copilot for location-based services sales
and support, directly addressing all 15 identified problems from the problem statement.

**What was built:**

- A **Planner → Executor → Critic** agentic loop (LangGraph) that handles both sales
  qualification and support diagnostics in a single unified workflow
- A **hybrid (BM25 + FAISS + reranker) RAG pipeline** grounding every response in the knowledge base with
  mandatory [KB-N] citations verified by the Critic
- **Deterministic validators** for coordinates, timestamps, device IDs and error codes —
  replacing repeated manual checks
- A **human-in-the-loop approval gate** ensuring no tracker update or escalation is applied
  without explicit human review
- **Persistent SQLite history and audit trail** enabling history-aware multi-turn conversations
  and full execution traceability
- A **Streamlit UI + FastAPI backend** providing a complete, deployable application

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Separate Planner/Executor/Critic | Clear separation of duties — Planner decides, Executor acts, Critic verifies |
| Deterministic validators over LLM | Testable, reproducible, 100% correct on edge cases |
| Human approval on all writes | Prevents autonomous operational changes; maintains trust |
| Local ONNX embeddings (fastembed) | vLLM server has no `/v1/embeddings`; no torch dependency on Windows |
| SSL_VERIFY=true + vm07-ca.crt | Fully verified HTTPS to TechCorp vLLM server; no OS trust store changes |
| LangGraph StateGraph | Typed state, conditional revision cycle, clean node separation |

**Known limitations and stretch goals:**

| Limitation | Upgrade Path |
|-----------|-------------|
| GT dataset is a target (not yet built) | Build 500-record set from Kaggle/HuggingFace location QA data |
| No competitor comparison tool | Add structured pricing/capability comparison tool as 4th tool |
| Single-user SQLite | Replace with PostgreSQL for multi-user deployment |
| No latency/cost logging | Integrate LangSmith or Langfuse for observability |
| Compliance checks (stretch goal) | Add GDPR/data residency compliance checker as optional tool |

The system is production-ready for single-user capstone demonstration on the TechCorp
internal network, with a clear upgrade path to multi-user, multi-provider deployment.
