# Implementation Plan: RepoGenius AI — Developer Intelligence and Repository Optimization Platform

## Overview

Full-stack SaaS platform built with FastAPI (Python), React/TypeScript, PostgreSQL, Redis, Celery,
and a hybrid AI backend (configurable provider order). The implementation follows Clean Architecture
(Presentation → Application → Domain → Infrastructure) with a DAG-based multi-agent Orchestrator,
shared repository parsing context, in-process EventBus, GitHubService rate limiting, versioned
Prompt Registry, LLM cost tracking, Feature Flags, and a Central ConfigRegistry.

> **Version 2 Note:** Code Translation and PR Review are out of scope for V1 MVP.

The spec covers **34 requirements** and **74 correctness properties**.

---

## Tasks

- [ ] 1. Infrastructure and DevOps Setup
  - [ ] 1.1 Create Docker Compose services and NGINX configuration
    - Write `docker-compose.yml` defining services: `backend`, `frontend`, `postgres` (v15),
      `redis` (v7), `celery_worker`, `celery_beat`, `nginx`
    - Write `docker-compose.override.yml` for local dev with volume mounts and hot-reload
    - Write `nginx/nginx.conf` with TLS termination, security headers (CSP, HSTS,
      X-Content-Type-Options, X-Frame-Options), reverse-proxy for `/api/` and `/ws/`
    - _Requirements: 14.1, 14.2, 14.5, 10.6_
  - [ ] 1.2 Create environment variable template and GitHub Actions CI
    - Create `.env.example` with ALL required env vars: `DATABASE_URL`, `REDIS_URL`,
      `SECRET_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `ANTHROPIC_API_KEY`,
      `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `OLLAMA_BASE_URL`,
      `ALLOWED_ORIGINS`, `ENVIRONMENT`, `AI_PROVIDER_ORDER`, `REPO_CACHE_TTL_HOURS`,
      `ENABLE_KG`, `ENABLE_OPTIMIZATION`, `ENABLE_REPORTS`, `ENABLE_EMBEDDINGS`,
      `ENABLE_EXECUTIVE_CTO`, `ENABLE_GITHUB_METADATA`
    - Write `.github/workflows/ci.yml` triggering on push to main and all pull requests;
      lint job (ruff + mypy; eslint + tsc), test job (pytest + vitest), build job
    - _Requirements: 14.4, 14.6, 22.1_


- [ ] 2. Backend Scaffolding — Clean Architecture
  - [ ] 2.1 Scaffold 4-layer directory structure and app factory
    - Create all directories: `presentation/api/v1/`, `presentation/websocket/`,
      `application/services/`, `application/`, `domain/entities/`, `domain/value_objects/`,
      `domain/events/`, `domain/repositories/`, `infrastructure/db/models/`,
      `infrastructure/repositories/`, `infrastructure/ai/`, `infrastructure/github/`,
      `infrastructure/config/`, `infrastructure/workers/`, `agents/core/`, `agents/stubs/`
    - Write `app/main.py` app factory with FastAPI lifespan hooks: ConfigRegistry validation,
      DB connectivity check, Alembic migration check, AgentRegistry.discover(), EventBus
      subscriber registration — exit non-zero on any startup failure
    - _Requirements: 20.1, 20.2, 20.3, 13.4, 25.3_
  - [ ] 2.2 Implement ConfigRegistry singleton
    - Write `infrastructure/config/config_registry.py` with `AISettings` (provider_order,
      default_timeout_seconds, per_agent_timeouts dict, cache_ttl_hours), `FeatureFlagSettings`
      (all 6 feature flags with defaults), and `ConfigRegistry(BaseSettings)` with typed
      accessors for all config groups and `get_agent_timeout(agent_name: str) -> int` method
    - Validate full registry at startup; exit non-zero with descriptive error on missing values
    - `config = ConfigRegistry()` singleton; ALL other code imports this — never reads env vars directly
    - _Requirements: 25.1, 25.2, 25.3, 25.4_
  - [ ] 2.3 Implement EventBus with domain events
    - Write `application/event_bus.py` with `DomainEvent` base dataclass, `AgentCompletedEvent`
      (job_id, agent_name, status, duration_ms, finding_count), `JobCompletedEvent` (job_id),
      `JobFailedEvent` (job_id, reason), and `EventBus` class with `publish()` and `subscribe()`
    - Subscriber exceptions MUST be caught, logged, and NOT re-raised — never propagate to caller
    - Register all subscribers at startup in `main.py` lifespan
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_
  - [ ] 2.4 Implement UnitOfWork and domain repository interfaces
    - Write `application/unit_of_work.py`: async context manager that groups repository writes
      into a single atomic SQLAlchemy transaction
    - Write abstract repository ABCs in `domain/repositories/`: `AnalysisJobRepository`,
      `UserRepository`, `RecommendationRepository`, `AgentResultRepository`,
      `ReportRepository`, `KGNodeRepository`, `KGEdgeRepository`
    - Write concrete SQLAlchemy implementations in `infrastructure/repositories/`
    - Service classes MUST import only domain interfaces, never SQLAlchemy session directly
    - _Requirements: 20.4, 20.5_
  - [ ]* 2.5 Write property tests for ConfigRegistry and EventBus
    - **Property 59: EventBus Subscriber Exception Isolation** — subscriber exception caught;
      publish() returns normally; remaining subscribers still invoked
    - **Property 60: ConfigRegistry Singleton Consistency** — all components read identical values
    - **Validates: Requirements 21.5, 25.1**


- [ ] 3. Database Models and Alembic Migrations (15 Entities)
  - [ ] 3.1 Implement all 15 SQLAlchemy ORM models
    - `users`: id (UUID), github_id, email, password_hash, oauth_token_enc (AES-256), role, created_at
    - `organizations`: id, name, owner_id (FK → users)
    - `repositories`: id, url, owner_id, org_id (nullable), last_analyzed_at
    - `analysis_jobs`: id, repo_id, status, progress_pct, optimization_score (int nullable),
      engineering_maturity_score (int nullable), content_hash, cache_hit, commit_sha,
      branch_name, total_input_tokens, total_output_tokens, total_estimated_cost_usd,
      cache_hit_count, created_at, completed_at
    - `repository_snapshots`: id, job_id (FK), commit_sha, branch, repository_url,
      clone_timestamp, default_branch
    - `agent_results`: id, job_id, agent_name, status, payload_json, created_at
    - `reports`: id, job_id, format, storage_path, created_at, expires_at
    - `recommendations`: id, job_id, title, description, severity, difficulty,
      estimated_hours (float), impact, roi (float 0–10), category, affected_files (JSON),
      related_agent, confidence (float 0–1), references (JSON), suggested_sprint (int nullable),
      priority, created_at
    - `kg_nodes`: id, job_id, entity_type (14-type Literal), name, file_path, description,
      embedding (pgvector nullable), metadata (JSON)
    - `kg_edges`: id, source_id, target_id, relationship (5-type Literal)
    - `audit_logs`: id, user_id, event_type, ip_address, outcome, user_agent, request_id,
      endpoint, latency_ms, session_id, created_at
    - `notifications`: id, user_id, job_id, type, message, read, created_at
    - `api_keys`: id, user_id, key_hash (bcrypt), name, last_used_at, created_at
    - `ai_invocation_logs`: id, job_id, agent_name, provider, model, prompt_name,
      prompt_version (int), input_tokens, output_tokens, latency_ms,
      estimated_cost_usd (float), cached (bool), created_at
    - `prompt_registry`: id, prompt_name, version (int), content, checksum (SHA-256),
      author, created_at, is_active (bool)
    - _Requirements: 13.1, 23.1, 24.1_
  - [ ] 3.2 Add FK constraints, indexes, and generate Alembic migration
    - Add FK constraints on all inter-entity relationships
    - Add indexes on all FK columns, `status`, `created_at`, `user_id`, `job_id`, `repo_id`,
      `prompt_name + is_active` (partial), `provider + created_at` (for cost-report queries)
    - Initialize Alembic; configure async engine in `env.py`; generate initial migration
    - _Requirements: 13.2, 13.3_
  - [ ]* 3.3 Write smoke tests for all 15 entity classes and migrations
    - Assert all 15 SQLAlchemy models importable; Alembic `current` == `head` in test DB
    - Assert `prompt_registry` and `ai_invocation_logs` tables exist with correct columns
    - _Requirements: 13.1, 13.2_


- [ ] 4. Authentication, Authorization, and Security Core
  - [ ] 4.1 Implement GitHub OAuth 2.0 flow (sole authentication method)
    - Write `presentation/api/v1/auth.py` with `GET /auth/github` and `GET /auth/github/callback`
    - On callback: upsert User record, AES-256 encrypt OAuth token, issue JWT, record audit log
    - DO NOT implement username/password login — GitHub OAuth and API Key are the ONLY methods
    - _Requirements: 9.1, 9.6, 10.1_
  - [ ] 4.2 Implement JWT issuance, validation, and Redis denylist
    - `create_access_token()` → JWT with `{sub, roles, exp: now+24h, jti: uuid}`
    - `decode_access_token()` → validate signature, expiry, and Redis denylist
    - `POST /auth/logout` → add `jti` to `jwt:denylist:{jti}` with TTL = remaining seconds
    - _Requirements: 9.2, 9.5, 9.7_
  - [ ] 4.3 Implement API Key creation and bcrypt storage
    - `POST /api/v1/users/api-keys` → generate key, store `bcrypt(key, cost=12)`, return raw once
    - API Key dependency: hash incoming key, lookup in `api_keys` table, update `last_used_at`
    - _Requirements: 9.3_
  - [ ] 4.4 Implement RBAC and rate limiter
    - `require_role(roles)` FastAPI dependency → HTTP 403 when insufficient
    - Redis sliding-window rate limiter: 10 req/min unauthenticated per IP,
      120 req/min authenticated per user → HTTP 429 on breach
    - _Requirements: 9.4, 7.3, 7.7, 7.8_
  - [ ] 4.5 Implement URL sanitization and allowlist validation
    - Validate repo URLs against allowlist: `github.com`, `gitlab.com`, `bitbucket.org`
    - Reject `file://`, `ssh://`, local paths, shell metacharacters before GitPython
    - Return HTTP 422 with field-level error; no DB record created on invalid URL
    - _Requirements: 1.3, 1.7, 10.4, 10.5_
  - [ ]* 4.6 Write property tests for auth and security
    - **Property 29: Unauthenticated/Unauthorized Rejection** — no cred → 401; wrong role → 403
    - **Property 32: JWT Expiry Invariant** — every issued JWT has `exp - iat == 24h`
    - **Property 33: API Key Storage Security** — stored value is bcrypt hash, never plaintext
    - **Property 34: JWT Denylist Invalidation** — denylisted JWT always returns 401
    - **Property 35: Auth Audit Log Completeness** — every auth event has complete audit record
    - **Property 36: Credential Storage Security** — OAuth tokens stored AES-256 encrypted
    - **Property 37: Input Sanitization** — sanitized URL never contains shell metacharacters
    - **Validates: Requirements 9.1–9.7, 10.1, 10.4**

- [ ] 5. Checkpoint — Auth and DB Foundation
  - Ensure all tests pass. Verify: GitHub OAuth issues JWT; API Key auth works; RBAC enforces
    401/403; all 15 DB models migrate; rate limiter returns 429; URL validator rejects bad inputs.


- [ ] 6. GitHubService and Rate Limit Management
  - [ ] 6.1 Implement RateLimitManager
    - Write `infrastructure/github/rate_limit_manager.py`
    - Track `_remaining` and `_reset_at` from GitHub response headers
    - `update_from_headers(headers)` — parse `X-RateLimit-Remaining` and `X-RateLimit-Reset`
    - `wait_if_exhausted()` — if `_remaining < 50`, await until `_reset_at + 1s`
    - _Requirements: 19.2, 19.3_
  - [ ] 6.2 Implement GitHubService
    - Write `infrastructure/github/github_service.py` using `httpx.AsyncClient`
    - ETag cache (`self._etags` dict): send `If-None-Match` header; return `None` on 304
    - Exponential backoff with jitter on HTTP 429 and 403: `sleep(2^attempt + random(0,1))`
    - After 3 retries, return `None` (field marked unavailable — not a job failure)
    - ALL GitHub API calls platform-wide route through this service — no direct `api.github.com` calls
    - Methods: `get(path)`, `get_repository_metadata(url)`, `get_latest_commit_sha(url)`,
      `get_branch_protection(owner, repo)`
    - _Requirements: 19.1, 19.4, 19.5, 19.6_
  - [ ]* 6.3 Write property tests for GitHub rate limiting
    - **Property 61: GitHub Rate Limit Pause** — when `_remaining < 50`, no HTTP call made until reset
    - **Property 51: GitHub Rate Limit Auto-Retry** — 429 response triggers backoff + successful retry
    - **Validates: Requirements 19.3, 19.5**

- [ ] 7. SharedAnalysisContext — Repository Parser Layer
  - [ ] 7.1 Implement SharedAnalysisContextBuilder
    - Write `agents/shared_context.py` with `SharedAnalysisContext` dataclass and builder
    - Builder parses repository ONCE: Language Map (language → file paths), File Index
      (path → FileMetadata with language, size, parse_error), AST Cache (path → AST or None),
      Symbol Table (qualified_name → SymbolInfo), Dependency Graph (module → imports),
      Git Metadata (commit_sha, branch, tags, contributors), Framework Detection
    - Support 12 languages: Python, JavaScript, TypeScript, Java, Go, Rust, C#, C++, PHP,
      Ruby, Kotlin, Swift; unsupported files included in file index with `language="unsupported"`
    - Per-file AST parse failure → set `file.parse_error=True`, skip from AST cache, continue
    - Full build must complete within 60 seconds; if it fails, return `None` (Orchestrator aborts job)
    - _Requirements: 18.1, 18.4, 18.5, 18.6_
  - [ ]* 7.2 Write property tests for SharedAnalysisContext
    - **Property 49: SharedAnalysisContext Completeness** — built context has all required fields
    - **Property 50: Parse-Error Isolation** — per-file syntax errors don't abort context build
    - **Property 57: SharedAnalysisContext Immutability** — all agents receive same reference; no mutation
    - **Validates: Requirements 18.1, 18.4–18.6**


- [ ] 8. Agent System Foundation
  - [ ] 8.1 Implement BaseAgent with dependencies declaration
    - Write `agents/base.py`: abstract `BaseAgent` with `name: str`, `version: str = "1.0.0"`,
      `dependencies: list[str] = []`, abstract `async run(payload) -> AgentOutputPayload`,
      default `async pre_run`, `async post_run`, `async on_error` lifecycle hooks
    - _Requirements: 2.5, 2.6, 2.11_
  - [ ] 8.2 Implement enriched AgentInputPayload and AgentFinding schemas
    - Write `agents/payloads.py`:
      - `AgentInputPayload`: job_id, repo_path, repo_url, metadata (includes
        `"analysis_context": SharedAnalysisContext` and `"prior_results": dict[str, AgentOutputPayload]`)
      - `AgentFinding`: severity, description, file_path, line_number, category,
        `owasp_category`, `cwe_id`, `exploitability`, `fix_difficulty`, `estimated_fix_minutes`
      - `AgentOutputPayload`: agent, status (success/error/stub), findings, metrics, summary,
        error_message, stack_trace
    - _Requirements: 2.3, 3.2, 15.3_
  - [ ] 8.3 Implement AgentRegistry with full discovery and lookup
    - Write `agents/registry.py` using `pkgutil.walk_packages` + `inspect.getmembers`
    - Methods: `discover(package)`, `get_all() -> list[BaseAgent]`, `get_agent(name) -> BaseAgent`
    - Module-level `registry` singleton; `discover()` called in `main.py` lifespan startup
    - _Requirements: 15.1, 15.2_
  - [ ] 8.4 Implement DAG-based Orchestrator
    - Write `agents/orchestrator.py` with:
      - `build_dag(agents)` — merges `DEFAULT_DAG` with `agent.dependencies` declarations
      - `validate_dag(dag)` — Kahn's algorithm cycle detection; exit non-zero on cycle (Req 2.12)
      - `run_analysis(job)`:
        1. Build `SharedAnalysisContext` via `SharedAnalysisContextBuilder`; abort if None
        2. Execute topological wave dispatch: ready agents (no unresolved deps) run concurrently
           bounded by `asyncio.Semaphore(config.get_concurrency())` with per-agent
           `asyncio.wait_for(timeout=config.get_agent_timeout(agent.name))`
        3. After each agent completes: persist result (Req 2.3); publish `AgentCompletedEvent`
        4. After all agents: publish `JobCompletedEvent` (triggers report generation via EventBus)
      - Inject `SharedAnalysisContext` + `prior_results` into each agent's payload metadata
      - `safe_run()` catches all exceptions → `AgentOutputPayload(status="error")` + log stack trace
    - _Requirements: 2.1, 2.2, 2.4, 2.7–2.13, 18.2, 18.3, 21.2, 21.3_
  - [ ]* 8.5 Write property tests for agent system
    - **Property 3: Full Agent Dispatch Coverage** — dispatched agent names = all registry names
    - **Property 4: Agent Result Persistence Invariant** — every completion creates DB record
    - **Property 5: Agent Error Isolation** — exceptions in some agents don't abort others
    - **Property 6: WebSocket Event Field Completeness** — every WS event has all 5 required fields
    - **Property 40: Plugin Registry Auto-Discovery** — conforming BaseAgent subclass auto-registered
    - **Property 56: Agent DAG Topological Ordering** — no agent starts before all its deps complete
    - **Property 58: DAG Topological Execution Order** — B's start > A's completion when B deps on A
    - **Validates: Requirements 2.2–2.13, 15.1–15.2**


- [ ] 9. AIManager, Prompt Registry, and Cost Tracking
  - [ ] 9.1 Implement provider classes and ProviderRouter
    - Write `OllamaProvider`, `ClaudeProvider`, `BedrockProvider` each implementing
      `async invoke(prompt, **kwargs) -> AIResponse` with 30s timeout
    - Write `ProviderRouter.invoke_with_fallback(prompt, provider_order)` — iterates providers
      in config order; `AllProvidersFailedError` if all fail; provider order from `ConfigRegistry`
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  - [ ] 9.2 Implement ResponseCache (Redis-backed)
    - Cache key: `{agent_name}:{hash(prompt)}`; configurable TTL from `ConfigRegistry`
    - Cache hit: return cached response, log with `cached=True`, skip provider invocation
    - _Requirements: 10.8_
  - [ ] 9.3 Implement ResponseParser with Pydantic validation and repair loop
    - `validate(response, expected_schema: type[BaseModel])` → Pydantic validation
    - On `ValidationError`: one repair attempt with correction instruction appended to prompt
    - If repair also fails: return `AIResponse(status="error")` — never persist malformed output
    - _Requirements: 11.8, 11.9_
  - [ ] 9.4 Implement InvocationLogger writing to ai_invocation_logs
    - Log every invocation: provider, model, prompt_name, prompt_version, input_tokens,
      output_tokens, latency_ms, estimated_cost_usd (from ConfigRegistry pricing constants),
      cached (bool); `estimated_cost_usd = 0.0` on cache hits
    - _Requirements: 11.6, 23.1, 23.2, 23.4_
  - [ ] 9.5 Implement PromptRegistry with versioning
    - Write `infrastructure/ai/prompt_registry.py`
    - `get_active(prompt_name)` → returns record with `is_active=True`
    - `register(prompt_name, content, author)` → deactivates previous; inserts new with
      `version+1`, `is_active=True`, `checksum=SHA-256(content)`
    - Existing records are NEVER modified — immutable once inserted
    - _Requirements: 24.1, 24.2, 24.3_
  - [ ] 9.6 Assemble AIManager and PromptBuilder
    - `AIManager.invoke(agent_name, prompt, expected_schema)` calls: cache check → provider →
      validation → repair if needed → cache write → log
    - `PromptBuilder.build(agent_name, ctx)` calls `PromptRegistry.get_active(f"agent.{agent_name}")`
      and formats with context; `prompt_name` + `prompt_version` stored in every invocation log
    - _Requirements: 11.5, 24.4_
  - [ ] 9.7 Implement BedrockEmbeddingProvider
    - Dedicated class for Titan Embeddings via AWS Bedrock — bypasses AIManager fallback chain
    - Used exclusively by EmbeddingWorker
    - _Requirements: 11.7_
  - [ ]* 9.8 Write property tests for AI layer
    - **Property 39: AI Provider Invocation Logging** — every invocation produces a log record
    - **Property 46: AI Response Cache Hit** — identical inputs return cached; provider count = 1
    - **Property 54: Prompt Version Immutability** — update creates new version; old retrievable
    - **Property 62: Prompt Record Immutability** — content/checksum never updated in-place
    - **Property 63: AI Cost Log Completeness** — cached and live invocations both produce records
    - **Validates: Requirements 10.8, 11.6, 23.1, 24.3–24.4**

- [ ] 10. Checkpoint — Core Infrastructure Complete
  - Ensure all tests pass. Verify: ConfigRegistry validates on startup; EventBus subscriber
    exceptions don't propagate; GitHubService pauses on <50 quota; SharedAnalysisContext builds
    in <60s; DAG cycle detection exits non-zero; AIManager caches and logs every invocation;
    PromptRegistry version increments correctly.


- [ ] 11. Core Agent Implementations (8 Agents)
  - [ ] 11.1 Implement Repository Understanding Agent
    - Write `agents/core/repo_understanding.py`; `name = "repository_understanding"`; `dependencies = []`
    - Use `SharedAnalysisContext` for: language distribution, file count, directory structure,
      commit history, contributor count, framework detection
    - Call `GitHubService` (when `ENABLE_GITHUB_METADATA=true`) for: README quality score,
      LICENSE, CONTRIBUTING, SECURITY.md, CODEOWNERS, issue/PR templates, Actions workflows,
      releases, semantic versioning, branch protection — all as boolean/quality-score metrics
    - If `ENABLE_GITHUB_METADATA=false`: return `null` for all GitHub metadata fields
    - _Requirements: 3.1, 19.6, 22.6_
  - [ ]* 11.2 Write property test (Property 7)
    - **Property 7: Repository Understanding Agent Output Completeness** — all required fields non-null
    - **Validates: Requirements 3.1**
  - [ ] 11.3 Implement Security Agent
    - Write `agents/core/security.py`; `name = "security"`; `dependencies = ["repository_understanding"]`
    - Use `SharedAnalysisContext` AST cache and file index for scanning
    - Every finding MUST include: `severity`, `owasp_category`, `cwe_id`, `exploitability`,
      `fix_difficulty`, `estimated_fix_minutes`
    - _Requirements: 3.2_
  - [ ]* 11.4 Write property test (Property 8)
    - **Property 8: Security Finding Field Completeness** — every finding has all 6 fields non-null
    - **Validates: Requirements 3.2**
  - [ ] 11.5 Implement Code Quality Agent
    - Write `agents/core/code_quality.py`; `name = "code_quality"`; `dependencies = ["repository_understanding"]`
    - Compute from `SharedAnalysisContext`: cyclomatic complexity, duplication %, comment
      coverage %, naming convention compliance — per-file AND aggregate scores
    - _Requirements: 3.3_
  - [ ]* 11.6 Write property test (Property 9)
    - **Property 9: Code Quality Metric Completeness** — all 4 metrics present at per-file and aggregate
    - **Validates: Requirements 3.3**
  - [ ] 11.7 Implement Architecture Agent
    - Write `agents/core/architecture.py`; `name = "architecture"`; `dependencies = ["repository_understanding"]`
    - Identify patterns (MVC, hexagonal, microservices) and anti-patterns (with description + file_path)
    - Generate 3 Mermaid diagrams: component dependency, sequence, call graph
    - _Requirements: 3.4_
  - [ ]* 11.8 Write property test (Property 10)
    - **Property 10: Architecture Anti-Pattern Annotation Completeness** — every anti-pattern has description + file_path
    - **Validates: Requirements 3.4**
  - [ ] 11.9 Implement Dependency Agent
    - Write `agents/core/dependency.py`; `name = "dependency"`; `dependencies = ["repository_understanding"]`
    - Output 4 separate lists: direct deps, transitive deps, outdated packages, license incompatibilities
    - CVE references from OSV API or bundled snapshot
    - _Requirements: 3.5_
  - [ ]* 11.10 Write property test (Property 11)
    - **Property 11: Dependency Agent Output Coverage** — all 4 category lists present
    - **Validates: Requirements 3.5**
  - [ ] 11.11 Implement Technical Debt Agent
    - Write `agents/core/technical_debt.py`; `name = "technical_debt"`; `dependencies = ["code_quality"]`
    - Estimate debt in hours by category; remediation list ordered descending by priority
    - Output MUST include: `quick_wins_count`, `major_refactors_count`, `risk_level`, `roi_assessment`
    - _Requirements: 3.6_
  - [ ]* 11.12 Write property test (Property 12)
    - **Property 12: Technical Debt Categorization and Ordering** — 4 categories, descending priority list
    - **Validates: Requirements 3.6**
  - [ ] 11.13 Implement Executive CTO Agent
    - Write `agents/core/executive_cto.py`; `name = "executive_cto"`
    - `dependencies = ["security", "architecture", "dependency", "code_quality", "technical_debt"]`
    - Output: `overall_risk_level`, exactly 3 `strategic_recommendations`, `production_readiness_assessment`
    - Skip if `ENABLE_EXECUTIVE_CTO=false`
    - _Requirements: 3.7, 22.5_
  - [ ]* 11.14 Write property test (Property 13)
    - **Property 13: Executive CTO Agent Output Completeness** — all 3 fields non-null
    - **Validates: Requirements 3.7**
  - [ ] 11.15 Implement Repository Optimization Agent (DAG terminal node)
    - Write `agents/core/optimization.py`; `name = "repository_optimization"`
    - `dependencies = ["repository_understanding","security","code_quality","architecture","dependency","technical_debt","executive_cto"]`
    - Receive all prior results via `payload.metadata["prior_results"]`
    - Merge all findings; deduplicate by content similarity; assign Priority; estimate effort
      (hours, difficulty, business impact, engineering impact, ROI 0–10)
    - Quick Wins: top 10 with ROI ≥ 7, difficulty ≤ easy, ≤ 2 hours
    - Optimization Roadmap: Sprint 1 (Quick Wins), Sprint 2 (Security+Critical),
      Sprint 3 (Architecture), Sprint 4 (Performance+Debt)
    - Optimization Score: `max(0, 100 - min(critical*5, 50) - min(high*2, 20))`
    - Engineering Maturity: 0–24=Beginner, 25–49=Intermediate, 50–74=Advanced, 75–100=Enterprise
    - Persist `optimization_score` and `engineering_maturity_score` on `analysis_jobs` record
    - Skip if `ENABLE_OPTIMIZATION=false`
    - _Requirements: 16.1–16.7, 4.4, 4.5, 22.3_
  - [ ]* 11.16 Write property tests for Optimization Agent
    - **Property 41: Optimization Score Formula** — `max(0,100-min(c*5,50)-min(h*2,20))` for all inputs
    - **Property 42: Engineering Maturity Level Mapping** — boundary values correct
    - **Property 43: Repository Optimization Agent Sequential Execution** — starts after all deps complete
    - **Property 44: Quick Wins Filter Correctness** — every item has ROI≥7, difficulty≤easy, hours≤2
    - **Property 45: Finding Deduplication Idempotency** — `deduplicate(deduplicate(S)) == deduplicate(S)`
    - **Validates: Requirements 4.4, 4.5, 16.1–16.5**

- [ ] 12. Stub Agents
  - [ ] 12.1 Implement GenericStub base and all 17+ stub agents
    - Write `agents/stubs/stub_base.py`: `GenericStub(BaseAgent)` always returns
      `AgentOutputPayload(agent=self.name, status="stub", findings=[], summary="")`; no deps
    - Create one file per stub agent (all inherit `GenericStub`): `repository_chat.py`,
      `test_coverage.py`, `ci_cd_analysis.py`, `performance_profiling.py`,
      `api_documentation.py`, `container_analysis.py`, `cloud_cost_analysis.py`,
      `accessibility_analysis.py`, `i18n_analysis.py`, `graphql_analysis.py`,
      `database_schema.py`, `mobile_analysis.py`, `ml_model_analysis.py`,
      `realtime_monitoring.py`, `compliance_audit.py`, `refactoring_suggestions.py`,
      `changelog_generator.py`
    - _Requirements: 3.8, 15.3_
  - [ ]* 12.2 Write property test (Property 14)
    - **Property 14: Stub Agent Contract** — every stub returns status="stub", findings=[], no exception
    - **Validates: Requirements 3.8**

- [ ] 13. Checkpoint — Agent System Complete
  - Ensure all tests pass. Verify: all 8 core agents return well-formed payloads; all 17+ stubs
    return status="stub"; DAG dispatch respects topological order; SharedAnalysisContext injected
    into every agent; prompt resolved from PromptRegistry at runtime; cost logged per invocation.


- [ ] 14. Scoring System and Feature Flags Integration
  - [ ] 14.1 Implement scoring service
    - Write `application/services/scoring.py` with `WEIGHTS` dict, `compute_scores()`,
      `to_letter_grade()` (90–100=A, 80–89=B, 70–79=C, 60–69=D, 0–59=F),
      `to_maturity_level()` (0–24=Beginner, 25–49=Intermediate, 50–74=Advanced, 75–100=Enterprise)
    - Wire `optimization_score` + `engineering_maturity_score` from Optimization Agent into `analysis_jobs`
    - Document WEIGHTS in `ScoreSet` Pydantic schema for OpenAPI exposure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [ ] 14.2 Implement Feature Flags enforcement
    - Use `config.features.*` from ConfigRegistry at every callsite
    - `ENABLE_KG=false` → skip KG generation; KG endpoints return HTTP 503 with `feature_disabled`
    - `ENABLE_OPTIMIZATION=false` → skip Repository Optimization Agent dispatch
    - `ENABLE_EMBEDDINGS=false` → skip EmbeddingWorker enqueue; nodes written with `embedding=null`
    - `ENABLE_EXECUTIVE_CTO=false` → skip Executive CTO Agent
    - `ENABLE_GITHUB_METADATA=false` → skip all GitHubService calls in Repository Understanding Agent
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6_
  - [ ]* 14.3 Write property tests for scoring and feature flags
    - **Property 15: Score Range Invariant** — every dimension score is int [0,100] or null
    - **Property 16: Overall Grade Weighted Average Correctness** — formula correct with renormalization
    - **Property 17: Letter Grade Boundary Mapping** — all integers 0–100 map to exactly one grade
    - **Property 42: Engineering Maturity Level Mapping** — all boundary values correct
    - **Property 64: Feature Flag KG Bypass** — no KGNode/KGEdge records when ENABLE_KG=false
    - **Validates: Requirements 4.1–4.5, 22.1–22.6**

- [ ] 15. Knowledge Graph and WebSocket Manager
  - [ ] 15.1 Implement KG node/edge generation and async EmbeddingWorker
    - Write `application/services/kg_service.py`: extract all 14 entity types from
      `SharedAnalysisContext`; create `KGNode` records; create `KGEdge` records (5 types)
    - After node writes, enqueue `EmbeddingWorker` Celery task on `embeddings` queue
    - Write `infrastructure/workers/embedding_worker.py`: processes queue; calls
      `BedrockEmbeddingProvider`; updates `kg_nodes.embedding`
    - Report generation MUST NOT wait for embedding completion
    - Respect `ENABLE_KG` and `ENABLE_EMBEDDINGS` feature flags
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 22.2, 22.4_
  - [ ]* 15.2 Write property tests for KG
    - **Property 18: KG Node Coverage** — every identified code entity has a KGNode
    - **Property 19: KG Edge Type Validity** — every edge relationship is one of 5 types
    - **Property 20: KG Node Entity Type Validity** — every node entity_type is one of 14 types
    - **Property 47: Async Embedding Non-Blocking** — reports complete when EmbeddingWorker delayed
    - **Validates: Requirements 5.1–5.4**
  - [ ] 15.3 Implement WebSocket Manager with EventBus subscription
    - Write `presentation/websocket/handler.py` with `WebSocketManager`
    - Subscribe `ws_manager.on_agent_completed` to `AgentCompletedEvent` via EventBus
    - Subscribe `ws_manager.on_job_completed` to `JobCompletedEvent` via EventBus
    - `connect()`: accept, replay events from 60s window, emit current status, register connection
    - `emit()`: persist to replay buffer, fan-out to all connected clients
    - Expose `WS /ws/jobs/{job_id}` endpoint
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 21.4_
  - [ ]* 15.4 Write property tests for WebSocket
    - **Property 6: WebSocket Event Field Completeness** — all 5 required fields present
    - **Property 30: WebSocket On-Connect Status Delivery** — immediate status on connect
    - **Property 31: Missed WebSocket Event Replay** — reconnect within 60s replays all missed events
    - **Validates: Requirements 8.2, 8.3, 8.5**

- [ ] 16. Report Generation
  - [ ] 16.1 Implement ReportService with 5 formats
    - Write `application/services/report_service.py` triggered by `JobCompletedEvent` via EventBus
    - Generate HTML (all scores + findings + recommendations + trend charts)
    - Generate PDF (print-ready, WeasyPrint or headless Chrome)
    - Generate Markdown (structured plain text)
    - Generate JSON (conforms to OpenAPI Report schema)
    - Generate Optimization Report HTML + PDF (Executive Summary → Optimization Score →
      Priority Matrix → Quick Wins → Architecture → Security → Technical Debt → Appendix)
    - Redact secret values before persistence; retain only file_path + line_number
    - Pre-signed download URL TTL = 1 hour; retain files ≥ 30 days
    - Respect `ENABLE_REPORTS` feature flag
    - _Requirements: 6.1–6.7, 10.7, 22.1_
  - [ ]* 16.2 Write property tests for reports
    - **Property 21: All Five Report Formats Generated** — every completed job produces ≥ 5 records
    - **Property 22: HTML Report Content Completeness** — all 10 scores, findings, recommendations, trends
    - **Property 23: JSON Report Schema Conformance** — validates against OpenAPI Report schema
    - **Property 38: Secret Redaction in Reports** — no literal secret string in any report
    - **Validates: Requirements 6.1–6.5, 10.7**

- [ ] 17. Checkpoint — Core Backend Services Complete
  - Ensure all tests pass. Verify: scoring produces correct letter grades and maturity levels;
    all 5 report formats generate; secret values redacted; KG generates 14 entity types; embeddings
    non-blocking; WebSocket replays events; feature flags each bypass their respective component.


- [ ] 18. Repository Snapshot and Cache Service
  - [ ] 18.1 Implement Repository Snapshot
    - Create `repository_snapshots` record on clone completion with: `commit_sha` (HEAD),
      `branch`, `repository_url`, `clone_timestamp`, `default_branch`
    - Link snapshot to Analysis Job; include snapshot reference in every generated report
    - Use `GitHubService.get_latest_commit_sha(url)` to verify HEAD before analysis begins
    - _Requirements: 1.9, 1.10_
  - [ ] 18.2 Implement RepoCacheService
    - Write cache check in `infrastructure/workers/analysis_task.py`:
      - Get `content_hash` = latest commit SHA via `GitHubService`
      - Query `analysis_jobs` for matching `repo_url + content_hash` completed within TTL
      - **Cache hit**: copy agent results + scores to new job; set `cache_hit=true`; emit
        WebSocket `completed` event; complete within 2 seconds without cloning or dispatching agents
      - **Cache miss**: proceed with normal clone + analysis
    - Cache TTL from `ConfigRegistry.get("REPO_CACHE_TTL_HOURS", default=24)`
    - _Requirements: (implicit from design)_
  - [ ]* 18.3 Write property tests for Repository Snapshot and cache
    - **Property 52: Repository Cache Hit Correctness** — cache hit completes in <2s without cloning
    - **Property 55: Repository Snapshot SHA Verification** — SHA mismatch → job failed, no dispatch
    - **Validates: Requirements 1.9, 1.10**

- [ ] 19. Celery Workers and Repository Lifecycle
  - [ ] 19.1 Implement AnalysisJobTask with workspace layout and all cloning limits
    - Write `infrastructure/workers/analysis_task.py`
    - Create workspace directories: `workspace/{job_id}/repo/`, `/analysis/`, `/logs/`
    - Call `RepoCacheService.clone_or_cache()` first
    - On cache miss: clone with GitPython (shallow, depth=20) within 10 seconds of job creation
    - Enforce all 6 limits: 2 GB size, 500k files, 50 MB per file, depth 20, 1000 symlinks
    - On any limit breach: abort, set status `failed`, record which limit breached, emit WS event
    - On clone success: create Repository Snapshot; update status to `cloned`; emit WS event
    - Invoke `Orchestrator.run_analysis(job)` after cloning
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.8, 1.9_
  - [ ] 19.2 Implement CleanupTask
    - Write `infrastructure/workers/cleanup_task.py` (Celery beat, every 5 minutes)
    - Delete `workspace/{job_id}/` trees older than 1 hour; idempotent on already-deleted dirs
    - Do NOT delete report files (separate 30-day retention policy)
    - _Requirements: 10.3_
  - [ ]* 19.3 Write property tests for Celery workers
    - **Property 1: Malformed URL Rejection** — invalid URL → HTTP 422; no DB record
    - **Property 2: Clone Failure Job Status** — clone failure → status=failed, error persisted, WS event
    - **Property 24: Original Repository Immutability** — SHA-256 checksums unchanged before/after analysis
    - **Property 48: Workspace Path Isolation** — two jobs share no files below `workspace/`
    - **Validates: Requirements 1.2–1.6, 10.2**


- [ ] 20. REST API Endpoints
  - [ ] 20.1 Implement repository, job, and snapshot endpoints
    - `POST /api/v1/repos/analyze` (analyst+): validate URL → 422 on failure; create job; return job_id within 2s
    - `GET /api/v1/jobs/{job_id}`: status + progress + cache_hit flag
    - `GET /api/v1/jobs/{job_id}/results`: paginated agent results
    - `GET /api/v1/jobs/{job_id}/cost`: per-job AI cost breakdown by agent and provider
    - _Requirements: 1.1, 1.3, 7.1, 7.2, 23.3_
  - [ ] 20.2 Implement report, KG, and history endpoints
    - `GET /api/v1/reports/{job_id}`: list all 5 report records
    - `GET /api/v1/reports/{id}/download`: pre-signed URL (1-hour TTL)
    - `GET /api/v1/kg/{job_id}/nodes`: paginated with `entity_type` filter
    - `GET /api/v1/kg/{job_id}/edges`: paginated with `relationship` filter
    - `GET /api/v1/repos/{repo_id}/history`: paginated job summaries with all scores
    - _Requirements: 6.6, 7.1, 7.4, 7.5, 17.4_
  - [ ] 20.3 Implement admin and cost endpoints
    - `GET /api/v1/admin/users`: paginated user list (admin only)
    - `GET /api/v1/admin/cost-report`: aggregated AI cost by provider/agent/model/date (admin only)
    - `GET /api/v1/feature-flags`: current feature flag state (admin only)
    - `GET /api/v1/prompts`: prompt registry listing (admin only)
    - _Requirements: 9.4, 23.3_
  - [ ] 20.4 Implement pagination, filtering, sorting, and OpenAPI spec
    - All list endpoints: `page` + `page_size` (max 100; HTTP 422 if exceeded)
    - Filter and sort params documented in OpenAPI; HTTP 422 with per-field error on schema failure
    - Serve OpenAPI 3.1 spec at `/api/v1/docs`; include ScoreSet weight documentation
    - _Requirements: 7.2, 7.4, 7.5, 7.6, 4.2_
  - [ ]* 20.5 Write property tests for API
    - **Property 25: Rate Limit Enforcement** — all over-limit requests receive HTTP 429
    - **Property 26: Pagination Correctness** — correct slice; page_size > 100 → HTTP 422
    - **Property 27: Filter and Sort Correctness** — filtered results satisfy predicate; sorted in order
    - **Property 28: Schema Validation Error Structure** — 422 includes field + violation_message per error
    - **Validates: Requirements 7.3–7.6**

- [ ] 21. Checkpoint — Backend API Complete
  - Ensure all tests pass. Verify: all endpoints respond with correct status codes; history
    endpoint returns paginated summaries; cost-report aggregates by provider/agent; feature flags
    endpoint shows current state; prompt registry endpoint lists active prompts; no /auth/login
    endpoint exists.

- [ ] 22. Frontend Scaffolding and Pages
  - [ ] 22.1 Scaffold Vite + React + TypeScript project with all dependencies
    - Bootstrap with Vite, React 18, TypeScript; install TailwindCSS, ShadCN UI,
      `@tanstack/react-query`, Zustand, Recharts, `react-force-graph`, React Router, Lucide
    - Configure Vite proxy for `/api` and `/ws`; ESLint + strict TypeScript; `vitest`
    - Create `frontend/src/` structure: `pages/`, `components/`, `stores/`, `hooks/`, `api/`, `lib/`
    - _Requirements: 12.2, 12.3, 12.4_
  - [ ] 22.2 Implement Zustand store, auth hooks, and API client
    - `useAppStore.ts`: `authUser`, `activeJob`, `notificationQueue`, `themePreference ("dark"|"light")`
    - Persist `themePreference` to localStorage; apply theme class to `<html>` on change
    - `useAuth.ts`: JWT `exp` inspection; `setTimeout` 30s before expiry → clear store, redirect, toast
    - `useJobWebSocket.ts`: WS connection lifecycle, auto-reconnect, expose `progress`/`status`/`currentStep`
    - `api/client.ts`: typed React Query wrappers for all backend endpoints
    - _Requirements: 12.3, 12.8, 12.9_
  - [ ] 22.3 Implement Dashboard page
    - Hero section: Optimization Score, Repository Grade (letter), Repository Health,
      Engineering Maturity Score + level label — prominent at top
    - Secondary: 9 dimension score gauge/ring charts (Recharts)
    - Recent jobs list; notifications feed
    - _Requirements: 12.1, 12.5, 4.6_
  - [ ] 22.4 Implement Repository Analysis page
    - URL submission form; real-time WS progress panel (`useJobWebSocket`)
    - Agent results display (per-agent, expandable)
    - Full-text search input across findings (calls search query param on jobs results endpoint)
    - Comparison view: select 2 jobs for same repo; display all 11 scores side-by-side with delta
    - Repository Timeline chart: score history + Optimization Score trend (Recharts, from history API)
    - _Requirements: 12.1, 12.6, 12.10, 12.11, 17.2, 17.3_
  - [ ] 22.5 Implement Reports, Knowledge Graph, and Agents pages
    - `Reports.tsx`: list 5 report types; download buttons hitting `/reports/{id}/download`
    - `KnowledgeGraph.tsx`: force-directed graph; node detail panel with metadata, edges, AI summary,
      inferred purpose, complexity score, optimization suggestions
    - `Agents.tsx`: catalog all 25+ agents with name, type (core/stub), last-run status + output summary
    - _Requirements: 12.1, 5.5, 5.6_
  - [ ] 22.6 Implement Settings, Profile, and Admin pages
    - `Settings.tsx`: dark/light theme toggle (wired to Zustand, persisted localStorage);
      API key management (create, list, revoke)
    - `Profile.tsx`: user info, GitHub OAuth connection status, activity history
    - `Admin.tsx` (admin only): user list, audit log viewer, feature flags viewer, prompt registry
    - _Requirements: 12.1, 12.9_
  - [ ] 22.7 Implement responsive layout and React Router
    - Configure routes for all 8 pages; protected routes redirect to `/login` on 401
    - Responsive layout: sidebar collapses to hamburger at ≤ 768px; usable 375px–1920px
    - _Requirements: 12.7_

- [ ] 23. Checkpoint — Frontend Complete
  - Ensure all tests pass. Verify: Dashboard shows Optimization Score + Grade + Health +
    Maturity hero; theme toggle persists; comparison view shows deltas; Timeline chart renders;
    Admin shows feature flags and prompts; all pages render at 375px and 1920px.


- [ ] 24. Integration Tests
  - [ ] 24.1 Write backend integration tests
    - AI provider fallback chain: mock Ollama timeout → assert Claude called; both fail → Bedrock
    - Celery worker begins clone within 10 seconds of job creation
    - Workspace cleanup: workspace deleted within 1 hour by CleanupTask
    - EmbeddingWorker processes queue without blocking report generation (delay worker; reports still generated)
    - Docker Compose `docker compose up` all services healthy within 3 minutes
    - GitHub rate limit: mocked `X-RateLimit-Remaining: 0` → pause → successful retry
    - Feature flag `ENABLE_KG=false`: no KGNode records created; KG endpoints return HTTP 503
    - Cache hit: new job completes within 2s with `cache_hit=true` when same repo+commit analyzed before
    - _Requirements: 11.1–11.4, 1.2, 10.3, 5.4, 14.3, 19.3, 22.2_
  - [ ] 24.2 Write security header and NGINX integration tests
    - Assert all 4 security headers present on every NGINX response:
      `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`
    - _Requirements: 10.6_
  - [ ]* 24.3 Write frontend integration tests
    - `useAuth` hook: JWT expiry redirects to login with toast
    - `useJobWebSocket`: reconnect within 60s replays all missed events
    - Dashboard: renders all 4 hero metrics from mock API
    - Comparison view: score deltas calculated and displayed correctly
    - _Requirements: 12.8, 8.5, 12.11_

- [ ] 25. OpenAPI Docs, README, and Deployment Documentation
  - [ ] 25.1 Finalize OpenAPI spec and documentation
    - Verify all 25 endpoints in OpenAPI spec with request/response schemas
    - Document `ScoreSet` weight coefficients in `Field` descriptions (OpenAPI-visible)
    - Document `FeatureFlags` state in admin endpoint
    - Verify no `/auth/login` endpoint in spec
    - _Requirements: 7.2, 4.2_
  - [ ] 25.2 Write README and deployment guide
    - `README.md`: prerequisites, `docker compose up` quickstart, env var reference,
      feature flags guide, AI_PROVIDER_ORDER configuration, running tests
    - `docs/deployment.md`: production Docker Compose, TLS setup, initial Alembic migration,
      seeding prompt registry, smoke test checklist
    - _Requirements: 14.3_

- [ ] 26. Final Checkpoint — All Tests Pass, Deployment Verified
  - Full end-to-end: submit GitHub repo URL → clone → SharedAnalysisContext built once →
    DAG dispatch (security/arch/dep/quality wave concurrently after repo_understanding) →
    technical_debt after code_quality → executive_cto after all → optimization last →
    EventBus triggers reports + WS updates + audit + metrics → 5 reports generated →
    KG nodes/edges persisted → embeddings enqueued non-blocking → costs logged per invocation →
    Repository Snapshot persisted → WebSocket terminal event → Frontend Dashboard shows
    Optimization Score + Grade + Health + Maturity + 9 dimension scores
  - Verify: all 25 requirements covered; all 64 correctness properties tested;
    no hardcoded secrets; ConfigRegistry validates on startup; DAG cycle detection works;
    all feature flags correctly bypass their components.

---

- [ ] 27. Job Lifecycle, Repository Cache, and Worker Specialization
  - [ ] 27.1 Implement job lifecycle management (cancel/retry/pause/resume)
    - Update `analysis_jobs.status` enum to the 12-state set: `pending`, `queued`, `cloning`,
      `cloned`, `running`, `completed`, `failed`, `cancel_requested`, `cancelled`, `retrying`,
      `paused`, `cached`
    - Add routes in `presentation/api/v1/jobs.py`:
      - `POST /api/v1/jobs/{job_id}/cancel` — set status to `cancel_requested`; Celery worker
        checks flag and transitions to `cancelled` within 30 seconds
      - `POST /api/v1/jobs/{job_id}/retry` — creates a new Analysis Job for same repo_id;
        returns new job_id
      - `POST /api/v1/jobs/{job_id}/pause` — suspends agent dispatch at next wave boundary
      - `POST /api/v1/jobs/{job_id}/resume` — continues from last completed wave
    - Publish `JobTerminalEvent` to EventBus on every terminal state transition
    - _Requirements: 26.1–26.5_
  - [ ] 27.2 Implement repository cache with composite key and invalidation
    - Create `repository_caches` ORM model and Alembic migration
    - Cache key = `repo_url + branch + commit_sha + analysis_version + prompt_versions_hash`
    - Implement `RepoCacheService`: on cache hit copy all artifacts, set `cache_hit=true`,
      complete within 2 seconds; invalidate on commit_sha / analysis_version / prompt change
    - _Requirements: 27.1–27.5_
  - [ ] 27.3 Implement worker specialization with 7 Celery queues
    - Add `celeryconfig.py` with `task_routes` mapping each task to its queue:
      `clone`, `parse`, `ai`, `kg`, `embed`, `report`, `cleanup`
    - Update `docker-compose.yml` to define one `celery_worker` service per queue
    - `docker-compose.override.yml` runs all queues on a single worker for local dev
    - Move each task to its designated worker module under `infrastructure/workers/`
    - _Requirements: 28.1–28.3_
  - [ ]* 27.4 Write property tests for job lifecycle and cache
    - **Property 65: Job Status State Machine Completeness** — all transitions produce valid states
    - **Property 66: Cancel Acknowledgement Timing** — cancelled within 30s of cancel request
    - **Property 67: Repository Cache Key Uniqueness** — differing key fields → no cache hit
    - **Property 68: Repository Cache Hit Completeness** — cache hit includes all artifacts
    - **Property 69: Worker Queue Routing** — every task placed on designated queue, not default
    - **Validates: Requirements 26.1–26.5, 27.1–27.5, 28.2**

- [ ] 28. Health Endpoints, Observability, and SLAs
  - [ ] 28.1 Implement health, readiness, liveness, and Prometheus metrics endpoints
    - Write `GET /health` checking all subsystems: database connectivity, Redis ping,
      Celery worker count + queue depths per queue, GitHub API remaining quota
    - Write `GET /ready` → HTTP 200 when DB connected + all migrations applied, else HTTP 503
    - Write `GET /live` → HTTP 200 always (simple heartbeat)
    - Write `GET /metrics` returning Prometheus text with all specified metrics:
      `repogenius_active_jobs`, `repogenius_queue_depth{queue}`,
      `repogenius_agent_duration_seconds{agent}`, `repogenius_ai_cost_usd_total{provider}`,
      `repogenius_cache_hit_ratio`, `repogenius_analysis_duration_seconds`,
      `repogenius_operation_duration_seconds{operation}` (histogram for SLA tracking)
    - _Requirements: 29.1–29.4_
  - [ ] 28.2 Implement structured logging with all required fields
    - Configure JSON structured logging backend (e.g., `structlog` or `python-json-logger`)
    - Every log entry MUST include: `job_id`, `agent`, `request_id`, `trace_id`,
      `correlation_id`, `duration_ms`, `provider`, `status`, `level`, `message`, `timestamp`
    - Emit WARNING log when any operation exceeds its p95 SLA target
    - _Requirements: 29.5, 30.2_
  - [ ]* 28.3 Write property tests for observability
    - **Property 70: Health Endpoint Subsystem Coverage** — all 4 subsystems in /health response
    - **Property 71: SLA Breach Warning Emission** — WARNING log emitted on every SLA breach
    - **Validates: Requirements 29.1, 30.2**

- [ ] 29. Expanded Static Analysis and Cross-Reference Index
  - [ ] 29.1 Expand Code Quality Agent with additional metrics
    - Add to `agents/core/code_quality.py`:
      - Maintainability Index (per-file and aggregate, 0–100)
      - Cognitive Complexity (per-function and aggregate)
      - Dead Code percentage (unreachable functions/classes)
      - Unused Imports count, Unused Variables count
      - Long Methods count (functions > 50 lines)
      - Large Classes count (classes > 300 lines)
      - Magic Numbers count
    - _Requirements: 31.1_
  - [ ] 29.2 Expand Architecture Agent with coupling and structural metrics
    - Add to `agents/core/architecture.py`:
      - God Classes detection (> 20 methods or > 500 lines)
      - Circular Dependencies between modules
      - Layer Violations (wrong-direction boundary crossings)
      - Fan-In, Fan-Out, Instability Index (Fan-Out / (Fan-In + Fan-Out))
      - Afferent Coupling, Efferent Coupling
    - _Requirements: 31.2_
  - [ ] 29.3 Expand Technical Debt Agent with financial and priority metrics
    - Add to `agents/core/technical_debt.py`:
      - Cost in USD (configurable developer hourly rate from ConfigRegistry)
      - Priority Score (0–10 composite of ROI and risk)
      - Interest Rate (debt growth rate as % per sprint)
      - Debt Category (design, code, test, documentation)
    - _Requirements: 31.3_
  - [ ] 29.4 Implement CrossReferenceIndex in SharedAnalysisContextBuilder
    - Extend `agents/shared_context.py` to build `CrossReferenceIndex` during single parse pass
    - For all covered symbol types (functions, classes, methods, constants, exported variables,
      HTTP routes, React components, hooks, Celery tasks): map to `defined_in`,
      `referenced_by`, `imported_by`, `calls`, `called_by`
    - Expose as `SharedAnalysisContext.cross_reference_index` (read-only, injected into all agents)
    - Update KG service to use CrossReferenceIndex for `calls`, `called_by`, `imports`,
      `depends_on` edge creation — no independent file re-parsing for KG edges
    - _Requirements: 32.1–32.4_
  - [ ]* 29.5 Write property tests for expanded analysis and cross-reference index
    - **Property 72: CrossReferenceIndex Symbol Coverage** — all covered symbols have entries
    - **Property 73: CrossReferenceIndex Immutability** — no agent mutates the index
    - **Property 74: KG Edge Population from CrossReferenceIndex** — KG edges sourced from index
    - **Validates: Requirements 31.1–31.3, 32.1–32.4**

- [ ] 30. Additional Frontend Pages
  - [ ] 30.1 Implement Analysis Queue page
    - Write `frontend/src/pages/AnalysisQueue.tsx`
    - List all active/pending jobs with status, repository, progress bar
    - Action buttons: Cancel (calls `POST /jobs/{id}/cancel`), Retry
      (calls `POST /jobs/{id}/retry`), Pause/Resume
    - Real-time updates via `useJobWebSocket` for each listed job
    - _Requirements: 33.1, 33.2_
  - [ ] 30.2 Implement Cost Dashboard page
    - Write `frontend/src/pages/CostDashboard.tsx`
    - Provider Cost breakdown bar chart, Agent Cost breakdown, Cache Hit % gauge,
      Money Saved metric, Daily Spend trend, Monthly Spend trend, Average Job Cost
    - All data from `GET /api/v1/admin/cost-report` via React Query
    - _Requirements: 33.1, 33.3_
  - [ ] 30.3 Implement System Health page
    - Write `frontend/src/pages/SystemHealth.tsx`
    - Subsystem status cards (Database, Redis, Celery queues with depth, GitHub API quota)
    - Data from `GET /health`; manual refresh button + auto-poll every 30s
    - _Requirements: 33.1, 33.4_
  - [ ] 30.4 Implement Notifications and API Keys pages
    - Write `frontend/src/pages/Notifications.tsx`: user notifications list with
      mark-as-read, mark-all-read, clear-all buttons
    - Write `frontend/src/pages/APIKeys.tsx`: create new key (name + expiry input),
      table of existing keys (name, last_used_at, created_at), revoke button per key
    - _Requirements: 33.1, 33.5, 33.6_
  - [ ] 30.5 Add new pages to React Router
    - Add routes for `AnalysisQueue`, `CostDashboard`, `SystemHealth`, `Notifications`,
      `APIKeys` in `src/App.tsx`; protect routes requiring auth
    - Update sidebar navigation to include all 13 pages
    - _Requirements: 33.1_

- [ ] 31. Additional DB Tables and Discovery API Endpoints
  - [ ] 31.1 Add ai_models, job_metrics, and agent_metrics ORM models and migration
    - Write `infrastructure/db/models/ai_models.py`: provider, model_name, context_window,
      input_price_per_1k_tokens, output_price_per_1k_tokens, status, updated_at
    - Write `infrastructure/db/models/job_metrics.py`: job_id, clone_duration_ms,
      parse_duration_ms, kg_duration_ms, report_duration_ms, total_duration_ms,
      peak_memory_mb, total_tokens, total_cost_usd, cache_hit_count, agent_error_count
    - Write `infrastructure/db/models/agent_metrics.py`: job_id, agent_name,
      execution_time_ms, cache_hits, retry_count, input_tokens, output_tokens,
      estimated_cost_usd, status
    - Generate Alembic migration for all 3 new tables
    - ConfigRegistry loads AI pricing constants from `ai_models` table at startup
    - Populate `job_metrics` and `agent_metrics` at job completion via EventBus subscriber
    - _Requirements: 34.1–34.3_
  - [ ] 31.2 Implement discovery API endpoints
    - `GET /api/v1/agents` — list all registered agents: name, version, dependencies, last-run status
    - `GET /api/v1/providers` — current AI provider config: providers in order, active models
      per provider, rate limit status from RateLimitManager
    - `GET /api/v1/system/status` — platform version, uptime, active job count,
      queue depths per worker, feature flag state
    - _Requirements: 34.4–34.6_

- [ ] 32. Final Gap Closure — Requirements 35–40
  - [ ] 32.1 Implement analysis versioning on analysis_jobs
    - Add `analysis_version`, `agent_bundle_version`, `schema_version` columns to `analysis_jobs` ORM model
    - Generate Alembic migration; populate all three fields in `AnalysisJobService.create_job()` from `ConfigRegistry` and `alembic_context.get_current_head()`
    - `agent_bundle_version` = SHA-256 of sorted `(agent.name, agent.version)` pairs from the registry at dispatch time
    - Update `GET /api/v1/jobs/{job_id}` response to include all three fields
    - Update cache invalidation: stale if `analysis_version` or `agent_bundle_version` differs
    - _Requirements: 35.1–35.4_
  - [ ] 32.2 Implement agent version tracking on agent_results
    - Add `agent_version`, `prompt_name`, `prompt_version`, `model`, `provider` columns to `agent_results` ORM model
    - Generate Alembic migration
    - Populate all five fields in the Orchestrator immediately after `safe_run()` returns, before persisting
    - Update `GET /api/v1/jobs/{job_id}/results` response schema to include all five fields
    - _Requirements: 36.1–36.3_
  - [ ] 32.3 Implement completed_with_warnings status
    - Add `completed_with_warnings` to `analysis_jobs.status` enum and `agent_errors` (JSON array) column
    - Update Orchestrator final status logic: if any Core Agent result has `status="error"`, set job to `completed_with_warnings` and populate `agent_errors`
    - Update Frontend: warning badge on `completed_with_warnings` jobs; Report page banner listing failed agents and null score dimensions
    - _Requirements: 37.1–37.4_
  - [ ] 32.4 Implement GET /api/v1/system/version endpoint
    - Add unauthenticated `GET /api/v1/system/version` route returning: `api_version`, `analysis_engine_version`, `schema_version`, `frontend_version`, `git_commit_sha`
    - Inject `GIT_COMMIT_SHA` via Docker build arg; default to `"unknown"` if not set
    - Route requires NO authentication
    - _Requirements: 38.1–38.3_
  - [ ] 32.5 Implement consistent error taxonomy
    - Define `ErrorCode` enum in `domain/value_objects/error_codes.py` with all 12 codes
    - Write `ErrorResponseMiddleware` (FastAPI exception handler) that wraps all 4xx/5xx responses with `{"error_code": ..., "detail": ..., "status": ...}` envelope
    - Ensure `error_code` is `null` or absent on 2xx responses
    - Document all error codes in OpenAPI spec
    - _Requirements: 39.1–39.3_
  - [ ] 32.6 Implement configurable data retention policies and enforce via CleanupWorker
    - Add `RetentionSettings` to `ConfigRegistry` with all 7 TTL fields and documented defaults
    - Update `CleanupWorker` to enforce each retention policy: workspaces (1h), logs (90d), job_metrics (365d), ai_invocation_logs (90d), repository_caches (24h), kg_node embeddings null-out (30d after job expiry), reports (30d)
    - Idempotent: already-deleted resources log debug + continue
    - Write audit log entry (`event_type`, `user_id=null`, `reason="retention_policy"`) for every deletion
    - _Requirements: 40.1–40.3_
  - [ ]* 32.7 Write property tests for requirements 35–40
    - **Property 75: Analysis Version Fields Populated** — all 3 version fields non-null on every new job
    - **Property 76: Cache Invalidation on Version Change** — differing analysis/bundle version → no cache hit
    - **Property 77: Agent Result Version Fields Completeness** — all 5 agent result version fields non-null
    - **Property 78: Partial Completion State Correctness** — any Core Agent error → `completed_with_warnings`
    - **Property 79: Version Endpoint Unauthenticated Availability** — `/system/version` returns 200 without auth
    - **Property 80: Error Code Presence on Error Responses** — every 4xx/5xx has non-null `error_code`
    - **Property 81: Error Code Null on Success** — every 2xx has null/absent `error_code`
    - **Property 82: Retention Policy Idempotency** — repeat cleanup on deleted resource does not raise
    - **Property 83: Retention Policy Audit Log Completeness** — every retention deletion produces audit entry
    - **Property 84: Agent Bundle Version Determinism** — same agent set always produces same bundle hash
    - **Property 85: Completed-With-Warnings Dashboard Visibility** — warning indicator shown in UI
    - **Validates: Requirements 35–40**

- [ ] 33. Final Checkpoint — Specification Complete, All 40 Requirements Verified
  - Ensure all tests pass (pytest + vitest). Verify:
    - All 85 correctness properties have a corresponding test
    - `analysis_version`, `agent_bundle_version`, `schema_version` populated on every new job
    - `agent_results` records include all 5 version fields
    - Jobs with partial agent failures show `completed_with_warnings` with `agent_errors` list
    - `GET /api/v1/system/version` returns 200 without auth with all 5 fields
    - All error responses include a valid `error_code` from the taxonomy
    - CleanupWorker enforces all 7 retention policies idempotently with audit entries
    - `agent_bundle_version` is deterministic for the same agent set regardless of discovery order
    - No hardcoded secrets; all 40 requirements covered; spec is frozen

---

## Notes

- Tasks marked `*` are optional property/integration tests — skip for faster MVP
- Checkpoints at tasks 5, 10, 13, 17, 21, 23, 26, 33 are quality gates
- The `depends_on` declaration on each `BaseAgent` subclass drives the entire Orchestrator
  dispatch order — no manual phase management needed
- GitHub OAuth + API Key are the ONLY auth methods — never add username/password login
- `AI_PROVIDER_ORDER` env var controls provider fallback order — never hard-code provider names
- All business logic lives in `domain/` or `application/` layers — never in route handlers or ORM models
- The EventBus is the only connection between the Orchestrator and WebSocket/audit/metrics/reports
- **Specification is FROZEN** — 40 requirements, 85 correctness properties. No further additions.
- All 85 correctness properties coverage:
  - Props 1–2: task 19.3 | Props 3–6: task 8.5 | Props 7–14: tasks 11.2–12.2
  - Props 15–17, 42: task 14.3 | Props 18–20: task 15.2 | Props 21–23: task 16.2
  - Props 24, 48: task 19.3 | Props 25–28: task 20.5 | Props 29–37: task 4.6
  - Prop 38: task 16.2 | Prop 39, 46, 54, 62, 63: task 9.8 | Prop 40, 56, 58: task 8.5
  - Props 41–45: task 11.16 | Prop 47: task 15.2 | Props 49–50, 57: task 7.2
  - Props 51, 61: task 6.3 | Prop 52, 55: task 18.3 | Prop 53: task 9.8
  - Props 59–60: task 2.5 | Prop 64: task 14.3
  - Props 65–69: task 27.4 | Props 70–71: task 28.3 | Props 72–74: task 29.5
  - Props 75–85: task 32.7

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["2.5", "3.1"] },
    { "id": 4, "tasks": ["3.2"] },
    { "id": 5, "tasks": ["3.3", "4.1", "4.2", "4.3", "4.4", "4.5"] },
    { "id": 6, "tasks": ["4.6"] },
    { "id": 7, "tasks": ["6.1", "6.2"] },
    { "id": 8, "tasks": ["6.3", "7.1"] },
    { "id": 9, "tasks": ["7.2", "8.1", "8.2"] },
    { "id": 10, "tasks": ["8.3"] },
    { "id": 11, "tasks": ["8.4"] },
    { "id": 12, "tasks": ["8.5", "9.1", "9.2", "9.3", "9.4", "9.5"] },
    { "id": 13, "tasks": ["9.6", "9.7"] },
    { "id": 14, "tasks": ["9.8", "11.1", "11.3", "11.5", "11.7", "11.9", "11.11", "11.13"] },
    { "id": 15, "tasks": ["11.2", "11.4", "11.6", "11.8", "11.10", "11.12", "11.14", "12.1"] },
    { "id": 16, "tasks": ["11.15", "12.2"] },
    { "id": 17, "tasks": ["11.16", "14.1"] },
    { "id": 18, "tasks": ["14.2"] },
    { "id": 19, "tasks": ["14.3", "15.1", "15.3", "29.1", "29.2", "29.3"] },
    { "id": 20, "tasks": ["15.2", "15.4", "16.1", "29.4"] },
    { "id": 21, "tasks": ["16.2", "18.1", "29.5"] },
    { "id": 22, "tasks": ["18.2", "19.1", "27.1", "27.2", "27.3"] },
    { "id": 23, "tasks": ["18.3", "19.2", "27.4", "28.1", "28.2"] },
    { "id": 24, "tasks": ["19.3", "20.1", "20.2", "20.3", "28.3", "31.1"] },
    { "id": 25, "tasks": ["20.4", "31.2"] },
    { "id": 26, "tasks": ["20.5", "22.1"] },
    { "id": 27, "tasks": ["22.2"] },
    { "id": 28, "tasks": ["22.3", "22.4", "22.5", "22.6", "30.1", "30.2", "30.3", "30.4"] },
    { "id": 29, "tasks": ["22.7", "30.5"] },
    { "id": 30, "tasks": ["24.1", "24.2", "24.3"] },
    { "id": 31, "tasks": ["25.1", "25.2"] },
    { "id": 32, "tasks": ["32.1", "32.2", "32.3", "32.4", "32.5", "32.6"] },
    { "id": 33, "tasks": ["32.7"] }
  ]
}
```
