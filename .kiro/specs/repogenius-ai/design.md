# Design Document

## RepoGenius AI — Multi-Agent Developer Intelligence and Repository Optimization Platform

---

## Overview

RepoGenius AI is a full-stack SaaS platform that accepts a Git repository URL and produces a
comprehensive optimization analysis via a coordinated suite of specialized AI agents. The system
follows a layered architecture: a React/TypeScript frontend communicates with a versioned FastAPI
backend, which delegates long-running work to Celery async workers, persists state in PostgreSQL,
caches and queues through Redis, and calls AI providers through a resilient fallback chain.

The design is organized around five core concerns:

1. **Repository ingestion** — cloning, workspace lifecycle, and isolation
2. **Multi-agent orchestration** — plugin-discovered agents, BaseAgent contract, Orchestrator
3. **Analytical pipeline** — eight core agents, stub agents, scoring, knowledge graph
4. **Delivery layer** — REST API, WebSocket, reports
5. **Platform concerns** — auth, RBAC, security, AI provider management, infrastructure

> **Version 2 Note:** Code Translation and PR Review are planned Version 2 features. The
> plugin-based agent architecture and extensibility points described in the Extensibility section
> are designed to accommodate these capabilities without breaking changes to the core system.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          NGINX (TLS termination)                    │
│          /api/v1/* → FastAPI   /ws/* → FastAPI   /* → React SPA     │
└───────────────────┬─────────────────────┬───────────────────────────┘
                    │                     │
        ┌───────────▼──────────┐ ┌────────▼──────────┐
        │   FastAPI Backend    │ │  WebSocket Server  │
        │  (REST API v1)       │ │  /ws/jobs/{job_id} │
        └───────────┬──────────┘ └────────┬───────────┘
                    │                     │
        ┌───────────▼─────────────────────▼───────────┐
        │                PostgreSQL                    │
        │     (SQLAlchemy ORM + Alembic migrations)    │
        └──────────────────────┬──────────────────────┘
                               │
        ┌──────────────────────▼──────────────────────┐
        │                  Redis                       │
        │    (Celery broker + result backend +          │
        │     JWT denylist + WebSocket event cache)     │
        └──────────────────────┬──────────────────────┘
                               │
        ┌──────────────────────▼──────────────────────┐
        │              Celery Workers                  │
        │   AnalysisJobTask                            │
        │     └── SharedAnalysisContextBuilder (once) │
        │     └── Orchestrator (DAG-based dispatch)   │
        │         ├── Core Agents (8) — DAG waves     │
        │         └── Stub Agents (17+)               │
        │   EmbeddingWorker (async, non-blocking)      │
        │   CleanupTask (beat)                         │
        │                                              │
        │  EventBus (in-process)                       │
        │    ├── WebSocketManager                      │
        │    ├── AuditLogger                           │
        │    ├── MetricsCollector                      │
        │    ├── NotificationService                   │
        │    └── ReportTrigger                         │
        └──────────────────────┬──────────────────────┘
                               │
        ┌──────────────────────▼──────────────────────┐
        │            AI Provider Chain                 │
        │   Ollama (primary) → Claude → Bedrock        │
        │   (order configurable via AI_PROVIDER_ORDER) │
        │   Titan Embeddings (KG nodes, Bedrock)       │
        └─────────────────────────────────────────────┘
```

---

## Components and Interfaces

### 1. FastAPI Backend (`backend/`)

The backend is the single HTTP surface area exposed to clients. All state mutations flow through it.

**Directory layout (Clean Architecture — 4 layers):**
```
backend/
├── app/
│   ├── main.py                          # App factory + lifespan hooks
│   ├── presentation/                    # Layer 1: HTTP surface
│   │   ├── api/v1/                      # FastAPI route handlers (thin — no business logic)
│   │   │   ├── router.py
│   │   │   ├── repos.py
│   │   │   ├── jobs.py
│   │   │   ├── reports.py
│   │   │   ├── kg.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── history.py
│   │   │   └── admin.py
│   │   └── websocket/
│   │       └── handler.py
│   ├── application/                     # Layer 2: Use case orchestration
│   │   ├── services/
│   │   │   ├── analysis_service.py
│   │   │   ├── report_service.py
│   │   │   ├── optimization_service.py
│   │   │   ├── history_service.py
│   │   │   └── kg_service.py
│   │   ├── event_bus.py                 # EventBus + DomainEvent base
│   │   └── unit_of_work.py              # UnitOfWork context manager
│   ├── domain/                          # Layer 3: Business rules, no framework deps
│   │   ├── entities/                    # Pure Python domain objects
│   │   ├── value_objects/
│   │   ├── events/                      # AgentCompletedEvent, JobCompletedEvent, etc.
│   │   └── repositories/               # Abstract repository interfaces (ABCs)
│   │       ├── analysis_job_repo.py
│   │       ├── user_repo.py
│   │       ├── recommendation_repo.py
│   │       └── ...
│   ├── infrastructure/                  # Layer 4: Framework + external deps
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models/                  # SQLAlchemy ORM models
│   │   ├── repositories/               # Concrete SQLAlchemy repo implementations
│   │   ├── ai/
│   │   │   ├── ai_manager.py
│   │   │   ├── prompt_registry.py
│   │   │   └── embedding_provider.py
│   │   ├── github/
│   │   │   ├── github_service.py
│   │   │   └── rate_limit_manager.py
│   │   ├── config/
│   │   │   └── config_registry.py
│   │   └── workers/
│   │       ├── analysis_task.py
│   │       ├── embedding_worker.py
│   │       └── cleanup_task.py
│   ├── agents/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── orchestrator.py
│   │   ├── shared_context.py            # SharedAnalysisContextBuilder
│   │   ├── payloads.py
│   │   ├── core/
│   │   │   ├── repo_understanding.py
│   │   │   ├── security.py
│   │   │   ├── code_quality.py
│   │   │   ├── architecture.py
│   │   │   ├── dependency.py
│   │   │   ├── technical_debt.py
│   │   │   ├── executive_cto.py
│   │   │   └── optimization.py
│   │   └── stubs/
│   │       ├── stub_base.py
│   │       └── <17+ stub files>
├── alembic/
└── tests/
    ├── unit/
    ├── integration/
    └── property/
```

**Environment variables** (`.env.example` additions):
```
REPO_CACHE_TTL_HOURS=24
ENABLE_KNOWLEDGE_GRAPH=true
ENABLE_OPTIMIZATION_ENGINE=true
ENABLE_EMBEDDINGS=true
ENABLE_CTO_AGENT=true
ENABLE_REPO_CACHE=true
ENABLE_COST_TRACKING=true
```


### 2. Agent System (`backend/app/agents/`)

```
agents/
├── base.py           # BaseAgent abstract class (with depends_on)
├── registry.py       # Plugin registry — auto-discovers all BaseAgent subclasses
├── orchestrator.py   # Orchestrator — builds DAG, dispatches, collects, persists
├── shared_context.py # SharedAnalysisContextBuilder
├── payloads.py       # AgentInputPayload, AgentOutputPayload Pydantic models
├── core/
│   ├── repo_understanding.py
│   ├── security.py
│   ├── code_quality.py
│   ├── architecture.py
│   ├── dependency.py
│   ├── technical_debt.py
│   ├── executive_cto.py
│   └── optimization.py          # Repository Optimization Agent (DAG final node)
└── stubs/
    ├── stub_base.py             # Generic stub that returns status="stub"
    └── <17+ stub files>         # One per planned agent (includes repository_chat.py)
```

#### BaseAgent Interface

```python
from abc import ABC, abstractmethod
from app.agents.payloads import AgentInputPayload, AgentOutputPayload

class BaseAgent(ABC):
    name: str                        # Unique agent identifier
    version: str = "1.0.0"
    depends_on: list[str] = []       # Names of agents whose outputs this agent requires

    async def pre_run(self, payload: AgentInputPayload) -> None:  ...
    async def post_run(self, result: AgentOutputPayload) -> None: ...
    async def on_error(self, exc: Exception) -> None:             ...

    @abstractmethod
    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload: ...
```

#### Agent Dependency DAG

The default dependency graph is:

```python
# agents/orchestrator.py — DAG-based dispatch

DEFAULT_DAG = {
    "repository_understanding": [],
    "security":                 ["repository_understanding"],
    "architecture":             ["repository_understanding"],
    "dependency":               ["repository_understanding"],
    "code_quality":             ["repository_understanding"],
    "technical_debt":           ["code_quality"],
    "executive_cto":            ["security", "architecture", "dependency", "code_quality", "technical_debt"],
    "repository_optimization":  ["executive_cto"],
    # All stubs: no dependencies (run concurrently with first wave)
}
```

Each `BaseAgent` subclass declares its dependencies:

```python
class SecurityAgent(BaseAgent):
    name = "security"
    dependencies = ["repository_understanding"]
```

#### Orchestrator Flow (DAG-based dispatch)

The Orchestrator constructs a directed acyclic graph (DAG) of all registered agents at job
dispatch time based on their `depends_on` declarations. Agents with no dependencies are
dispatched immediately in parallel. As each agent completes, the Orchestrator inspects the DAG
and dispatches any agents whose full dependency set is now satisfied.

```python
# agents/core/optimization.py
class RepositoryOptimizationAgent(BaseAgent):
    name = "repository_optimization"
    depends_on = [
        "repository_understanding", "security", "code_quality",
        "architecture", "dependency", "technical_debt", "executive_cto"
    ]
```

```python
# agents/orchestrator.py
async def run_analysis(job: AnalysisJob) -> None:
    dag = build_dag(registry.get_all())           # merge DEFAULT_DAG with declared deps
    validate_dag(dag)                              # cycle detection — exits non-zero on cycle

    ctx     = SharedAnalysisContextBuilder().build(job.id, job.workspace_path)
    if ctx is None:
        job.status = "failed"; return

    results = {}
    sem     = asyncio.Semaphore(config.orchestrator_concurrency)

    ready   = {a for a in dag if not dag[a]}       # agents with no deps

    while ready:
        tasks = {agent: asyncio.create_task(bounded_run(agent, ctx, sem)) for agent in ready}
        for agent, coro in asyncio.as_completed(tasks.values()):
            result = await coro
            results[result.agent] = result
            await persist_result(job, result)
            event_bus.publish(AgentCompletedEvent(job_id=job.id, agent_name=result.agent,
                                                   status=result.status, ...))
        # Unlock next wave: agents whose deps are all done
        ready = {a for a in dag
                 if a not in results
                 and all(dep in results for dep in dag[a])}

    event_bus.publish(JobCompletedEvent(job_id=job.id))


async def bounded_run(agent, ctx, sem):
    async with sem:
        return await asyncio.wait_for(safe_run(agent, ctx), timeout=config.get_agent_timeout(agent.name))


async def safe_run(agent, payload):
    try:
        await agent.pre_run(payload)
        result = await agent.run(payload)
        await agent.post_run(result)
        return result
    except Exception as exc:
        await agent.on_error(exc)
        return AgentOutputPayload(status="error", agent=agent.name, ...)  # Req 2.4
```

The `validate_dag()` function uses Kahn's algorithm. If a circular dependency is detected at
startup, the Backend exits with a non-zero status code and logs the cycle (Req 2.12).
Dependent agents whose dependency completed with `status: "error"` are still dispatched, but
their `AgentInputPayload.metadata` includes the dependency's error status so the dependent
agent can handle partial inputs (Req 2.4).

#### Plugin Registry

```python
# registry.py
import pkgutil, importlib, inspect
from app.agents.base import BaseAgent

class AgentRegistry:
    _agents: dict[str, type[BaseAgent]] = {}

    def discover(self, package: str = "app.agents") -> None:
        for _, module_name, _ in pkgutil.walk_packages(
            importlib.import_module(package).__path__, prefix=package + "."
        ):
            module = importlib.import_module(module_name)
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if issubclass(cls, BaseAgent) and cls is not BaseAgent:
                    self._agents[cls.name] = cls

    def get_agent(self, name: str) -> BaseAgent:
        return self._agents[name]()

    def get_all(self) -> list[BaseAgent]:
        return [cls() for cls in self._agents.values()]

registry = AgentRegistry()
```


### 3. Agent Payload Schemas

```python
# payloads.py
from pydantic import BaseModel
from typing import Any, Literal

class AgentInputPayload(BaseModel):
    job_id: str
    repo_path: str          # local workspace path: workspace/{job_id}/repo/
    repo_url: str
    metadata: dict[str, Any] = {}
    # metadata["analysis_context"] → SharedAnalysisContext (Req 18.2)
    # metadata["prior_results"]   → dict[str, AgentOutputPayload] for depends_on agents

class AgentFinding(BaseModel):
    severity: Literal["critical", "high", "medium", "low"] | None = None
    description: str
    file_path: str | None = None
    line_number: int | None = None
    category: str | None = None
    owasp_category: str | None = None      # e.g. "A07:2021"
    cwe_id: str | None = None              # e.g. "CWE-798"
    exploitability: str | None = None      # "low" | "medium" | "high"
    fix_difficulty: str | None = None      # "trivial" | "easy" | "medium" | "hard" | "complex"
    estimated_fix_minutes: int | None = None

class AgentOutputPayload(BaseModel):
    agent: str
    status: Literal["success", "error", "stub"]
    findings: list[AgentFinding] = []
    metrics: dict[str, Any] = {}
    summary: str = ""
    error_message: str | None = None
    stack_trace: str | None = None
```

Schemas for all 25+ agents extend or compose `AgentOutputPayload` by adding typed `metrics`
fields while keeping the base contract identical. This allows new agents to be dropped into the
`agents/` package without Orchestrator changes (Req 15.2–15.3).

### 4. Stub Agents

The `stubs/` directory contains 17+ stub agent files, each implementing `BaseAgent` via a shared
`GenericStub` base class. Stubs include (non-exhaustive):

```
repository_chat.py         # Q&A over analysis results — stub in V1, full impl planned V2+
test_coverage.py
ci_cd_analysis.py
performance_profiling.py
api_documentation.py
container_analysis.py
cloud_cost_analysis.py
accessibility_analysis.py
i18n_analysis.py
graphql_analysis.py
database_schema.py
mobile_analysis.py
ml_model_analysis.py
realtime_monitoring.py
compliance_audit.py
refactoring_suggestions.py
changelog_generator.py
```

Every stub returns:
```python
AgentOutputPayload(agent=self.name, status="stub", findings=[], summary="")
```


### 5. AIManager Abstraction

All agent AI calls are routed through `AIManager`, which provides caching, logging, prompt
construction, and provider routing in a single abstraction layer (Req 11.5).

```python
# infrastructure/ai/ai_manager.py
class AIManager:
    def __init__(self, provider_order: list[str], cache: ResponseCache):
        self.router = ProviderRouter(provider_order)
        self.builder = PromptBuilder()          # calls PromptRegistry.get_active(agent_name)
        self.parser = ResponseParser()
        self.cache = cache
        self.logger = InvocationLogger()        # writes AIInvocationLog records

    async def invoke(self, agent_name: str, prompt: str, expected_schema: type[BaseModel]) -> AIResponse:
        cache_key = f"{agent_name}:{hash(prompt)}"
        if cached := await self.cache.get(cache_key):
            await self.logger.log(cached=True, cost_usd=0.0, ...)
            return cached

        response = await self.router.invoke_with_fallback(prompt)

        # Validate — one repair attempt on failure
        try:
            validated = self.parser.validate(response, expected_schema)
        except ValidationError as e:
            repair_prompt = f"{prompt}\n\nPrevious response failed validation: {e}\nPlease fix."
            response = await self.router.invoke_with_fallback(repair_prompt)
            try:
                validated = self.parser.validate(response, expected_schema)
            except ValidationError:
                return AIResponse(status="error", message="Validation failed after repair")

        await self.cache.set(cache_key, validated, ttl=config.ai.cache_ttl_hours * 3600)
        await self.logger.log(...)
        return validated
```

The `provider_order` list is loaded from the `AI_PROVIDER_ORDER` environment variable
(default: `["ollama", "claude", "bedrock"]`). `ProviderRouter.invoke_with_fallback` iterates the
list, retrying the next provider on timeout or error (Req 11.1–11.4). `InvocationLogger` writes
one `AIInvocationLog` record per invocation including `prompt_name` and `prompt_version` from the
`PromptRegistry` (Req 11.6, 23.1, 24.4). `ResponseCache` keys responses by
`hash(repo_content) + agent_name + prompt_hash` in Redis with a configurable TTL
(default 24 hours); a cache hit skips provider invocation (Req 10.8).


### 6. Repository Optimization Engine

The Repository Optimization Agent (`agents/core/optimization.py`) is the DAG terminal node. It
runs after all 7 other Core Agents complete (enforced by `depends_on`), receives their merged
results via `payload.metadata["prior_results"]`, and produces the Optimization Score,
Engineering Maturity Score, Quick Wins list, and four-sprint Optimization Roadmap.

```python
# agents/core/optimization.py
class RepositoryOptimizationAgent(BaseAgent):
    name = "repository_optimization"
    depends_on = [
        "repository_understanding", "security", "code_quality",
        "architecture", "dependency", "technical_debt", "executive_cto"
    ]

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        prior = payload.metadata.get("prior_results", {})
        all_findings = self._merge_all_agent_findings(prior)
        deduped      = self._deduplicate(all_findings)         # content-similarity dedup
        prioritized  = self._assign_priority(deduped)          # critical/high/medium/low
        estimated    = self._estimate_effort(prioritized)       # hours, difficulty, ROI

        quick_wins = self._get_quick_wins(estimated)            # ROI >= 7, difficulty <= easy, <= 2h
        roadmap    = self._build_roadmap(estimated)             # 4 sprints

        score    = self._compute_optimization_score(estimated)
        maturity = self._compute_engineering_maturity(prior)

        return AgentOutputPayload(
            agent=self.name, status="success",
            metrics={
                "optimization_score":          score,
                "engineering_maturity_score":  maturity,
                "maturity_level":              self._maturity_level(maturity),
                "quick_wins":                  quick_wins,
                "optimization_roadmap":        roadmap,
                "total_findings":              len(prioritized),
                "critical_count":              sum(1 for f in prioritized if f.priority == "critical"),
                "high_count":                  sum(1 for f in prioritized if f.priority == "high"),
            }
        )
```

**Optimization Score formula:**
- Base: 100
- Subtract 5 per critical finding, capped at −50
- Subtract 2 per high finding, capped at −20
- Floor: 0

```
score = max(0, 100 - min(critical_count * 5, 50) - min(high_count * 2, 20))
```

**Engineering Maturity Level mapping:**

| Score range | Maturity Level |
|------------|----------------|
| 0 – 24     | Beginner       |
| 25 – 49    | Intermediate   |
| 50 – 74    | Advanced       |
| 75 – 100   | Enterprise     |

**Optimization Roadmap (4 sprints):**
- Sprint 1 — Quick Wins: ROI ≥ 7 and difficulty ≤ `easy`
- Sprint 2 — Security and Critical findings
- Sprint 3 — Architecture findings
- Sprint 4 — Performance and Technical Debt


### 7. Scoring System

```python
# services/scoring.py
WEIGHTS = {
    "repository_health": 0.10,
    "architecture":      0.12,
    "security":          0.15,
    "performance":       0.08,
    "testing":           0.12,
    "documentation":     0.08,
    "maintainability":   0.10,
    "production_readiness": 0.12,
    "technical_debt":    0.13,
}
# Overall Grade = weighted average of non-null scores, weights renormalized

GRADE_MAP = [
    (90, 100, "A"),
    (80,  89, "B"),
    (70,  79, "C"),
    (60,  69, "D"),
    (0,   59, "F"),
]

MATURITY_MAP = [
    (0,  24,  "Beginner"),
    (25, 49,  "Intermediate"),
    (50, 74,  "Advanced"),
    (75, 100, "Enterprise"),
]

def compute_scores(agent_results: list[AgentOutputPayload]) -> ScoreSet:
    """
    Returns a ScoreSet with integer scores in [0,100] or None per dimension.
    Overall Grade excludes any dimension whose agent returned status='error'.
    """
    ...

def to_letter_grade(score: int) -> str:
    for lo, hi, letter in GRADE_MAP:
        if lo <= score <= hi:
            return letter
    raise ValueError(f"Score {score} out of range")

def to_maturity_level(score: int) -> str:
    for lo, hi, level in MATURITY_MAP:
        if lo <= score <= hi:
            return level
    raise ValueError(f"Score {score} out of range")
```


### 8. Knowledge Graph

```python
# db/models/kg_node.py
class KGNode(Base):
    __tablename__ = "kg_nodes"
    id: UUID
    job_id: UUID                    # FK → analysis_jobs
    entity_type: Literal[
        "class", "function", "module", "package", "external_dep",
        "api_endpoint", "environment_variable", "docker_service",
        "sql_table", "http_endpoint", "celery_task",
        "react_component", "route", "hook"
    ]
    name: str
    file_path: str | None
    description: str                # AI-generated
    embedding: list[float] | None   # Titan Embeddings vector (pgvector); nullable until worker completes
    metadata: dict

# db/models/kg_edge.py
class KGEdge(Base):
    __tablename__ = "kg_edges"
    id: UUID
    source_node_id: UUID            # FK → kg_nodes
    target_node_id: UUID            # FK → kg_nodes
    relationship: Literal["imports","inherits","calls","implements","depends_on"]
```

**Async Embedding via EmbeddingWorker:**

After KGNode records are written to the database, a Celery task is enqueued on the `embeddings`
queue (Req 5.4). The `EmbeddingWorker` (`workers/embedding_worker.py`) processes this queue,
calls `BedrockEmbeddingProvider` with each node's content, and updates the node record with the
resulting vector. Report generation does **not** wait for embedding completion — the report
pipeline proceeds immediately after node records are written.

Titan Embeddings are invoked exclusively through `BedrockEmbeddingProvider` — they bypass the
Ollama/Claude fallback chain (Req 11.7).

When `ENABLE_EMBEDDINGS=false`, the `EmbeddingWorker` enqueue step is skipped entirely and all
KG node records are written with `embedding: null` (Req 24.4).
When `ENABLE_KNOWLEDGE_GRAPH=false`, KG node and edge generation is skipped; KG API endpoints
return HTTP 503 with a `feature_disabled` body (Req 24.2).


### 9. Report Generation

Reports are generated by a `ReportService` triggered by the Orchestrator when all agent results
are collected. Five report types are produced per Analysis Job.

```python
# services/report_service.py
class ReportService:
    async def generate_all(self, job: AnalysisJob) -> list[Report]:
        context     = self._build_context(job)          # scores, findings, trend data
        html        = await self._render_html(context)
        pdf         = await self._render_pdf(html)       # headless Chrome / WeasyPrint
        md          = await self._render_markdown(context)
        json_r      = self._render_json(context)         # OpenAPI-compliant Report schema
        opt_report  = await self._render_optimization_report(context)  # HTML + PDF
        return await self._persist_all([html, pdf, md, json_r, *opt_report], job)
```

**Report formats:**

| Format               | Description                                                        |
|---------------------|--------------------------------------------------------------------|
| HTML                | All scores, agent findings, recommendations, score trend charts    |
| PDF                 | Print-ready rendering of HTML report with embedded charts          |
| Markdown            | Plain-text structured report for developer consumption             |
| JSON                | Machine-readable; conforms to published OpenAPI Report schema      |
| Optimization Report | HTML + PDF; sections: Executive Summary → Optimization Score → Priority Matrix → Quick Wins → Architecture Findings → Security Findings → Technical Debt → Appendix |

- Reports are stored in the filesystem (configurable: local or S3-compatible object storage).
- Download URLs are pre-signed with a 1-hour TTL (Req 6.6).
- Retention policy enforces minimum 30-day file lifetime (Req 6.7).
- Secret values detected by the Security Agent are redacted before any report is persisted
  (Req 10.7): only `file_path` and `line_number` are stored.


### 10. WebSocket Manager

```python
# websocket/manager.py
class WebSocketManager:
    _connections: dict[str, list[WebSocket]]   # job_id → active connections
    _event_log: dict[str, deque[WSEvent]]      # job_id → last N events (60s window)

    async def connect(self, job_id: str, ws: WebSocket) -> None:
        """On connect: replay all events emitted within the last 60 seconds."""
        await ws.accept()
        missed = self._get_missed_events(job_id)   # Req 8.5
        for event in missed:
            await ws.send_json(event.dict())
        await ws.send_json(self._current_status(job_id))  # Req 8.2
        self._connections.setdefault(job_id, []).append(ws)

    async def emit(self, job_id: str, event: WSEvent) -> None:
        """Persist to replay buffer, fan-out to all connected clients."""
        self._event_log.setdefault(job_id, deque()).append(event)
        for ws in self._connections.get(job_id, []):
            await ws.send_json(event.dict())

class WSEvent(BaseModel):
    job_id: str
    status: str
    progress_percentage: int        # 0–100
    current_step: str
    timestamp: datetime
```


### 11. Authentication & Authorization

```
Auth flow:
  GitHub OAuth  →  /auth/github/callback  →  create/update User  →  issue JWT
  API Key       →  Authorization: ApiKey <key>  →  hash(key) lookup in DB

JWT claims:
  { sub: user_id, roles: ["analyst"], exp: now + 24h, jti: uuid }

Denylist (Redis):
  Key:  "jwt:denylist:{jti}"
  TTL:  remaining seconds until exp
  On logout: SET jwt:denylist:{jti} 1 EX {ttl}
  On request: EXISTS jwt:denylist:{jti}  → 401 if true
```

RBAC permission table:

| Endpoint category          | viewer | analyst | admin |
|---------------------------|--------|---------|-------|
| GET repositories / jobs   | ✓      | ✓       | ✓     |
| POST repositories / jobs  | —      | ✓       | ✓     |
| DELETE jobs / reports     | —      | —       | ✓     |
| Admin endpoints            | —      | —       | ✓     |

API Keys are stored as `bcrypt(key, cost=12)` in the `api_keys` table. The raw key is shown
only once at creation time and never stored (Req 9.3).


### 12. AI Provider Management

```python
# core/ai_provider.py — invoked via AIManager.router

async def invoke_with_fallback(prompt: str, provider_order: list[str], **kwargs) -> AIResponse:
    providers = [PROVIDER_MAP[name] for name in provider_order]
    for provider in providers:
        try:
            start  = time.monotonic()
            result = await provider.invoke(prompt, **kwargs)
            _log_invocation(provider, success=True,
                            latency_ms=(time.monotonic()-start)*1000, ...)
            return result
        except (ProviderError, asyncio.TimeoutError) as exc:
            _log_invocation(provider, success=False, ...)
            continue
    raise AllProvidersFailedError()
```

Provider order is loaded from `AI_PROVIDER_ORDER` (default: `["ollama", "claude", "bedrock"]`).
Titan Embeddings are invoked exclusively through `BedrockEmbeddingProvider` and bypass the
fallback chain (Req 11.7).


---

## SharedAnalysisContext (Repository Parser Layer)

The `SharedAnalysisContext` is a pre-computed, immutable, read-only representation of the
cloned repository built once before any agents are dispatched. Every agent consumes it via
`AgentInputPayload.metadata["analysis_context"]` instead of re-reading source files.

```
Repository
    │
    ▼
SharedAnalysisContextBuilder (agents/shared_context.py)
    │
    ├── Language Map (language → list of file paths)
    ├── File Index (path → FileMetadata)
    ├── AST Cache (per-file AST, keyed by path)
    ├── Symbol Table (qualified_name → SymbolInfo)
    ├── Dependency Graph (module-level imports)
    ├── Git Metadata (commit SHA, branch, tags, contributors)
    └── Framework Detection (primary_framework, detected_patterns)
            │
            ▼
    SharedAnalysisContext (injected into every agent)
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
Security  Arch  Code Quality
    ▼       ▼       ▼
Dependency  TechDebt  Executive CTO
            │
            ▼
    Repository Optimization
```

```python
# agents/shared_context.py

@dataclass
class SharedAnalysisContext:
    """Immutable, read-only context built once per Analysis Job and injected into every agent."""
    job_id: str
    repo_path: str
    commit_sha: str
    branch: str
    language_map: dict[str, list[str]]          # language → list of file paths
    file_index: dict[str, FileMetadata]          # path → FileMetadata(language, size, parse_error)
    ast_cache: dict[str, ASTNode | None]         # path → AST (None if unsupported/parse_error)
    symbol_table: dict[str, SymbolInfo]          # qualified_name → SymbolInfo
    dependency_graph: DependencyGraph            # edges: module → imports
    git_metadata: GitMetadata                    # commit_sha, branch, contributors, tags
    framework_detection: FrameworkDetection      # primary_framework, detected_patterns
    cross_reference_index: CrossReferenceIndex   # per-symbol definition, references, call graph
    supported_languages = {
        "python", "javascript", "typescript", "java", "go",
        "rust", "csharp", "cpp", "php", "ruby", "kotlin", "swift"
    }
```

The `CrossReferenceIndex` maps every tracked symbol to its definition location, all references,
imports, and call graph edges. It is built by `SharedAnalysisContextBuilder` as part of the
single parse pass, before any agents are dispatched:

```python
@dataclass
class SymbolReference:
    file_path: str
    line_number: int

@dataclass
class CrossReferenceEntry:
    defined_in: SymbolReference
    referenced_by: list[SymbolReference]
    imported_by: list[str]          # file paths
    calls: list[str]                # symbol qualified names
    called_by: list[str]            # symbol qualified names

@dataclass
class CrossReferenceIndex:
    symbols: dict[str, CrossReferenceEntry]   # qualified_name → entry
    # Covers: functions, classes, methods, constants, exported variables,
    # HTTP routes, React components, React hooks, Celery tasks
```

The KG service uses `CrossReferenceIndex` to populate `calls`, `called_by`, `imports`, and
`depends_on` edges in the Knowledge Graph — no independent file re-parsing is performed for
edge extraction (Req 32.4). The index is read-only; no agent may mutate it (Req 32.3).

```python
class SharedAnalysisContextBuilder:
    def build(self, job_id: str, repo_path: str) -> SharedAnalysisContext | None:
        """
        Parse repository exactly once. Build complete context in ≤ 60 seconds.
        If AST parsing fails for a file, mark file.parse_error=True, skip from AST cache.
        Unsupported languages: included in file_index with language="unsupported".
        CrossReferenceIndex is built during this single parse pass.
        Returns None if build fails (Orchestrator marks job failed).
        """
        ...
    def build(self, job_id: str, repo_path: str) -> SharedAnalysisContext | None:
        """
        Parse repository exactly once. Build complete context in ≤ 60 seconds.
        If AST parsing fails for a file, mark file.parse_error=True, skip from AST cache.
        Unsupported languages: included in file_index with language="unsupported".
        Returns None if build fails (Orchestrator marks job failed).
        """
        ...
```

The Orchestrator builds the context BEFORE dispatching any agents:

```python
async def run_analysis(job: AnalysisJob) -> None:
    # Build shared context once
    ctx = SharedAnalysisContextBuilder().build(job.id, job.workspace_path)
    if ctx is None:
        job.status = "failed"; return

    # Inject into every agent payload
    payloads = {agent: build_payload(job, agent, shared_ctx=ctx) for agent in all_agents}
    ...
```

`SharedAnalysisContext` is passed to every agent via
`AgentInputPayload.metadata["analysis_context"]`. Agents MUST use it instead of re-reading
files (Req 18.2). The context build step is logged upon completion (Req 18.4).

---

## GitHubService and Rate Limit Management

All GitHub API interactions are routed through `GitHubService`, which embeds a
`RateLimitManager` to handle primary and secondary rate limits transparently.

```python
# infrastructure/github/rate_limit_manager.py
class RateLimitManager:
    _remaining: int = 5000
    _reset_at: datetime = None

    def update_from_headers(self, headers: dict) -> None:
        self._remaining = int(headers.get("X-RateLimit-Remaining", 5000))
        self._reset_at  = datetime.fromtimestamp(int(headers.get("X-RateLimit-Reset", 0)))

    async def wait_if_exhausted(self) -> None:
        if self._remaining < 50:
            wait_secs = max(0, (self._reset_at - datetime.utcnow()).total_seconds()) + 1
            await asyncio.sleep(wait_secs)


# infrastructure/github/github_service.py
class GitHubService:
    def __init__(self, token: str, rate_limiter: RateLimitManager):
        self._client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
        self._rl     = rate_limiter
        self._etags: dict[str, str] = {}

    async def get(self, path: str) -> dict | None:
        await self._rl.wait_if_exhausted()
        headers = {}
        if etag := self._etags.get(path):
            headers["If-None-Match"] = etag          # conditional request

        for attempt in range(3):
            resp = await self._client.get(f"https://api.github.com{path}", headers=headers)
            self._rl.update_from_headers(dict(resp.headers))
            if resp.status_code == 304: return None  # not modified
            if resp.status_code in (429, 403):
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 1))  # exponential backoff + jitter
                continue
            if resp.status_code == 200:
                if etag := resp.headers.get("ETag"):
                    self._etags[path] = etag
                return resp.json()
        return None  # mark field as unavailable after 3 retries

    async def get_repository_metadata(self, repo_url: str) -> dict: ...
    async def get_latest_commit_sha(self, repo_url: str) -> str: ...
    async def get_branch_protection(self, owner: str, repo: str) -> dict: ...
```

When remaining quota falls below 50, `RateLimitManager.wait_if_exhausted()` pauses further
calls until the reset timestamp (Req 19.3). ETag conditional requests avoid consuming quota for
unchanged resources (Req 19.4). Exponential backoff with jitter is applied on HTTP 429 and 403
responses, retrying up to 3 times before returning `None` for the affected field
(Req 19.5). All GitHub API calls across all agents and services go exclusively through
`GitHubService` (Req 19.6).

---

## Repository Cache Service

The `RepoCacheService` avoids redundant clone-and-analysis cycles when the repository content
has not changed since the last completed job.

```python
# infrastructure/workers/ (invoked from analysis_task.py)
class RepoCacheService:
    async def get_content_hash(self, repo_url: str) -> str:
        """Fetch latest commit SHA from GitHub API; use as content_hash."""
        return await self.github_service.get_latest_commit_sha(repo_url)

    async def find_cached_job(
        self, repo_url: str, content_hash: str, ttl_hours: int
    ) -> AnalysisJob | None:
        """Return most recent completed job for same repo_url + content_hash
        completed within ttl_hours; None if not found or ENABLE_REPO_CACHE=false."""
        ...

    async def clone_or_cache(self, job: AnalysisJob) -> str:
        """Returns workspace path.
        On cache hit: copy agent results, emit WS event, mark job complete.
        On cache miss: proceed with normal clone + analysis."""
        ...
```

**Cache hit flow:**
1. Compute `content_hash` from GitHub API (latest commit SHA)
2. Query DB for matching completed job for same `repo_url` + `content_hash` within TTL
3. **On hit:** copy agent results + scores to new job; set `cache_hit=true`; emit WS
   `completed` event with `cache_hit: true`; skip clone and orchestrator; complete within
   2 seconds (Req 20.2, 20.4)
4. **On miss:** normal clone + analysis flow (Req 20.3)

Cache TTL is configurable via `REPO_CACHE_TTL_HOURS` (default: 24 hours, Req 20.5).
When `ENABLE_REPO_CACHE=false`, `find_cached_job` always returns `None` and a full clone +
analysis is always performed (Req 24.5).

---

## EventBus

The `EventBus` decouples the Orchestrator from all downstream concerns: WebSocket updates,
audit logging, metrics collection, notification delivery, and report generation (Req 21.1–21.5).

```python
# application/event_bus.py

@dataclass
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class AgentCompletedEvent(DomainEvent):
    job_id: str
    agent_name: str
    status: str
    duration_ms: int
    finding_count: int

@dataclass
class JobCompletedEvent(DomainEvent):
    job_id: str

@dataclass
class JobFailedEvent(DomainEvent):
    job_id: str
    reason: str

class EventBus:
    _handlers: dict[type[DomainEvent], list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception as exc:
                logger.error("EventBus subscriber failed: %s", exc)
                # Never propagate to Orchestrator

# Registered subscribers at startup:
event_bus.subscribe(AgentCompletedEvent, ws_manager.on_agent_completed)
event_bus.subscribe(AgentCompletedEvent, audit_logger.on_agent_completed)
event_bus.subscribe(AgentCompletedEvent, metrics_collector.on_agent_completed)
event_bus.subscribe(JobCompletedEvent,   report_trigger.on_job_completed)
event_bus.subscribe(JobCompletedEvent,   notification_service.on_job_completed)
event_bus.subscribe(JobFailedEvent,      notification_service.on_job_failed)
```

Subscriber exceptions are caught and logged; they never propagate to the Orchestrator's
`publish()` call (Req 21.5).

---

## Repository Snapshot

An immutable snapshot of repository state is created when cloning completes and linked to
every Analysis Job for reproducibility (Req 1.9, 1.10).

```python
# domain/entities/repository_snapshot.py
@dataclass(frozen=True)
class RepositorySnapshot:
    id: UUID
    job_id: UUID
    commit_sha: str
    branch: str
    repository_url: str
    clone_timestamp: datetime
    default_branch: str
```

All reports generated for an Analysis Job reference the associated Repository Snapshot so that
any report is reproducible by re-cloning the same commit SHA.

---

## LLM Cost Tracking

Every AI provider invocation is recorded in `ai_invocation_logs` for cost visibility and
query-ability by job, agent, and provider (Req 23.1–23.4).

```python
# infrastructure/db/models/ai_invocation_log.py
class AIInvocationLog(Base):
    __tablename__ = "ai_invocation_logs"
    id:                UUID       # PK
    job_id:            UUID       # FK → analysis_jobs
    agent_name:        str
    provider:          str        # "ollama" | "claude" | "bedrock"
    model:             str
    prompt_name:       str
    prompt_version:    int
    input_tokens:      int
    output_tokens:     int
    latency_ms:        int
    estimated_cost_usd: float
    cached:            bool
    created_at:        datetime
```

`InvocationLogger` (part of `AIManager`) writes one record per call. Pricing constants are
stored in `ConfigRegistry`. When `cached=true`, `estimated_cost_usd` is set to `0.0`
(Req 23.4).

On job completion, `analysis_task.py` aggregates per-job totals and writes them to
`analysis_jobs`:
- `total_input_tokens`, `total_output_tokens`, `total_estimated_cost_usd`,
  `total_ai_latency_ms`, `cache_hit_count`

---

## Prompt Registry

All AI prompt templates are version-controlled via a database-backed `PromptRegistry`. Old
versions are never deleted, enabling report reproduction by re-running the same prompt version
against the same repository snapshot (Req 24.1–24.4).

```python
# infrastructure/ai/prompt_registry.py

class PromptVersion(Base):
    __tablename__ = "prompt_registry"
    id:          UUID       # PK
    prompt_name: str
    version:     int
    content:     str
    checksum:    str        # SHA-256(content)
    author:      str
    created_at:  datetime
    is_active:   bool


class PromptRegistry:
    async def get_active(self, prompt_name: str) -> PromptVersion:
        """Returns the record with is_active=True for this prompt_name."""
        ...

    async def register(self, prompt_name: str, content: str, author: str) -> PromptVersion:
        """Deactivates previous version; inserts new record with version+1, is_active=True."""
        ...
```

`PromptBuilder` resolves prompts via `PromptRegistry` at runtime:

```python
class PromptBuilder:
    async def build(self, agent_name: str, ctx: SharedAnalysisContext) -> str:
        prompt_version = await self.registry.get_active(f"agent.{agent_name}")
        return prompt_version.content.format(**ctx.__dict__)
```

`prompt_name` and `prompt_version` are stored in every `AIInvocationLog` record (Req 24.4).
Once a prompt record is inserted, its `content` and `checksum` are never modified — updates
always insert a new record with a higher version (Req 24.3).

---

## ConfigRegistry

All configuration is accessed through a single typed `ConfigRegistry` singleton (Req 25.1–25.4).

```python
# infrastructure/config/config_registry.py
class AISettings(BaseModel):
    provider_order: list[str] = ["ollama", "claude", "bedrock"]
    default_timeout_seconds: int = 60
    per_agent_timeouts: dict[str, int] = {}   # overrides per agent name
    cache_ttl_hours: int = 24

class FeatureFlagSettings(BaseModel):
    enable_kg: bool = True
    enable_optimization: bool = True
    enable_reports: bool = True
    enable_embeddings: bool = True
    enable_executive_cto: bool = True
    enable_github_metadata: bool = True

class ConfigRegistry(BaseSettings):
    ai: AISettings = AISettings()
    features: FeatureFlagSettings = FeatureFlagSettings()
    database_url: str
    redis_url: str
    secret_key: str
    github_client_id: str
    github_client_secret: str
    # ... all other env vars

    def get_agent_timeout(self, agent_name: str) -> int:
        return self.ai.per_agent_timeouts.get(agent_name, self.ai.default_timeout_seconds)

    class Config:
        env_file = ".env"

config = ConfigRegistry()  # singleton — read ONCE at startup
```

`ConfigRegistry` is validated at startup; if any required value is missing or invalid, the
Backend exits with a non-zero status code and a descriptive error message (Req 25.3).

---

## Feature Flags

Runtime feature flags allow platform capabilities to be toggled without redeployment (Req 22.1).

```python
# Feature flags are part of FeatureFlagSettings in ConfigRegistry

# Usage example in analysis_task.py
if not config.features.enable_kg:
    logger.info("Knowledge Graph disabled by feature flag; skipping KG generation")
else:
    await kg_service.generate_nodes(job, agent_results)
    if config.features.enable_embeddings:
        await embedding_worker.enqueue(job)
```

**Feature flag enforcement points:**

| Flag                     | Effect when `false`                                                          |
|--------------------------|------------------------------------------------------------------------------|
| `ENABLE_KG`              | Skip KG generation + embedding enqueue; KG endpoints return HTTP 503 with `feature_disabled` |
| `ENABLE_OPTIMIZATION`    | Skip Repository Optimization Agent dispatch; Optimization Score + Engineering Maturity Score → `null` |
| `ENABLE_EMBEDDINGS`      | Skip EmbeddingWorker enqueue; KG nodes written with `embedding=null`         |
| `ENABLE_EXECUTIVE_CTO`   | Skip Executive CTO Agent dispatch                                            |
| `ENABLE_GITHUB_METADATA` | Repository Understanding Agent skips all GitHub API calls; GitHub metadata fields → `null` |
| `ENABLE_REPORTS`         | Skip report generation; report endpoints return HTTP 503 with `feature_disabled` |



---

## Data Models

### Database Entities (SQLAlchemy ORM) — 19 Entities

| Entity                  | Key Fields                                                                                     |
|-------------------------|-----------------------------------------------------------------------------------------------|
| `users`                 | id, github_id, email, password_hash, oauth_token_enc, role, created_at                       |
| `organizations`         | id, name, owner_id                                                                            |
| `repositories`          | id, url, owner_id, org_id, last_analyzed_at                                                  |
| `analysis_jobs`         | id, repo_id, status (`pending`\|`queued`\|`cloning`\|`cloned`\|`running`\|`completed`\|`completed_with_warnings`\|`failed`\|`cancel_requested`\|`cancelled`\|`retrying`\|`paused`\|`cached`), progress_pct, optimization_score (int nullable), engineering_maturity_score (int nullable), content_hash, cache_hit, commit_sha, branch_name, analysis_version, agent_bundle_version, schema_version, agent_errors (JSON array), total_input_tokens, total_output_tokens, total_estimated_cost_usd, cache_hit_count, created_at, completed_at |
| `repository_snapshots`  | id, job_id (FK → analysis_jobs), commit_sha, branch, repository_url, clone_timestamp, default_branch |
| `agent_results`         | id, job_id, agent_name, agent_version, status, prompt_name, prompt_version, model, provider, payload_json, created_at |
| `reports`               | id, job_id, format, storage_path, created_at, expires_at                                     |
| `recommendations`       | id, job_id, title, description, severity, difficulty, estimated_hours (float), impact, roi (float), category, affected_files (JSON), related_agent, confidence (float), references (JSON), suggested_sprint (int nullable), priority, created_at |
| `kg_nodes`              | id, job_id, entity_type, name, file_path, description, embedding (pgvector nullable)         |
| `kg_edges`              | id, source_id, target_id, relationship                                                       |
| `audit_logs`            | id, user_id, event_type, ip_address, outcome, user_agent, request_id, endpoint, latency_ms, session_id, created_at |
| `notifications`         | id, user_id, job_id, type, message, read, created_at                                         |
| `api_keys`              | id, user_id, key_hash, name, last_used_at, created_at                                        |
| `ai_invocation_logs`    | id, job_id, agent_name, provider, model, prompt_name, prompt_version, input_tokens, output_tokens, latency_ms, estimated_cost_usd (float), cached, created_at |
| `prompt_registry`       | id, prompt_name, version (int), content, checksum (SHA-256), author, created_at, is_active   |
| `repository_caches`     | id, repo_url, branch, commit_sha, analysis_version, prompt_versions_hash, job_id (FK → analysis_jobs), clone_path, size_bytes, last_used_at, created_at |
| `ai_models`             | id, provider, model_name, context_window (int), input_price_per_1k_tokens (float), output_price_per_1k_tokens (float), status, updated_at |
| `job_metrics`           | id, job_id (FK → analysis_jobs), clone_duration_ms, parse_duration_ms, kg_duration_ms, report_duration_ms, total_duration_ms, peak_memory_mb, total_tokens, total_cost_usd, cache_hit_count, agent_error_count, created_at |
| `agent_metrics`         | id, job_id (FK → analysis_jobs), agent_name, execution_time_ms, cache_hits, retry_count, input_tokens, output_tokens, estimated_cost_usd, status, created_at |

All tables have appropriate foreign key constraints and indexes on foreign keys and
frequently-queried columns (status, created_at, user_id) to support pagination and filtering
(Req 13.3).

### Recommendation Schema (SQLAlchemy + Pydantic)

```python
class Recommendation(Base):
    __tablename__ = "recommendations"
    id: UUID
    job_id: UUID                    # FK → analysis_jobs
    title: str
    description: str
    severity: Literal["critical","high","medium","low"]
    difficulty: Literal["trivial","easy","medium","hard","complex"]
    estimated_hours: float
    impact: Literal["low","medium","high","critical"]
    roi: float                      # 0–10
    category: str
    affected_files: list[str]       # JSON array
    related_agent: str
    confidence: float               # 0–1
    references: list[str]           # JSON array
    suggested_sprint: int | None    # 1–4
    priority: Literal["critical","high","medium","low"]
    created_at: datetime
```


### REST API Catalogue

All endpoints are under `/api/v1/`. Full schema available at `/api/v1/docs`.

```
POST   /api/v1/repos/analyze             Submit repository for analysis
GET    /api/v1/jobs/{job_id}             Get Analysis Job status
GET    /api/v1/jobs/{job_id}/results     Get agent results for a job
GET    /api/v1/jobs/{job_id}/cost        Per-job cost breakdown by agent/provider
POST   /api/v1/jobs/{job_id}/cancel      Cancel a running/queued job
POST   /api/v1/jobs/{job_id}/retry       Retry a failed/cancelled job
POST   /api/v1/jobs/{job_id}/pause       Pause a running job
POST   /api/v1/jobs/{job_id}/resume      Resume a paused job
GET    /api/v1/reports/{job_id}          List reports for a job
GET    /api/v1/reports/{id}/download     Get pre-signed download URL
GET    /api/v1/kg/{job_id}/nodes         Paginated Knowledge Graph nodes
GET    /api/v1/kg/{job_id}/edges         Paginated Knowledge Graph edges
GET    /api/v1/repos/{repo_id}/history   Paginated analysis history with scores
GET    /api/v1/agents                    List all registered agents with metadata
GET    /api/v1/providers                 Current AI provider config + rate limit status
GET    /api/v1/system/status             Platform version, uptime, queue depths, flags
GET    /api/v1/system/version            API version, engine version, schema version, git SHA (no auth)
GET    /api/v1/feature-flags             Current feature flag state (admin only)
GET    /api/v1/prompts                   Prompt registry listing (admin only)
GET    /api/v1/admin/cost-report         Aggregated AI cost by provider/agent/model/date (admin only)
GET    /auth/github                      GitHub OAuth redirect
GET    /auth/github/callback             GitHub OAuth callback
POST   /auth/logout                      Logout (JWT denylist)
POST   /api/v1/users/api-keys            Create API Key
GET    /api/v1/admin/users               List users (admin only)
GET    /health                           Subsystem health check
GET    /ready                            Readiness probe
GET    /live                             Liveness probe
GET    /metrics                          Prometheus metrics
```

### WebSocket

```
WS /ws/jobs/{job_id}
```

Event payload schema (Req 8.3):
```json
{
  "job_id": "uuid",
  "status": "running | completed | failed",
  "progress_percentage": 42,
  "current_step": "Security Agent completed",
  "timestamp": "2024-01-15T10:30:00Z"
}
```


---

## Error Handling

| Scenario                                  | Behavior                                                              |
|-------------------------------------------|-----------------------------------------------------------------------|
| Invalid repo URL submitted                | HTTP 422 with field-level error; no DB record created (Req 1.3)      |
| Clone fails (auth / timeout / not found)  | Job status → `failed`; error message persisted; WS event (Req 1.4)   |
| Repo exceeds 2 GB                         | Clone aborted; job → `failed`; reason recorded (Req 1.5)             |
| File count > 500k                         | Clone aborted; job → `failed`; limit breach recorded (Req 1.6)       |
| Individual file > 50 MB                   | Clone aborted; job → `failed`; limit breach recorded (Req 1.6)       |
| Directory depth > 20                      | Clone aborted; job → `failed`; limit breach recorded (Req 1.6)       |
| Symlink count > 1,000                     | Clone aborted; job → `failed`; limit breach recorded (Req 1.6)       |
| Agent throws unhandled exception          | Agent result → `error`; stack trace logged; other agents proceed (Req 2.4) |
| Agent exceeds per-agent timeout           | Treated as exception; agent → `error`; others continue (Req 2.8)     |
| All AI providers fail                     | Agent result → `error`; analysis continues (Req 11.4)                |
| JWT expired or denylisted                 | HTTP 401 (Req 9.7)                                                    |
| Insufficient RBAC role                    | HTTP 403 (Req 7.8)                                                    |
| Schema validation failure                 | HTTP 422 with per-field violation messages (Req 7.6)                  |
| Rate limit exceeded                       | HTTP 429 (Req 7.3)                                                    |
| DB connectivity failure on startup        | Backend exits with non-zero status code (Req 13.4)                   |
| `snapshot_mismatch`                       | Job status → `failed` with reason `snapshot_mismatch`; no agent execution proceeds (Req 23.2) |
| GitHub API rate limit exhausted           | Affected agent fields set to `null`; agent continues; `GITHUB_RATE_LIMIT_EXHAUSTED` event logged (Req 19.4) |
| `ENABLE_KG=false`                         | KG endpoints return HTTP 503 with `feature_disabled` body (Req 22.2) |
| Circular agent dependency detected        | Backend exits with non-zero status code; cycle logged at startup (Req 2.12) |
| SharedAnalysisContext build fails         | Orchestrator marks job `failed`; emits failure WebSocket event (Req 18.4) |
| GitHub API rate limit < 50 remaining      | RateLimitManager waits until reset timestamp, retries; field marked unavailable after 3 retries (Req 19.3, 19.5) |
| Agent DAG cycle detected at startup       | Backend exits non-zero; cycle logged (Req 2.12)                      |
| AI response validation fails after repair | Agent result marked `error` (Req 11.8)                               |
| Feature flag disabled (e.g., `ENABLE_KG=false`) | Component skipped; job continues without that feature (Req 22.1) |

**Workspace layout** (per job):
```
workspace/{job_id}/
├── repo/       # read-only clone
├── analysis/   # intermediate analysis artifacts
└── logs/       # per-job log files
```

No two jobs share a workspace directory — all paths are scoped under the unique `job_id`.

**Workspace cleanup:** The `CleanupTask` Celery beat task runs every 5 minutes and deletes
repository workspaces older than 1 hour from the filesystem (Req 10.3). Cleanup is idempotent —
if the directory was already removed, the task logs a warning and continues.

**Cloning limits enforced before analysis begins:**
- Maximum repository size: 2 GB
- Maximum file count: 500,000
- Maximum individual file size: 50 MB
- Maximum directory depth: 20
- Maximum symlink count: 1,000
- Clone depth: 20 (shallow clone)

**Input sanitization:** All repository URLs are validated against an allowlist regex
(`^https?://[a-zA-Z0-9._/-]+$`) and the permitted host allowlist
(`github.com`, `gitlab.com`, `bitbucket.org`) before being passed to GitPython. Shell
metacharacters are rejected at the schema validation layer (Req 10.4–10.5).

---

## Frontend Architecture

```
frontend/
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx           # Hero: OptScore + Grade + RepoHealth + EngMaturity;
│   │   │                           #   then 9 dimension scores (Recharts gauges)
│   │   ├── RepositoryAnalysis.tsx  # Submit URL, WS progress, agent results,
│   │   │                           #   full-text search across findings,
│   │   │                           #   comparison view with score deltas
│   │   ├── Reports.tsx
│   │   ├── KnowledgeGraph.tsx      # Force-directed graph (react-force-graph or D3)
│   │   ├── Agents.tsx
│   │   ├── Settings.tsx            # Theme toggle (dark/light, persisted to localStorage)
│   │   ├── Profile.tsx
│   │   ├── Admin.tsx
│   │   ├── AnalysisQueue.tsx       # Active/pending jobs; Cancel/Retry/Pause/Resume buttons
│   │   ├── Notifications.tsx       # User notifications; mark-as-read, clear-all
│   │   ├── APIKeys.tsx             # Create/list/revoke API keys
│   │   ├── CostDashboard.tsx       # Provider/agent cost breakdown, cache hit %, daily/monthly spend (Recharts)
│   │   └── SystemHealth.tsx        # Subsystem status cards from /health; auto-refresh; queue depths; GitHub quota
│   ├── components/                 # ShadCN-based reusable components
│   ├── stores/
│   │   └── useAppStore.ts          # Zustand: auth user, active job, notifications, theme
│   ├── hooks/
│   │   ├── useJobWebSocket.ts      # WS connection + event handler per job
│   │   └── useAuth.ts              # JWT expiry detection → redirect (Req 12.8)
│   ├── api/
│   │   └── client.ts               # React Query wrappers over fetch
│   └── lib/
│       └── utils.ts
```

**Pages (13 total):**
- **Dashboard** — hero metrics: Optimization Score, Repository Grade, Repository Health,
  Engineering Maturity Score (prominent, top of page); followed by 9 dimension score
  gauge/ring charts (Recharts); recent jobs list; notifications
- **Repository Analysis** — submit URL; real-time WebSocket progress panel; agent results;
  full-text search across all findings; comparison view showing two jobs side-by-side with
  score delta indicators; Repository Timeline chart (score history via Recharts)
- **Reports** — list and download reports (HTML, PDF, MD, JSON, Optimization Report)
- **Knowledge Graph** — interactive force-directed graph; node detail panel
- **Agents** — catalog of all 25+ agents, status (core/stub), last-run output
- **Settings** — API keys; preferences; theme toggle (dark/light, persisted to localStorage);
  notification settings
- **Profile** — user account, GitHub OAuth connection, activity history
- **Admin** — user management, audit log viewer, feature flags viewer, prompt registry (admin role only)
- **AnalysisQueue** — active/pending jobs with status, progress, Cancel/Retry/Pause/Resume buttons
- **Notifications** — user notifications with mark-as-read, clear-all
- **APIKeys** — create/list/revoke API keys
- **CostDashboard** — provider/agent cost breakdown, cache hit %, money saved, daily/monthly spend (Recharts)
- **SystemHealth** — subsystem status cards from `/health`, auto-refresh, queue depths, GitHub quota

**State management:**
- **React Query**: all server state (jobs, reports, KG data, scores). Automatic background
  refetch, loading/error states surfaced through ShadCN skeletons and toasts.
- **Zustand**: client-only state — authenticated user object, active job reference, notification
  queue, theme preference (dark/light).

**JWT expiry:** `useAuth` hook inspects the JWT `exp` claim. A `setTimeout` fires 30 seconds
before expiry; on trigger, it clears the Zustand auth state, redirects to `/login`, and displays
a toast message (Req 12.8).


---

## Infrastructure

**Docker Compose services:**
- `backend` — FastAPI (uvicorn), hot-reload in dev via volume mount
- `frontend` — Vite dev server in dev; nginx serving dist/ in prod
- `postgres` — PostgreSQL 15
- `redis` — Redis 7
- `celery_worker` — same image as backend, `CMD celery worker`
- `celery_beat` — scheduled `CleanupTask`
- `nginx` — TLS termination, static asset serving, reverse proxy

**Environment variables** (never hardcoded; Req 14.6):
```
DATABASE_URL, REDIS_URL, SECRET_KEY, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET,
ANTHROPIC_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
OLLAMA_BASE_URL, ALLOWED_ORIGINS, ENVIRONMENT,
AI_PROVIDER_ORDER,          # e.g. '["ollama","claude","bedrock"]' (default)
REPO_CACHE_TTL_HOURS,       # default: 24
ENABLE_KNOWLEDGE_GRAPH,     # default: true
ENABLE_OPTIMIZATION_ENGINE, # default: true
ENABLE_EMBEDDINGS,          # default: true
ENABLE_CTO_AGENT,           # default: true
ENABLE_REPO_CACHE,          # default: true
ENABLE_COST_TRACKING        # default: true
```

**GitHub Actions CI** (Req 14.4):
```yaml
on: [push to main, pull_request]
jobs:
  lint:    ruff + mypy (backend), eslint + tsc (frontend)
  test:    pytest (backend unit + integration), vitest (frontend)
  build:   docker compose build --no-cache
```

**NGINX** terminates TLS, adds security headers (CSP, X-Content-Type-Options, X-Frame-Options,
HSTS) to all responses (Req 10.6), and reverse-proxies `/api/` and `/ws/` to the backend.

---

## Worker Specialization

Celery task routing is explicit — each task type is assigned to a dedicated queue and serviced
by a specialized worker with a matching Docker Compose service entry.

**Celery Queues and Specialized Workers:**

| Queue     | Worker             | Responsibility                                                          |
|-----------|--------------------|-------------------------------------------------------------------------|
| `clone`   | `CloneWorker`      | Repository cloning, workspace setup, limit enforcement                  |
| `parse`   | `ParseWorker`      | `SharedAnalysisContextBuilder` + `CrossReferenceIndex` build            |
| `ai`      | `AIWorker`         | All agent AI inference calls via `AIManager`                            |
| `kg`      | `KGWorker`         | Knowledge Graph node/edge extraction                                    |
| `embed`   | `EmbeddingWorker`  | Titan Embeddings via `BedrockEmbeddingProvider`                         |
| `report`  | `ReportWorker`     | All 5 report format generation                                          |
| `cleanup` | `CleanupWorker`    | Workspace deletion, report file retention enforcement                   |

Task routing is configured via Celery's `task_routes` dict in `celeryconfig.py`. In
`docker-compose.yml` each queue gets its own `celery_worker` service entry with
`--queues=<queue_name>`. In `docker-compose.override.yml` all queues can run on a single
worker for local development (e.g., `--queues=clone,parse,ai,kg,embed,report,cleanup`).

---

## Health and Observability

### Health Endpoints

```
GET /health     → {
                    "database": "connected",
                    "redis": "connected",
                    "celery": { "workers": 7, "queues": { "clone": 0, "parse": 0, "ai": 3, ... } },
                    "github_api": { "remaining": 4500, "reset_at": "2024-01-15T11:00:00Z" }
                  }

GET /ready      → HTTP 200 (DB connected + migrations applied) or HTTP 503

GET /live       → HTTP 200 (always, simple heartbeat)

GET /metrics    → Prometheus text format:
  repogenius_active_jobs
  repogenius_queue_depth{queue="clone"}
  repogenius_agent_duration_seconds{agent="security",quantile="0.95"}
  repogenius_ai_cost_usd_total{provider="ollama"}
  repogenius_cache_hit_ratio
  repogenius_analysis_duration_seconds
  repogenius_operation_duration_seconds{operation="clone"}
```

### Structured Log Format

Every log entry emitted by the platform follows this JSON schema:

```json
{
  "job_id": "uuid",
  "agent": "security",
  "request_id": "uuid",
  "trace_id": "uuid",
  "correlation_id": "uuid",
  "duration_ms": 1240,
  "provider": "ollama",
  "status": "success",
  "level": "INFO",
  "message": "Agent completed",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

A WARNING-level entry is emitted whenever any operation exceeds its documented p95 SLA target,
within the same request/task context (Req 30.2).

---

## Performance SLA Targets

| Operation                       | p95 SLA Target  |
|---------------------------------|-----------------|
| Repository clone                | ≤ 60 seconds    |
| `SharedAnalysisContext` build   | ≤ 60 seconds    |
| Individual agent execution      | ≤ 60 seconds    |
| Knowledge Graph generation      | ≤ 90 seconds    |
| All report formats generated    | ≤ 30 seconds    |
| Total end-to-end Analysis Job   | ≤ 10 minutes    |

These targets inform the per-agent timeout defaults in `ConfigRegistry.ai.default_timeout_seconds`
and the SLA warning threshold checked by the observability layer (Req 30.1, 30.2).

---

## Extensibility

The platform is designed as an extensible Developer Intelligence and Repository Optimization
Platform. The following capabilities are planned for **Version 2** and can be added via the
existing plugin architecture without breaking changes to the core Orchestrator or BaseAgent
contract:

- **Code Translation** — automated language-to-language repository migration engine (e.g., Python → TypeScript). Stub agent interface already defined in `AgentInputPayload`/`AgentOutputPayload`.
- **PR Review** — AI-powered pull request analysis and inline comment generation. Webhook endpoint scaffolding and RBAC permissions already accounted for in the extensibility design.
- **VS Code Extension API** — read-only agent result surfaces accessible from the editor.
- **GitHub App Webhook Integration** — trigger analysis jobs from push/PR events.
- **GitLab and Bitbucket Support** — alternative Git hosting providers via abstracted `GitProvider` interface.
- **MCP Server Interface** — expose analysis results as a Model Context Protocol server.
- **Plugin Marketplace** — community-contributed agent packages installable at runtime.

Each future capability drops in as a new `BaseAgent` subclass (for agents) or a new API router
(for endpoints), requiring no modifications to the Orchestrator, registry, or existing agents.

---

## Testing Strategy

**Dual testing approach** — unit/example tests cover specific scenarios and edge cases;
property-based tests validate universal invariants across wide input spaces.

### Unit and Example Tests

Focus areas:
- State transitions (job status: pending → cloned → running → completed/failed)
- OAuth flow completion with mocked GitHub API
- JWT issuance, expiry, and denylist invalidation
- Per-endpoint HTTP status codes for auth/authz failures
- Report generation for each of the five formats
- WebSocket terminal event and connection close
- Optimization Score formula with known inputs
- Engineering Maturity level mapping boundary values
- Cache hit flow: new job receives previous job's results without cloning
- Prompt registry: version increment on update, old version still retrievable
- Feature flag enforcement: each flag toggles the correct behavior

### Property-Based Tests

Use [Hypothesis](https://hypothesis.readthedocs.io/) (Python) and
[fast-check](https://fast-check.dev/) (TypeScript/Vitest) for property tests.

Minimum **100 iterations** per property test. Each test is tagged with its property number:

```python
# Example — Property 17: Letter Grade Boundary Mapping
from hypothesis import given, strategies as st
from app.services.scoring import to_letter_grade

@given(st.integers(min_value=0, max_value=100))
def test_property_17_letter_grade_mapping(score: int):
    """Feature: repogenius-ai, Property 17: Letter grade boundary mapping"""
    grade = to_letter_grade(score)
    if score >= 90:   assert grade == "A"
    elif score >= 80: assert grade == "B"
    elif score >= 70: assert grade == "C"
    elif score >= 60: assert grade == "D"
    else:             assert grade == "F"
```

### Integration Tests

Cover external-boundary behaviors that require infrastructure:
- AI provider fallback chain (Ollama → Claude → Bedrock) with mocked HTTP responses
- Celery worker beginning clone within 10 seconds of job creation
- Workspace cleanup within 1 hour of job completion
- Docker Compose startup within 3 minutes
- Security headers present on all NGINX responses
- EmbeddingWorker processes queue without blocking report generation
- Cache hit: new job returns completed status within 2 seconds without cloning
- GitHub rate limit: mocked 0-remaining header causes wait + successful retry
- Feature flag `ENABLE_KNOWLEDGE_GRAPH=false`: KG endpoints return HTTP 503

### Smoke Tests

Verify configuration and structural invariants at startup:
- All 13 SQLAlchemy entity classes exist and migrations are applied
- OpenAPI spec served at `/api/v1/docs`
- WebSocket endpoint accepts connections at `/ws/jobs/{job_id}`
- Titan Embeddings configured as the exclusive embedding provider
- No hardcoded secrets in source files or Docker images
- All 8 core agent modules and 17+ stub agent modules importable
- Prompt registry populated with at least one prompt per core agent


---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of
a system — essentially, a formal statement about what the system should do. Properties serve as
the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

---

### Property 1: Malformed URL Rejection

*For any* string that is not a structurally valid, reachable Git repository URL, submitting it to
the repository submission endpoint SHALL return HTTP 422, and no Analysis Job record SHALL exist
in the database for that input.

**Validates: Requirements 1.3**

---

### Property 2: Clone Failure Job Status

*For any* Analysis Job where cloning fails due to authentication failure, network timeout, or
repository not found, the job status SHALL be set to `failed`, an error message SHALL be persisted,
and a failure WebSocket event SHALL be emitted — no clone failure SHALL leave a job in a
non-terminal state without an error record.

**Validates: Requirements 1.4**

---

### Property 3: Full Agent Dispatch Coverage

*For any* Analysis Job that reaches `cloned` status, the set of agent names dispatched by the
Orchestrator SHALL equal the complete set of agent names registered in the plugin registry at
startup — no registered agent shall be silently skipped.

**Validates: Requirements 2.2, 15.2**

---

### Property 4: Agent Result Persistence Invariant

*For any* agent that completes execution (whether with status `success`, `error`, or `stub`),
an Agent Result record linked to the correct Analysis Job SHALL exist in the database with the
agent's name, status, and result payload.

**Validates: Requirements 2.3**

---

### Property 5: Agent Error Isolation

*For any* Analysis Job where a subset of agents raise unhandled exceptions, the Orchestrator
SHALL mark each failing agent's result as `error` and SHALL collect and persist results from all
remaining non-failing agents — the Analysis Job SHALL NOT be aborted due to individual agent
failures.

**Validates: Requirements 2.4**

---

### Property 6: WebSocket Event Field Completeness

*For any* agent result received by the Orchestrator, the emitted WebSocket progress event SHALL
contain all of: `job_id`, `status`, `progress_percentage` (integer in 0–100), `current_step`,
and `timestamp`.

**Validates: Requirements 2.7, 8.3**

---

### Property 7: Repository Understanding Agent Output Completeness

*For any* valid cloned repository passed to the Repository Understanding Agent, the returned
`AgentOutputPayload` SHALL contain non-null values for all of: language distribution, file count,
directory structure summary, commit history summary, contributor count, and primary framework
identification.

**Validates: Requirements 3.1**

---

### Property 8: Security Finding Field Completeness

*For any* security finding produced by the Security Agent, the finding SHALL have all of the
following fields populated with non-null values: `severity` (one of `critical`, `high`, `medium`,
`low`), `owasp_category`, `cwe_id`, `exploitability`, `fix_difficulty`, and
`estimated_fix_minutes` — no security finding SHALL be emitted missing any of these fields.

**Validates: Requirements 3.2**

---

### Property 9: Code Quality Agent Metric Completeness

*For any* repository analyzed by the Code Quality Agent, the output SHALL contain cyclomatic
complexity, code duplication percentage, comment coverage percentage, and naming convention
compliance scores at both per-file granularity and as aggregate values.

**Validates: Requirements 3.3**

---

### Property 10: Architecture Anti-Pattern Annotation Completeness

*For any* architectural anti-pattern flagged by the Architecture Agent, the anti-pattern record
SHALL include both a human-readable description and at least one file reference — no anti-pattern
SHALL be reported without both fields populated.

**Validates: Requirements 3.4**

---

### Property 11: Dependency Agent Output Coverage

*For any* repository analyzed by the Dependency Agent, the output SHALL include all four
categories: direct dependencies, transitive dependencies, outdated packages, and license
incompatibility findings — each as a separate list in the payload.

**Validates: Requirements 3.5**

---

### Property 12: Technical Debt Categorization and Ordering

*For any* Technical Debt Agent output, the debt estimate SHALL be categorized by type (code
smells, duplication, complexity, test coverage gaps), and the remediation list SHALL be ordered
by descending priority so that the first item is always the highest-priority action.

**Validates: Requirements 3.6**

---

### Property 13: Executive CTO Agent Output Completeness

*For any* valid set of Core Agent results passed to the Executive CTO Agent, the output SHALL
contain an `overall_risk_level` value, exactly three `strategic_recommendations`, and a
`production_readiness_assessment` — no Executive CTO output SHALL be missing any of these three
elements.

**Validates: Requirements 3.7**

---

### Property 14: Stub Agent Contract

*For any* stub agent class that inherits from `BaseAgent`, invoking `run(payload)` SHALL return a
well-formed `AgentOutputPayload` with `status = "stub"` and `findings = []`, without raising any
exception.

**Validates: Requirements 3.8**

---

### Property 15: Score Range Invariant

*For any* completed Analysis Job, every computed dimension score (Repository Health, Architecture,
Security, Performance, Testing, Documentation, Maintainability, Production Readiness, Technical
Debt) SHALL be either an integer in the closed range [0, 100] or `null` (when the required agent
returned `error`).

**Validates: Requirements 4.1**

---

### Property 16: Overall Grade Weighted Average Correctness

*For any* set of non-null dimension scores, the Overall Grade SHALL equal the weighted average
computed using the documented weight coefficients, rounded to the nearest integer. Null-score
dimensions SHALL be excluded and the remaining weights renormalized to sum to 1.0.

**Validates: Requirements 4.2**

---

### Property 17: Letter Grade Boundary Mapping

*For any* integer `n` in [0, 100], the letter grade mapping SHALL satisfy:
`n ∈ [90,100] → "A"`, `n ∈ [80,89] → "B"`, `n ∈ [70,79] → "C"`,
`n ∈ [60,69] → "D"`, `n ∈ [0,59] → "F"` — every integer in range has exactly one letter grade
and no boundary produces an incorrect result.

**Validates: Requirements 4.3**

---

### Property 18: Knowledge Graph Node Coverage

*For any* completed Analysis Job, every code entity identified during analysis (class, function,
module, package, external dependency) SHALL have a corresponding Knowledge Graph node record in
the database linked to that job.

**Validates: Requirements 5.1**

---

### Property 19: Knowledge Graph Edge Type Validity

*For any* Knowledge Graph edge generated by the platform, the `relationship` field SHALL be one
of the five defined types: `imports`, `inherits`, `calls`, `implements`, `depends_on` — no edge
SHALL be persisted with an undefined relationship type.

**Validates: Requirements 5.3**

---

### Property 20: Knowledge Graph Node Entity Type Validity

*For any* Knowledge Graph node persisted in the database, the `entity_type` field SHALL be one
of the fourteen defined types: `class`, `function`, `module`, `package`, `external_dep`,
`api_endpoint`, `environment_variable`, `docker_service`, `sql_table`, `http_endpoint`,
`celery_task`, `react_component`, `route`, or `hook` — no node SHALL be persisted with an
undefined entity type.

**Validates: Requirements 5.2**

---

### Property 21: All Five Report Formats Generated

*For any* completed Analysis Job, the platform SHALL generate and persist reports in all five
formats (HTML, PDF, Markdown, JSON, and Optimization Report) — no completed job SHALL result in
fewer than five report records.

**Validates: Requirements 6.1, 6.5**

---

### Property 22: HTML Report Content Completeness

*For any* HTML report generated from an Analysis Job, the report document SHALL contain all ten
dimension scores, all agent findings, all recommendations, and score trend chart data — no
required content section SHALL be absent from the rendered HTML.

**Validates: Requirements 6.2**

---

### Property 23: JSON Report Schema Conformance

*For any* JSON report generated by the platform, the document SHALL validate successfully against
the published OpenAPI schema for the `Report` entity — no generated JSON report SHALL contain
fields not in the schema or omit required fields.

**Validates: Requirements 6.4**

---

### Property 24: Original Repository Immutability

*For any* Analysis Job operation, the byte-level checksum (SHA-256) of every file in the original
cloned repository workspace SHALL be identical before and after the operation completes — no
analysis operation SHALL modify, rename, or delete any file in the original workspace.

**Validates: Requirements 10.2**

---

### Property 25: Rate Limit Enforcement

*For any* sequence of requests to any API endpoint that exceeds the per-IP (unauthenticated) or
per-user (authenticated) limit within a 60-second window, all requests beyond the limit SHALL
receive HTTP 429 — no request over the limit SHALL be processed successfully.

**Validates: Requirements 7.3**

---

### Property 26: Pagination Correctness

*For any* list endpoint, any valid `page` and `page_size` (≤ 100) combination SHALL return the
correct slice of items; a `page_size` greater than 100 SHALL be rejected with HTTP 422.

**Validates: Requirements 7.4**

---

### Property 27: Filter and Sort Correctness

*For any* list endpoint with a filter parameter applied, every item in the response SHALL satisfy
the filter predicate; for any sort parameter applied, items in the response SHALL appear in the
specified order.

**Validates: Requirements 7.5**

---

### Property 28: Schema Validation Error Structure

*For any* request body that fails schema validation, the HTTP 422 response SHALL include a
structured error body containing the `field` name and `violation_message` for every failing
field — no failing field SHALL be silently omitted from the error response.

**Validates: Requirements 7.6**

---

### Property 29: Unauthenticated and Unauthorized Request Rejection

*For any* protected endpoint, a request without a valid JWT or API Key SHALL receive HTTP 401;
a request with a valid credential that lacks the required RBAC role SHALL receive HTTP 403.

**Validates: Requirements 7.7, 7.8, 9.4**

---

### Property 30: WebSocket On-Connect Status Delivery

*For any* Analysis Job in any state, a client that establishes a WebSocket connection to
`/ws/jobs/{job_id}` SHALL immediately receive a message containing the current job `status` and
`progress_percentage` — no connection SHALL result in a silent initial state.

**Validates: Requirements 8.2**

---

### Property 31: Missed WebSocket Event Replay

*For any* WebSocket client that disconnects and reconnects to the same `job_id` within 60
seconds, the client SHALL receive all events emitted during the disconnection window in the order
they were originally emitted — no event from the disconnection window SHALL be missing on
reconnection.

**Validates: Requirements 8.5**

---

### Property 32: JWT Expiry Invariant

*For any* JWT issued by the platform, the token's `exp` claim SHALL be exactly 24 hours after
the issuance timestamp (`iat`) — no issued JWT SHALL have an expiry shorter or longer than 24
hours.

**Validates: Requirements 9.2**

---

### Property 33: API Key Storage Security

*For any* API Key created by the platform, the value stored in the `api_keys` table SHALL be a
bcrypt hash of the raw key — the plaintext key value SHALL NOT appear in any database column,
log line, or API response after the creation response.

**Validates: Requirements 9.3**

---

### Property 34: JWT Denylist Invalidation

*For any* JWT that has been added to the denylist via logout, every subsequent request to any
protected endpoint using that JWT SHALL receive HTTP 401 — no denylisted JWT SHALL grant access
to any endpoint before its original expiry time.

**Validates: Requirements 9.5**

---

### Property 35: Authentication Audit Log Completeness

*For any* authentication event (login, logout, token refresh, API key usage), an Audit Log
record SHALL be created containing the user ID, event timestamp, IP address, and outcome — no
authentication operation SHALL proceed without a corresponding audit entry.

**Validates: Requirements 9.6**

---

### Property 36: Credential Storage Security

*For any* user account with an OAuth token, the token value stored in the database SHALL be
AES-256 encrypted — no plaintext credential SHALL ever be persisted.

**Validates: Requirements 10.1**

---

### Property 37: Input Sanitization — No Shell Metacharacters

*For any* user-supplied repository URL, the sanitized value passed to GitPython SHALL not contain
shell metacharacters (`;`, `|`, `&`, `$`, `` ` ``, `(`, `)`, `>`, `<`, `\n`, `\r`) — the
sanitizer SHALL reject or strip all such characters before any external process invocation.

**Validates: Requirements 10.4**

---

### Property 38: Secret Redaction in Reports

*For any* report generated from a repository where the Security Agent detected one or more
secrets, every secret value SHALL be replaced with a redaction marker in the stored report — no
report document SHALL contain the literal secret string, only the file path and line number of
the detection.

**Validates: Requirements 10.7**

---

### Property 39: AI Provider Invocation Logging

*For any* AI provider invocation (Ollama, Claude, or Bedrock), a log record SHALL be created
containing provider name, model name, latency in milliseconds, input and output token counts, and
outcome (`success` or `failure`) — no invocation SHALL complete without a log entry.

**Validates: Requirements 11.6**

---

### Property 40: Plugin Registry Auto-Discovery

*For any* Python class placed in the `agents/` package directory that inherits from `BaseAgent`
and defines a non-empty `name` attribute, the plugin registry SHALL include that class in its
registered agent set after the next startup scan — no conforming class SHALL be silently skipped
by the discovery mechanism.

**Validates: Requirements 15.1, 15.2**

---

### Property 41: Optimization Score Formula Correctness

*For any* pair of non-negative integers `(critical_count, high_count)`, the Optimization Score
computed by the Repository Optimization Engine SHALL equal
`max(0, 100 − min(critical_count × 5, 50) − min(high_count × 2, 20))` — the score SHALL
never fall below 0 and SHALL never exceed 100.

**Validates: Requirements 16.5, 4.4**

---

### Property 42: Engineering Maturity Level Mapping

*For any* integer `n` in [0, 100], the Engineering Maturity level mapping SHALL satisfy:
`n ∈ [0, 24] → "Beginner"`, `n ∈ [25, 49] → "Intermediate"`, `n ∈ [50, 74] → "Advanced"`,
`n ∈ [75, 100] → "Enterprise"` — every integer in range has exactly one maturity level and no
boundary produces an incorrect result.

**Validates: Requirements 4.5**

---

### Property 43: Repository Optimization Agent Sequential Execution

*For any* Analysis Job, the Repository Optimization Agent's execution start time SHALL be greater
than or equal to the completion timestamp of every other Core Agent in the same job — the
Optimization Agent SHALL never begin before all Phase 1 agents have returned their results.

**Validates: Requirements 16.6, 2.9**

---

### Property 44: Quick Wins Filter Correctness

*For any* set of findings passed to the quick wins filter, every finding returned in the quick
wins list SHALL satisfy all three criteria: ROI ≥ 7, fix difficulty ≤ `easy` (i.e., `trivial`
or `easy`), and estimated resolution time ≤ 2 developer hours — no finding failing any of these
criteria SHALL appear in the quick wins output.

**Validates: Requirements 16.4**

---

### Property 45: Finding Deduplication Idempotency

*For any* set of findings, applying the deduplication operation twice SHALL produce the same
result as applying it once — the deduplicated set SHALL be stable under repeated application
(`deduplicate(deduplicate(S)) = deduplicate(S)`).

**Validates: Requirements 16.1**

---

### Property 46: AI Response Cache Hit

*For any* pair of identical AI invocations (same `agent_name` and `prompt`), the second
invocation SHALL return the cached response from the first invocation without calling the
underlying AI provider — the provider call count SHALL remain 1 regardless of how many times the
same inputs are submitted within the cache TTL window.

**Validates: Requirements 10.8**

---

### Property 47: Async Embedding Non-Blocking

*For any* Analysis Job where the EmbeddingWorker is artificially delayed or unavailable, the
report generation pipeline SHALL still complete successfully and return all five report formats —
report generation SHALL NOT be blocked by or dependent on the completion of embedding tasks.

**Validates: Requirements 5.4**

---

### Property 48: Workspace Path Isolation

*For any* two distinct Analysis Jobs with different `job_id` values, their workspace paths
(`workspace/{job_id_1}/` and `workspace/{job_id_2}/`) SHALL share no common files or directories
below the top-level `workspace/` directory — no file written or read for one job SHALL be
accessible via another job's workspace path.

**Validates: Requirements 1.2**

---

### Property 49: SharedAnalysisContext Completeness

*For any* valid cloned repository, the `SharedAnalysisContext` built before agent dispatch SHALL
contain non-null values for: `file_index`, `dependency_graph`, `symbol_table`, `git_metadata`,
`language_detection`, and `repo_metadata`; the `ast_cache` SHALL be non-empty for repositories
containing at least one supported-language file; `construction_time_ms` SHALL be a positive
integer recorded upon completion.

**Validates: Requirements 18.1, 18.4**

---

### Property 50: SharedAnalysisContext Parse-Error Isolation

*For any* source file that fails AST parsing due to a syntax error, the `SharedAnalysisContext`
SHALL include that file in the `file_index` with `parse_error: true` and SHALL NOT include it in
the `ast_cache`; all other files in the repository SHALL be unaffected and context construction
SHALL complete successfully regardless of per-file parse failures.

**Validates: Requirements 18.5**

---

### Property 51: GitHub Rate Limit Auto-Retry

*For any* GitHub API call that receives a `X-RateLimit-Remaining: 0` response, the
`RateLimitManager` SHALL wait until the `X-RateLimit-Reset` timestamp before retrying; the
caller SHALL not observe an error or receive a null response solely due to the rate limit — only
exhaustion after all retries SHALL surface an error to the caller.

**Validates: Requirements 19.2**

---

### Property 52: Repository Cache Hit Correctness

*For any* Analysis Job submission where a completed job for the same repository URL with a
matching `content_hash` exists within the cache TTL, the new job SHALL be marked
`cache_hit: true`, SHALL receive the previous job's agent results and scores, and SHALL reach
`completed` status within 2 seconds without cloning or dispatching any agents.

**Validates: Requirements 20.2, 20.4**

---

### Property 53: LLM Cost Record Completeness

*For any* AI provider invocation that returns a successful response (when
`ENABLE_COST_TRACKING=true`), an `AIInvocationLog` record SHALL be created containing all
required fields (`job_id`, `agent_name`, `provider_name`, `model_name`, `input_tokens`,
`output_tokens`, `latency_ms`, `cache_hit`, `prompt_id`, `prompt_version`, `created_at`) — no
successful invocation SHALL complete without a corresponding log entry.

**Validates: Requirements 21.1**

---

### Property 54: Prompt Version Immutability

*For any* prompt template registered in the Prompt Registry, updating the template SHALL create
a new version entry with an incremented `prompt_version`; the previous version SHALL remain
retrievable and executable via `PromptRegistry.get(prompt_id, version)`; no in-place
modification of existing prompt version entries SHALL occur.

**Validates: Requirements 22.4**

---

### Property 55: Repository Snapshot SHA Verification

*For any* Analysis Job where the local clone's HEAD commit SHA does not match the SHA returned
by the GitHub API at clone time, the job status SHALL be set to `failed` with reason
`snapshot_mismatch` and no agent execution SHALL proceed — the mismatch SHALL be detected and
recorded before the Orchestrator dispatches any agents.

**Validates: Requirements 23.2**

---

### Property 56: Agent DAG Topological Ordering

*For any* Analysis Job, no agent SHALL begin execution before all agents listed in its
`depends_on` attribute have returned a result (whether `success`, `error`, or `stub`); the
Orchestrator SHALL never dispatch an agent while any of its declared dependencies are still
running or pending — the DAG execution order SHALL be strictly consistent with a valid
topological sort of the dependency graph.

**Validates: Requirements 25.2, 25.3**

---

### Property 57: SharedAnalysisContext Immutability

*For any* Analysis Job, the `SharedAnalysisContext` injected into all agents SHALL be the same
object (same reference); no agent SHALL mutate the context — every agent in the same job reads
an identical, immutable context.

**Validates: Requirements 18.1, 18.2**

---

### Property 58: Agent DAG Topological Execution Order

*For any* two agents A and B in the same Analysis Job where B declares A in its `dependencies`,
B's execution start timestamp SHALL be strictly greater than A's completion timestamp — no
downstream agent SHALL begin while its declared predecessor is still running or pending.

**Validates: Requirements 2.2, 2.13**

---

### Property 59: EventBus Subscriber Exception Isolation

*For any* `EventBus.publish()` call, if one or more subscribers raise an exception, the
exception SHALL be caught and logged; the `publish()` call SHALL return normally and all
remaining subscribers SHALL still be invoked — subscriber failures SHALL never propagate to the
Orchestrator.

**Validates: Requirements 21.5**

---

### Property 60: ConfigRegistry Singleton Consistency

*For any* two components in the same process that read the same configuration key from
`ConfigRegistry`, both SHALL receive identical values — no component SHALL observe a different
value for the same key within a single process lifetime.

**Validates: Requirements 25.1, 25.2**

---

### Property 61: GitHub Rate Limit Pause

*For any* GitHub API call attempted when `RateLimitManager._remaining < 50`, no outbound HTTP
request to `api.github.com` SHALL be made until the `_reset_at` timestamp has passed — the
manager SHALL pause the caller until quota is available.

**Validates: Requirements 19.3**

---

### Property 62: Prompt Record Immutability

*For any* `prompt_registry` record that has been inserted, its `content` and `checksum` columns
SHALL never be updated in-place; any change to a prompt SHALL produce a new row with
`version + 1` while the original row remains unchanged and retrievable.

**Validates: Requirements 24.3**

---

### Property 63: AI Cost Log Completeness

*For any* AI provider invocation (cached or live), exactly one `ai_invocation_logs` record SHALL
be produced: cached invocations with `cached=true` and `estimated_cost_usd=0.0`; live
invocations with actual token counts and computed cost — no invocation SHALL complete without
a corresponding log entry.

**Validates: Requirements 23.1, 23.4**

---

### Property 64: Feature Flag KG Bypass

*For any* Analysis Job executed when `ENABLE_KG=false`, no `kg_nodes` or `kg_edges` records
SHALL be created in the database for that job — the Knowledge Graph generation step SHALL be
completely skipped with no partial writes.

**Validates: Requirements 22.2**

---

### Property 65: Job Status State Machine Completeness

*For any* transition attempted on an Analysis Job, the resulting status SHALL be a member of the
defined 12-state set (`pending`, `queued`, `cloning`, `cloned`, `running`, `completed`, `failed`,
`cancel_requested`, `cancelled`, `retrying`, `paused`, `cached`) and no transition SHALL leave
the job in an undefined state.

**Validates: Requirements 26.1**

---

### Property 66: Cancel Acknowledgement Timing

*For any* Analysis Job in `queued`, `cloning`, or `running` state that receives a cancel request,
the job status SHALL transition to `cancelled` within 30 seconds of the request being accepted —
no job SHALL remain indefinitely in `cancel_requested` state.

**Validates: Requirements 26.2**

---

### Property 67: Repository Cache Key Uniqueness

*For any* two Analysis Jobs with differing values of `repo_url`, `branch`, `commit_sha`,
`analysis_version`, or `prompt_versions_hash`, their cache keys SHALL be distinct — no cache hit
SHALL occur between jobs with any differing key component.

**Validates: Requirements 27.1, 27.3**

---

### Property 68: Repository Cache Hit Completeness

*For any* cache hit, the artifacts returned SHALL include all of: agent results, KG nodes/edges,
scores, and reports — no cache hit SHALL return a partial artifact set.

**Validates: Requirements 27.2**

---

### Property 69: Worker Queue Routing

*For any* Celery task submitted by the platform, the task SHALL be placed on its designated queue
and SHALL NOT appear on the default queue — every task type has an explicit `task_routes` entry.

**Validates: Requirements 28.2**

---

### Property 70: Health Endpoint Subsystem Coverage

*For any* call to `GET /health`, the response SHALL include a status field for every registered
subsystem (database, redis, celery, github_api) — no subsystem SHALL be silently omitted from
the health response.

**Validates: Requirements 29.1**

---

### Property 71: SLA Breach Warning Emission

*For any* operation that exceeds its documented p95 SLA target, a WARNING-level structured log
entry SHALL be emitted within the same request/task context — no SLA breach SHALL pass silently
without a corresponding log warning.

**Validates: Requirements 30.2**

---

### Property 72: CrossReferenceIndex Symbol Coverage

*For any* symbol in the repository that matches the covered types (functions, classes, methods,
constants, exported variables, HTTP routes, React components, React hooks, Celery tasks), the
`CrossReferenceIndex` SHALL contain an entry for that symbol — no covered symbol SHALL be absent
from the index.

**Validates: Requirements 32.1, 32.2**

---

### Property 73: CrossReferenceIndex Immutability

*For any* agent that reads the `CrossReferenceIndex` from its payload, the agent SHALL NOT mutate
the index — the index contents SHALL be identical before and after every agent's execution.

**Validates: Requirements 32.3**

---

### Property 74: KG Edge Population from CrossReferenceIndex

*For any* `calls`, `called_by`, `imports`, or `depends_on` edge in the Knowledge Graph, the edge
SHALL be sourced from the `CrossReferenceIndex` rather than from independent file re-parsing —
no KG edge SHALL contradict the `CrossReferenceIndex`.

**Validates: Requirements 32.4**

---

## Analysis Versioning

Every Analysis Job captures the exact engine state at dispatch time, enabling clean cache
invalidation and reproducible historical comparisons (Req 35.1–35.4).

```python
# Three new columns on analysis_jobs:
analysis_version:     str   # e.g. "1.0.0" — platform release tag
agent_bundle_version: str   # SHA-256 of sorted agent name+version pairs at dispatch time
schema_version:       str   # Alembic migration head revision at job creation time

# Populated in AnalysisJobService.create_job():
analysis_version     = config.get("ANALYSIS_VERSION", "1.0.0")
agent_bundle_version = compute_bundle_version(registry.get_all())  # sorted hash
schema_version       = alembic_context.get_current_head()
```

Cache invalidation uses all three: if `analysis_version` or `agent_bundle_version` differs
between a candidate cached job and the current runtime, the cache entry is stale (Req 35.3).
Both fields are returned in `GET /api/v1/jobs/{job_id}` (Req 35.4).

---

## Agent Version Tracking

Every `AgentResult` record captures the agent and prompt versions that produced it,
enabling full reproducibility when agent logic or prompts change (Req 36.1–36.3).

New columns on `agent_results`:

| Column           | Type   | Source                                          |
|-----------------|--------|-------------------------------------------------|
| `agent_version`  | str    | `agent.version` class attribute                 |
| `prompt_name`    | str    | Active prompt name from PromptRegistry          |
| `prompt_version` | int    | Active prompt version from PromptRegistry       |
| `model`          | str    | Model name from last AIManager invocation       |
| `provider`       | str    | Provider name from last AIManager invocation    |

Populated by the Orchestrator immediately after `safe_run()` returns, before persisting the
result record (Req 36.2). All five fields are included in the `GET /api/v1/jobs/{job_id}/results`
response (Req 36.3).

---

## Partial Completion State

The job status `completed_with_warnings` is set when the Orchestrator finishes all dispatches
but one or more Core Agents returned `status: "error"` (Req 37.1–37.4).

```python
# orchestrator.py — final status decision
core_errors = [r for r in results.values()
               if r.status == "error" and r.agent in CORE_AGENT_NAMES]
if core_errors:
    job.status = "completed_with_warnings"
    job.agent_errors = [r.agent for r in core_errors]   # JSON array column
else:
    job.status = "completed"
event_bus.publish(JobCompletedEvent(job_id=job.id, status=job.status))
```

**Updated status state machine (13 states):**
`pending` → `queued` → `cloning` → `cloned` → `running` →
`completed` | `completed_with_warnings` | `failed` | `cancelled` | `cached` | `retrying` | `paused`

The Frontend displays a warning badge on `completed_with_warnings` jobs and the Report page
shows a banner listing failed agents and null score dimensions (Req 37.3).

---

## API Version Metadata Endpoint

```
GET /api/v1/system/version   (no authentication required)

Response 200:
{
  "api_version":              "1.0.0",
  "analysis_engine_version":  "1.0.0",
  "schema_version":           "abc123def456",   // Alembic head revision
  "frontend_version":         "1.0.0",
  "git_commit_sha":           "d4e5f6a..."       // injected at build time
}
```

`git_commit_sha` is injected via the `GIT_COMMIT_SHA` Docker build argument and defaults to
`"unknown"` if not set (Req 38.2). No auth required — usable in unauthenticated deployment
scripts (Req 38.3).

---

## Error Taxonomy

Every HTTP error response includes a top-level `error_code` field alongside `detail` (Req 39.1).
The full taxonomy is published in the OpenAPI specification (Req 39.2):

| `error_code`           | HTTP Status | Trigger                                                  |
|------------------------|-------------|----------------------------------------------------------|
| `INVALID_URL`          | 422         | URL fails allowlist or format validation                 |
| `REPO_NOT_FOUND`       | 422         | Repository URL inaccessible or returns 404               |
| `REPO_TOO_LARGE`       | 422         | Exceeds 2 GB or any secondary cloning limit              |
| `CLONE_TIMEOUT`        | job-level   | GitPython clone exceeded configured timeout              |
| `GITHUB_RATE_LIMIT`    | 429         | GitHub API quota exhausted before metadata fetch         |
| `AI_PROVIDER_TIMEOUT`  | agent-level | All configured providers timed out for one agent         |
| `PARSER_FAILURE`       | job-level   | `SharedAnalysisContext` build returned `None`            |
| `REPORT_FAILED`        | job-level   | Report generation failed for one or more formats         |
| `CACHE_MISS`           | informational | No cache entry found; full analysis will run           |
| `CACHE_CORRUPT`        | 500         | Cache entry found but artifact integrity check failed    |
| `AGENT_TIMEOUT`        | agent-level | Individual agent exceeded its per-agent timeout          |
| `DAG_CYCLE`            | 500/startup | Circular dependency detected in agent DAG                |

Error responses follow this envelope:
```json
{
  "error_code": "REPO_TOO_LARGE",
  "detail": "Repository size 3.2 GB exceeds the 2 GB limit.",
  "status": 422
}
```

`error_code` is `null` on all 2xx responses (Req 39.3).

---

## Data Retention Configuration

All retention TTLs are configurable via `ConfigRegistry` and enforced idempotently by
`CleanupWorker` on every scheduled run (Req 40.1–40.3).

```python
# infrastructure/config/config_registry.py — RetentionSettings
class RetentionSettings(BaseModel):
    workspace_hours: int = 1           # RETENTION_WORKSPACE_HOURS
    logs_days: int = 90                # RETENTION_LOGS_DAYS
    job_metrics_days: int = 365        # RETENTION_JOB_METRICS_DAYS
    ai_invocation_logs_days: int = 90  # RETENTION_AI_INVOCATION_LOGS_DAYS
    cache_hours: int = 24              # RETENTION_CACHE_HOURS (same as REPO_CACHE_TTL_HOURS)
    kg_embeddings_days: int = 30       # RETENTION_KG_EMBEDDINGS_DAYS (days after job expiry)
    reports_days: int = 30             # RETENTION_REPORTS_DAYS
```

`CleanupWorker` enforcement logic per resource:

| Resource               | Action on expiry                                          | Audit event       |
|------------------------|-----------------------------------------------------------|-------------------|
| Workspace directory    | `shutil.rmtree(workspace/{job_id}/)` — idempotent        | `workspace_deleted` |
| Log files              | Delete files in `workspace/{job_id}/logs/`               | `logs_deleted`    |
| `job_metrics` rows     | `DELETE WHERE created_at < now() - interval`             | `metrics_purged`  |
| `ai_invocation_logs`   | `DELETE WHERE created_at < now() - interval`             | `invocations_purged` |
| `repository_caches`    | Delete row + `clone_path` on disk                        | `cache_evicted`   |
| `kg_nodes.embedding`   | `UPDATE SET embedding = NULL WHERE job.completed_at < threshold` | `embeddings_nulled` |
| Report files           | Delete from storage; `UPDATE reports SET storage_path = NULL` | `reports_expired` |

Every deletion writes an `audit_logs` entry with `event_type = <action>`, `user_id = NULL`
(system-initiated), and `reason = "retention_policy"` (Req 40.3).

---

## Correctness Properties (continued)

---

### Property 75: Analysis Version Fields Populated

*For any* Analysis Job created after platform startup, the `analysis_version`,
`agent_bundle_version`, and `schema_version` fields SHALL be non-null and SHALL match the
values returned by `ConfigRegistry` and `AlembicContext.get_current_head()` at the time of
job creation — no job SHALL be persisted with any of these three fields null or empty.

**Validates: Requirements 35.1, 35.2**

---

### Property 76: Cache Invalidation on Version Change

*For any* two Analysis Jobs for the same repository where `analysis_version` or
`agent_bundle_version` differs between them, the newer job SHALL NOT be considered a cache
hit against the older job — stale version entries SHALL never be reused.

**Validates: Requirements 35.3**

---

### Property 77: Agent Result Version Fields Completeness

*For any* Agent Result record persisted in the database, all five version fields
(`agent_version`, `prompt_name`, `prompt_version`, `model`, `provider`) SHALL be non-null —
no agent result SHALL be written without all five fields populated.

**Validates: Requirements 36.1, 36.2**

---

### Property 78: Partial Completion State Correctness

*For any* Analysis Job where at least one Core Agent returned `status = "error"` and all
dispatched agents have completed, the job status SHALL be set to `completed_with_warnings`
rather than `completed`, and the `agent_errors` list SHALL contain the names of all Core
Agents whose result status was `error` — no partially-failed job SHALL show status `completed`.

**Validates: Requirements 37.1, 37.2**

---

### Property 79: Version Endpoint Unauthenticated Availability

*For any* request to `GET /api/v1/system/version` without an `Authorization` header,
the response SHALL be HTTP 200 with all five version fields present — the endpoint SHALL
never return 401 or 403 regardless of authentication state.

**Validates: Requirements 38.1, 38.3**

---

### Property 80: Error Code Presence on Error Responses

*For any* HTTP 4xx or 5xx response from the Backend, the response body SHALL contain a
top-level `error_code` field with a non-null value from the defined taxonomy — no error
response SHALL omit the `error_code` field or set it to a value outside the defined set.

**Validates: Requirements 39.1, 39.2**

---

### Property 81: Error Code Null on Success Responses

*For any* HTTP 2xx response from the Backend, the response body SHALL either omit the
`error_code` field entirely or set it to `null` — no successful response SHALL include a
non-null `error_code`.

**Validates: Requirements 39.3**

---

### Property 82: Retention Policy Idempotency

*For any* `CleanupWorker` run that attempts to delete a resource that was already deleted by
a prior run, the task SHALL log a debug message and continue without raising an exception —
repeated cleanup runs on the same resource SHALL produce identical state (resource absent).

**Validates: Requirements 40.2**

---

### Property 83: Retention Policy Audit Log Completeness

*For any* resource deleted by `CleanupWorker` under a retention policy, an `audit_logs`
record SHALL be created with `event_type` matching the deletion action, `user_id = null`,
and `reason = "retention_policy"` — no retention-policy deletion SHALL occur without a
corresponding audit entry.

**Validates: Requirements 40.3**

---

### Property 84: Agent Bundle Version Determinism

*For any* two identical sets of registered agents (same agent names and versions), the
computed `agent_bundle_version` hash SHALL be identical — the hash function SHALL be
deterministic and order-independent so that agent registration order does not affect the
bundle version.

**Validates: Requirements 35.1**

---

### Property 85: Completed-With-Warnings Dashboard Visibility

*For any* Analysis Job with status `completed_with_warnings`, the Frontend Dashboard and
Repository Analysis page SHALL display a visible warning indicator and the `agent_errors`
list SHALL be accessible to the user — no `completed_with_warnings` job SHALL appear
identical to a `completed` job in the UI.

**Validates: Requirements 37.3**

---

> **Specification Frozen.** This document covers 40 requirements and 85 correctness
> properties. No further scope additions should be made. Proceed to implementation.
