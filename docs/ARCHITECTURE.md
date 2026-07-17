# RepoGenius AI — System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              NGINX                                       │
│         TLS Termination · Security Headers · Reverse Proxy               │
│    /api/v1/* → Backend    /ws/* → Backend    /* → React SPA             │
└────────────────────┬──────────────────────┬─────────────────────────────┘
                     │                      │
         ┌───────────▼────────┐  ┌──────────▼───────────┐
         │   FastAPI Backend  │  │   WebSocket Server    │
         │   (Presentation)   │  │   /ws/jobs/{job_id}   │
         └───────────┬────────┘  └──────────┬────────────┘
                     │                      │
         ┌───────────▼──────────────────────▼────────────┐
         │              Application Layer                  │
         │   Services · EventBus · UnitOfWork              │
         └───────────────────────┬────────────────────────┘
                                 │
         ┌───────────────────────▼────────────────────────┐
         │                Domain Layer                     │
         │   Entities · Value Objects · Domain Events      │
         │   Repository Interfaces (ABCs)                  │
         └───────────────────────┬────────────────────────┘
                                 │
         ┌───────────────────────▼────────────────────────┐
         │            Infrastructure Layer                  │
         │   PostgreSQL (SQLAlchemy) · Redis · Celery       │
         │   GitPython · GitHub API · AI Providers          │
         └───────────────────────┬────────────────────────┘
                                 │
    ┌────────────────────────────▼────────────────────────────────┐
    │                    Celery Workers (7 Queues)                  │
    │  ┌─────────┐ ┌─────────┐ ┌──────┐ ┌────┐ ┌───────┐         │
    │  │  clone  │ │  parse  │ │  ai  │ │ kg │ │ embed │         │
    │  └────┬────┘ └────┬────┘ └──┬───┘ └─┬──┘ └───┬───┘         │
    │       │            │         │       │        │              │
    │  ┌────▼────┐  ┌────▼──────────▼───────▼────────▼──────────┐ │
    │  │CloneWkr │  │         Orchestrator (DAG)                 │ │
    │  │         │  │  SharedAnalysisContext → Agent DAG Dispatch │ │
    │  └─────────┘  └───────────────────────────────────────────┘ │
    │  ┌──────────┐ ┌───────────┐                                  │
    │  │  report  │ │  cleanup  │                                  │
    │  └──────────┘ └───────────┘                                  │
    └──────────────────────────────────────────────────────────────┘
                                 │
    ┌────────────────────────────▼────────────────────────────────┐
    │                   AI Provider Chain                           │
    │   Configurable order (AI_PROVIDER_ORDER env var)             │
    │   Default: Ollama → Claude → Bedrock                         │
    │   + Titan Embeddings (Bedrock-only, bypasses chain)           │
    └──────────────────────────────────────────────────────────────┘
```

---

## Clean Architecture (4 Layers)

```
backend/app/
├── presentation/          # Layer 1 — HTTP surface (thin handlers)
│   ├── api/v1/            #   FastAPI route handlers
│   └── websocket/         #   WebSocket connection handlers
│
├── application/           # Layer 2 — Use case orchestration
│   ├── services/          #   Business logic service classes
│   ├── event_bus.py       #   In-process pub/sub
│   └── unit_of_work.py    #   Atomic transaction scope
│
├── domain/                # Layer 3 — Pure business rules (NO framework deps)
│   ├── entities/          #   Domain objects (AnalysisJob, Repository, etc.)
│   ├── value_objects/     #   Immutable value types (ErrorCode, Score, etc.)
│   ├── events/            #   Domain event definitions
│   └── repositories/      #   Abstract repository interfaces (ABCs)
│
├── infrastructure/        # Layer 4 — Framework + external integrations
│   ├── db/models/         #   SQLAlchemy ORM models (19 entities)
│   ├── repositories/      #   Concrete repository implementations
│   ├── ai/                #   AIManager, PromptRegistry, EmbeddingProvider
│   ├── github/            #   GitHubService + RateLimitManager
│   ├── config/            #   ConfigRegistry singleton
│   └── workers/           #   Celery task definitions (7 queues)
│
└── agents/                # Agent system (separate from layers)
    ├── base.py            #   BaseAgent ABC
    ├── registry.py        #   Plugin auto-discovery
    ├── orchestrator.py    #   DAG-based parallel dispatch
    ├── shared_context.py  #   SharedAnalysisContextBuilder
    ├── payloads.py        #   Input/Output schemas
    ├── core/              #   8 Core Agent implementations
    └── stubs/             #   17+ Stub Agents
```

**Dependency rules:**
- Presentation → Application → Domain ← Infrastructure
- Domain has ZERO framework dependencies
- Infrastructure implements Domain interfaces
- Agents consume Application services and Domain entities

---

## Data Flow

```
1. User submits repo URL
        │
        ▼
2. POST /api/v1/repos/analyze
   ├── Validate URL (allowlist + sanitize)
   ├── Check repository cache (commit SHA match?)
   │   ├── Cache HIT → copy results, complete in <2s
   │   └── Cache MISS → continue to step 3
   └── Create AnalysisJob (status: pending)
        │
        ▼
3. CloneWorker (queue: clone)
   ├── Create workspace: workspace/{job_id}/repo/
   ├── Clone with GitPython (shallow, depth=20)
   ├── Enforce 6 limits (2GB, 500k files, 50MB/file, depth 20, 1000 symlinks)
   ├── Create Repository Snapshot
   └── Set status: cloned → emit WebSocket event
        │
        ▼
4. ParseWorker (queue: parse)
   ├── Build SharedAnalysisContext (AST, SymbolTable, DepGraph, CrossRefIndex)
   ├── 12 language parsers
   ├── Must complete in ≤60 seconds
   └── Inject context into all agent payloads
        │
        ▼
5. Orchestrator (DAG-based parallel dispatch)
   ├── Validate DAG (no cycles)
   ├── Dispatch Wave 1: repo_understanding (no deps)
   ├── Dispatch Wave 2: security, architecture, dependency, code_quality (dep: repo_understanding)
   ├── Dispatch Wave 3: technical_debt (dep: code_quality)
   ├── Dispatch Wave 4: executive_cto (dep: all above)
   ├── Dispatch Wave 5: repository_optimization (dep: executive_cto)
   ├── All stub agents: no deps → run in Wave 1 concurrently
   ├── Concurrency: asyncio.Semaphore(5)
   ├── Timeout: asyncio.wait_for(60s per agent)
   └── Publish AgentCompletedEvent after each
        │
        ▼
6. EventBus publishes JobCompletedEvent
   ├── ReportTrigger → ReportWorker (queue: report) → 5 formats
   ├── WebSocketManager → emit terminal event + close connection
   ├── AuditLogger → audit_logs record
   ├── MetricsCollector → job_metrics + agent_metrics records
   ├── NotificationService → notifications record
   └── KGWorker (queue: kg) → nodes/edges, then EmbeddingWorker (queue: embed)
        │
        ▼
7. Job complete (status: completed | completed_with_warnings)
```

---

## EventBus Architecture

```
┌─────────────────────────────────────────┐
│              Orchestrator                 │
│  (publishes events, never calls          │
│   subscribers directly)                  │
└─────────────┬───────────────────────────┘
              │ publish()
              ▼
┌─────────────────────────────────────────┐
│              EventBus                    │
│  Synchronous, in-process, V1            │
│  Exceptions caught per subscriber       │
└─────────────┬───────────────────────────┘
              │ fan-out to subscribers
    ┌─────────┼─────────┬────────────┬─────────────┐
    ▼         ▼         ▼            ▼             ▼
WebSocket  AuditLog  Metrics  Notifications  ReportTrigger
Manager    Service   Collector   Service       Service
```

**Events:**
- `AgentCompletedEvent` — after each agent finishes
- `JobCompletedEvent` — all agents done, job successful
- `JobFailedEvent` — job aborted
- `JobTerminalEvent` — any terminal state (completed/failed/cancelled/cached)

---

## Worker Queue Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Redis (Celery Broker)                       │
├──────────┬─────────┬──────┬──────┬─────────┬────────┬───────┤
│  clone   │  parse  │  ai  │  kg  │  embed  │ report │cleanup│
└────┬─────┴────┬────┴──┬───┴──┬───┴────┬────┴───┬────┴──┬────┘
     │          │       │      │        │        │       │
     ▼          ▼       ▼      ▼        ▼        ▼       ▼
CloneWorker ParseWkr AIWorker KGWorker EmbedWkr RptWorker CleanupWkr
```

Each queue scales independently via Docker Compose replicas.

---

## Database Schema (19 Entities)

```
users ─────────────────┐
organizations ─────────┤
repositories ──────────┤
analysis_jobs ─────────┼── repository_snapshots
  │                    │
  ├── agent_results    │
  ├── reports          │
  ├── recommendations  │
  ├── kg_nodes ────── kg_edges
  ├── job_metrics      │
  ├── agent_metrics    │
  └── ai_invocation_logs
                       │
audit_logs ────────────┤
notifications ─────────┤
api_keys ──────────────┤
prompt_registry ───────┤
repository_caches ─────┤
ai_models ─────────────┘
```

---

## Security Architecture

```
┌─────────────────────────────────────────────┐
│                   Client                     │
└──────────────────────┬──────────────────────┘
                       │ HTTPS only
                       ▼
┌─────────────────────────────────────────────┐
│  NGINX: TLS + CSP + HSTS + X-Frame-Options  │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  Rate Limiter (Redis sliding window)         │
│  10 req/min unauthenticated per IP           │
│  120 req/min authenticated per user          │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  Authentication                              │
│  GitHub OAuth 2.0 (sole interactive method)  │
│  API Key (bcrypt-hashed, programmatic)       │
│  JWT (24h expiry, Redis denylist on logout)  │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  RBAC Enforcement                            │
│  admin > analyst > viewer                    │
│  Per-endpoint role requirement               │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  Input Sanitization                          │
│  URL allowlist (github/gitlab/bitbucket)     │
│  Shell metacharacter rejection               │
│  Error taxonomy (machine-readable codes)     │
└─────────────────────────────────────────────┘
```

---

## AI Pipeline Architecture

```
Agent
  │
  ▼
AIManager.invoke(agent_name, prompt, expected_schema)
  │
  ├─① Cache Check (Redis: agent_name + hash(prompt))
  │     ├── HIT → return cached, log as cached ($0.00)
  │     └── MISS → continue
  │
  ├─② PromptBuilder.build() → resolve from PromptRegistry (versioned)
  │
  ├─③ ProviderRouter.invoke_with_fallback(prompt, AI_PROVIDER_ORDER)
  │     ├── Provider 1 (30s timeout) → success? return
  │     ├── Provider 2 (30s timeout) → success? return
  │     └── Provider 3 (30s timeout) → success? return
  │          └── AllProvidersFailedError
  │
  ├─④ ResponseParser.validate(response, expected_schema)
  │     ├── Valid → continue
  │     └── Invalid → ONE repair attempt (re-invoke with correction)
  │          ├── Valid after repair → continue
  │          └── Still invalid → return error
  │
  ├─⑤ ResponseCache.set(key, response, TTL)
  │
  └─⑥ InvocationLogger.log(job_id, agent, provider, model, tokens, cost, prompt_version)
          → writes to ai_invocation_logs table
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, TypeScript, TailwindCSS, ShadCN UI, React Query, Zustand, Recharts, react-force-graph |
| API | FastAPI, Pydantic v2, OpenAPI 3.1, uvicorn |
| Auth | GitHub OAuth 2.0, JWT (PyJWT), bcrypt, AES-256 |
| Database | PostgreSQL 15, SQLAlchemy (async), Alembic, pgvector |
| Cache/Queue | Redis 7, Celery 5 |
| AI | Ollama, Anthropic Claude, AWS Bedrock, Titan Embeddings |
| Infra | Docker Compose, NGINX, GitHub Actions |
| Testing | pytest, Hypothesis (PBT), vitest, fast-check |

---

## Performance SLA Targets

| Operation | p95 Target |
|-----------|-----------|
| Clone | ≤ 60s |
| SharedAnalysisContext build | ≤ 60s |
| Each agent | ≤ 60s |
| Knowledge Graph generation | ≤ 90s |
| Report generation (all 5 formats) | ≤ 30s |
| Total end-to-end job | ≤ 10 min |
| Cache hit completion | ≤ 2s |
