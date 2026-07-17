# Requirements Document

## Introduction

RepoGenius AI is an AI-powered Multi-Agent Developer Intelligence and Repository Optimization Platform delivered as a SaaS application. It enables software teams to submit a Git repository URL and receive a comprehensive, automated analysis produced by a coordinated suite of specialized AI agents. The platform provides security audits, architecture reviews, code quality assessments, dependency analysis, technical debt estimation, repository optimization roadmaps, executive and developer reports, a knowledge graph, and real-time progress streaming — all without ever modifying the user's source code.

The Version 1 MVP is a single-tenant, full-stack deployment consisting of a FastAPI backend, a React/TypeScript frontend, PostgreSQL + Redis persistence, Celery async workers, and a hybrid AI backend (configurable provider order, default: Ollama primary, Anthropic Claude + AWS Bedrock fallback). Version 1 includes 8 fully implemented Core Agents (Repository Understanding, Security, Code Quality, Architecture, Dependency, Technical Debt, Executive CTO, and Repository Optimization) coordinated through a dependency-aware Agent Execution DAG, 17+ Stub Agents (including a Repository Chat stub), a Knowledge Graph with Titan Embeddings, a Repository Optimization Engine, and a five-format report export engine.

All agents share a pre-built `SharedAnalysisContext` constructed exactly once per Analysis Job before any agent is dispatched, eliminating redundant file parsing. The Orchestrator dispatches agents according to a declared dependency DAG — agents with no unresolved dependencies run concurrently while downstream agents wait for their predecessors. The platform follows a Clean Architecture with four explicit layers (Presentation, Application, Domain, Infrastructure) and an in-process `EventBus` that decouples the Orchestrator from WebSocket, audit, metrics, notification, and report-generation concerns.

The platform includes repository caching (reusing results when content has not changed) and immutable Repository Snapshot metadata (commit SHA, branch, tag, clone timestamp) linked to every Analysis Job for reproducibility. LLM cost and token usage are tracked per invocation and per job via a dedicated `ai_invocation_logs` table. All AI prompt templates are versioned via a database-backed Prompt Registry to enable report reproduction. All GitHub API calls are routed exclusively through `GitHubService` with a `RateLimitManager` that enforces quota management, ETag conditional requests, and exponential backoff. Runtime Feature Flags allow platform capabilities to be enabled or disabled via environment variables without redeployment. All configuration is accessed through a single typed `ConfigRegistry` singleton.

This document defines 40 requirements for the Version 1 MVP, which is now frozen for implementation. Requirements 26–34 capture the operational additions (job lifecycle, caching, worker specialization, observability, SLAs, expanded analysis, cross-reference index, additional pages, and metrics tables). Requirements 35–40 are the final refinements: full job lifecycle management (cancel, retry, pause, and resume with a 12-state status machine); a repository cache specification keyed by composite content hash with explicit invalidation rules; worker specialization across 7 dedicated Celery queues (clone, parse, ai, kg, embed, report, cleanup); health, readiness, liveness, and Prometheus metrics endpoints; explicit p95 performance SLA targets for all pipeline operations; expanded static analysis metrics in the Code Quality Agent (Maintainability Index, Cognitive Complexity, Dead Code, Long Methods, Large Classes, Magic Numbers) and the Architecture Agent (God Classes, Circular Dependencies, Layer Violations, Fan-In, Fan-Out, Instability Index, Afferent and Efferent Coupling); a `CrossReferenceIndex` built as part of `SharedAnalysisContext` mapping every symbol to its definition, references, imports, and call graph; 13 frontend pages (including Analysis Queue, Notifications, API Keys, Cost Dashboard, and System Health); and dedicated `ai_models`, `job_metrics`, and `agent_metrics` database tables with discovery endpoints for agents, providers, and system status.

> **Version 2 Features:** Code Translation (automated language-to-language repository migration) and PR Review (AI-powered pull request analysis) are planned for Version 2 and are not part of the Version 1 MVP. The platform is designed as an extensible Developer Intelligence and Repository Optimization Platform with a plugin-based agent architecture that accommodates these and other capabilities over time without requiring breaking changes to the core system.

---

## Glossary

- **Platform**: The RepoGenius AI SaaS application as a whole.
- **Backend**: The FastAPI Python service that exposes the REST API and orchestrates analysis jobs.
- **Frontend**: The React/Vite/TypeScript single-page application consumed by end users.
- **Orchestrator**: The single coordinating component responsible for dispatching work to agents and aggregating their results. No agent may call another agent directly.
- **Agent**: A discrete analytical unit that inherits from `BaseAgent`, accepts a standardized input payload from the Orchestrator, and returns a standardized output payload to the Orchestrator.
- **BaseAgent**: The abstract base class that defines the common interface, lifecycle hooks, and error-handling contract for all agents.
- **Core Agent**: One of the eight fully implemented agents in Version 1: Repository Understanding, Security, Code Quality, Architecture, Dependency, Technical Debt, Executive CTO, and Repository Optimization.
- **Stub Agent**: One of the 17+ agents whose schema and interface are fully defined in Version 1 but whose analytical logic is not yet implemented. Includes Repository Chat as a stub.
- **Repository Chat**: An AI-powered Q&A stub agent that enables natural language interaction with a repository's analysis results. Planned for full implementation in a future version.
- **Analysis Job**: An async Celery task that clones a repository, runs the Orchestrator, persists results, and emits WebSocket progress events.
- **Knowledge Graph**: A graph structure of nodes and edges representing code entities, their relationships, and metadata extracted from a repository.
- **Report**: A structured document generated from agent results, available in HTML, PDF, Markdown, and JSON formats.
- **Repository Health Score**: A composite numeric score (0–100) reflecting overall repository quality.
- **Optimization Score**: A composite 0–100 score derived by the Repository Optimization Engine representing the actionability and improvement readiness of a repository.
- **Engineering Maturity Score**: A 0–100 score mapped to four levels (Beginner, Intermediate, Advanced, Enterprise) reflecting the overall engineering practices quality of a repository.
- **Repository Optimization Agent**: The Core Agent that runs after all other agents, merging findings, deduplicating, prioritizing, and generating the Optimization Roadmap and Optimization Score.
- **Optimization Roadmap**: A sprint-organized plan of repository improvements generated by the Repository Optimization Agent.
- **Quick Wins**: Optimization findings with ROI ≥ 7 and fix difficulty ≤ easy, listed as immediately actionable items.
- **AIManager**: The abstraction layer through which all agent AI calls are routed, providing PromptBuilder, ProviderRouter, ResponseParser, ResponseCache, and InvocationLogger sub-components.
- **JWT**: JSON Web Token used for stateless session authentication.
- **RBAC**: Role-Based Access Control governing which authenticated users may perform which actions.
- **Audit Log**: An immutable record of user and system actions stored in the database.
- **API Key**: A long-lived credential issued to a user for programmatic API access.
- **Redis**: The in-memory data store used for Celery task queuing and caching.
- **Celery**: The distributed task queue used to execute Analysis Jobs asynchronously.
- **GitPython**: The Python library used by the Backend to clone and inspect Git repositories.
- **Ollama**: A local AI model provider supported by the configurable AI provider chain.
- **Claude**: Anthropic's Claude API supported as an AI provider in the configurable chain.
- **Bedrock**: AWS Bedrock supported as an AI provider in the configurable chain.
- **Titan Embeddings**: The AWS Titan embedding model used to generate vector representations for Knowledge Graph nodes.
- **OpenAPI**: The machine-readable API specification format exposed by the Backend via Swagger UI.
- **WebSocket**: The persistent bidirectional connection used to stream real-time progress updates to the Frontend.
- **NGINX**: The reverse proxy that routes traffic to the Backend and serves the Frontend static assets.
- **Docker Compose**: The container orchestration tool used for local and production deployment of all services.
- **ScoreSet**: The complete collection of all computed dimension scores for a single Analysis Job.
- **content_hash**: A hash derived from a repository's latest commit SHA used to identify whether a repository's content has changed between analysis runs.
- **Shared Analysis Context**: A pre-built, read-only data structure containing AST cache, Symbol Table, Dependency Graph, File Index, Language Map, Git Metadata, and Framework Detection results, constructed once per Analysis Job and injected into every agent's input payload.
- **Repository Snapshot**: An immutable record of repository state at cloning time, including `commit_sha`, `branch`, `repository_url`, `clone_timestamp`, and `default_branch`.
- **GitHubService**: The dedicated service that mediates all GitHub API calls with rate limit management, ETag conditional requests, and exponential backoff retry.
- **RateLimitManager**: A component within `GitHubService` that inspects GitHub API rate limit headers and automatically waits and retries when the quota is exhausted.
- **EventBus**: The in-process publish/subscribe component that decouples the Orchestrator from WebSocket, audit, metrics, notification, and report-generation concerns.
- **Feature Flags**: Boolean environment-variable toggles that enable or disable platform capabilities at startup without redeployment.
- **ConfigRegistry**: The singleton Pydantic-backed configuration registry through which all components access environment variables and typed settings.
- **Prompt Registry**: The database-backed versioned store of all agent prompts, ensuring prompt changes are traceable and invocations are reproducible.
- **Agent Dependency DAG**: The directed acyclic graph of agent execution dependencies, determining which agents may run concurrently and which must wait for specific predecessors.
- **CrossReferenceIndex**: A per-repository index mapping every symbol to its definition location, references, imports, call graph, and reverse call graph; built as part of SharedAnalysisContext.
- **SLA**: Service Level Agreement — documented performance targets for individual operations.
- **Instability Index**: A software metric equal to Fan-Out / (Fan-In + Fan-Out); 0 = maximally stable, 1 = maximally unstable.

---

## Requirements

### Requirement 1: Repository Submission and Cloning

**User Story:** As a developer, I want to submit a Git repository URL so that the Platform can clone and analyze it.

#### Acceptance Criteria

1. WHEN an authenticated user submits a valid Git repository URL via the REST API, THE Backend SHALL create an Analysis Job record in the database with status `pending` and return the job ID in the response within 2 seconds.
2. WHEN an Analysis Job is created, THE Celery worker SHALL begin cloning the repository to an isolated workspace at the path `workspace/{job_id}/repo/` using GitPython within 10 seconds of job creation; THE workspace SHALL also contain `workspace/{job_id}/analysis/` and `workspace/{job_id}/logs/` subdirectories.
3. IF the provided repository URL is malformed or unreachable, THEN THE Backend SHALL return an HTTP 422 response with a structured error body describing the validation failure before creating any database record.
4. IF cloning fails due to authentication failure, network timeout, or repository not found, THEN THE Celery worker SHALL mark the Analysis Job status as `failed`, persist an error message, and emit a failure WebSocket event to the connected client.
5. THE Backend SHALL enforce a maximum cloned repository size of 2 GB; IF a repository exceeds this limit, THEN THE Celery worker SHALL abort cloning, mark the Analysis Job as `failed`, and record the reason.
6. THE Backend SHALL enforce the following cloning limits in addition to the 2 GB size cap: maximum 500,000 files, maximum individual file size of 50 MB, maximum directory depth of 20 levels, and maximum symlink count of 1,000; IF any limit is exceeded, THEN THE Celery worker SHALL abort cloning, mark the Analysis Job as `failed`, and record which limit was breached.
7. THE Backend SHALL validate repository URLs against an allowlist of permitted schemes and hosts (`https://github.com/*`, `https://gitlab.com/*`, `https://bitbucket.org/*`); `file://`, `ssh://`, local paths, and git submodule hooks SHALL be rejected before cloning begins.
8. WHEN cloning completes successfully, THE Celery worker SHALL update the Analysis Job status to `cloned` and emit a progress WebSocket event.
9. WHEN cloning completes successfully, THE Backend SHALL create a Repository Snapshot record and persist it alongside the Analysis Job; THE Repository Snapshot SHALL include: `commit_sha` (HEAD), `branch`, `repository_url`, `clone_timestamp`, and `default_branch`.
10. ALL reports generated for an Analysis Job SHALL reference the associated Repository Snapshot so that any report is reproducible by re-cloning the same commit SHA.

---

### Requirement 2: Multi-Agent Orchestration

**User Story:** As a developer, I want the Platform to coordinate multiple specialized AI agents so that I receive a holistic repository analysis without managing individual agent calls.

#### Acceptance Criteria

1. THE Orchestrator SHALL be the sole component permitted to invoke agents; no Agent SHALL call another Agent directly.
2. WHEN an Analysis Job reaches `cloned` status, THE Orchestrator SHALL execute agents according to a declared Agent Dependency DAG; agents with no unresolved dependencies SHALL execute concurrently (bounded by the concurrency semaphore); an agent SHALL NOT begin execution until all of its declared dependency agents have completed successfully or with `error` status.
3. WHEN an Agent completes, THE Agent SHALL return its result payload exclusively to the Orchestrator; THE Orchestrator SHALL persist the result as an Agent Result record linked to the Analysis Job.
4. IF an Agent raises an unhandled exception, THEN THE Orchestrator SHALL mark that Agent's result as `error`, log the stack trace, and continue processing results from remaining Agents without aborting the Analysis Job.
5. THE BaseAgent SHALL define a `run(payload: AgentInputPayload) -> AgentOutputPayload` method that all Agents MUST implement.
6. THE BaseAgent SHALL define standard lifecycle hooks — `pre_run`, `post_run`, and `on_error` — that all Agents inherit and MAY override.
7. THE Orchestrator SHALL emit a WebSocket progress event after each Agent result is received, including the agent name, status, and completion percentage.
8. EACH Agent invocation SHALL be wrapped in `asyncio.wait_for()` with a configurable per-agent timeout (default 60 seconds); IF an agent exceeds its timeout, THEN THE Orchestrator SHALL treat the timeout as an unhandled exception, mark the result as `error`, and continue processing remaining agents.
9. THE Orchestrator SHALL use a configurable concurrency semaphore (default: 5 concurrent agents) to limit simultaneous agent executions; agents exceeding the concurrency limit SHALL queue and run when a slot becomes available.
10. WHEN all Agent results are collected, THE Orchestrator SHALL mark the Analysis Job status as `completed` and trigger Report generation.
11. EACH `BaseAgent` subclass SHALL declare a `dependencies: list[str]` class attribute listing the `name` values of agents that must complete before it runs; an empty list means the agent has no dependencies and runs immediately.
12. THE Orchestrator SHALL validate at startup that the declared Agent Dependency DAG contains no cycles; IF a cycle is detected, THE Backend SHALL exit with a non-zero status code and log the cycle.
13. THE default Agent Dependency DAG SHALL be: `repository_understanding` has no dependencies; `architecture`, `dependency`, `security` depend on `repository_understanding`; `code_quality` depends on `repository_understanding`; `technical_debt` depends on `code_quality`; `executive_cto` depends on all other Core Agents except `repository_optimization`; `repository_optimization` depends on `executive_cto`.

---

### Requirement 3: Core Agent Implementations

**User Story:** As a developer, I want detailed analysis from specialized agents so that I receive actionable insights across security, architecture, code quality, dependencies, and technical debt.

#### Acceptance Criteria

1. THE Repository Understanding Agent SHALL extract language distribution, file count, directory structure, commit history summary, contributor count, primary framework identification, README quality score, presence of LICENSE file, presence of CONTRIBUTING guide, presence of SECURITY.md, presence of CODEOWNERS, presence of issue templates, presence of PR templates, presence of GitHub Actions workflows, release history, semantic versioning compliance, and branch protection status (when accessible via the GitHub API) from the cloned repository; each of these metadata fields SHALL be a boolean or quality-score field in the `metrics` output.
2. THE Security Agent SHALL detect hardcoded secrets, known vulnerable dependency versions (CVE references), insecure coding patterns, and missing security headers; THE Security Agent SHALL assign a severity level (`critical`, `high`, `medium`, `low`) to each finding; each finding SHALL include `severity`, `owasp_category` (e.g., `A07:2021`), `cwe_id` (e.g., `CWE-798`), `exploitability` level, `fix_difficulty`, and `estimated_fix_minutes`.
3. THE Code Quality Agent SHALL compute cyclomatic complexity, code duplication percentage, comment coverage percentage, and naming convention compliance; THE Code Quality Agent SHALL produce per-file and aggregate scores.
4. THE Architecture Agent SHALL identify architectural patterns present in the repository (e.g., MVC, hexagonal, microservices), flag architectural anti-patterns with descriptions and file references, and generate architecture diagrams in Mermaid format — specifically: a component dependency diagram, a sequence diagram for the primary request flow, and a call graph for top-level entry points.
5. THE Dependency Agent SHALL list all direct and transitive dependencies, identify outdated packages, flag license incompatibilities, and report known CVEs using publicly available vulnerability data.
6. THE Technical Debt Agent SHALL estimate technical debt in hours, categorized by type (code smells, duplication, complexity, test coverage gaps), and produce a prioritized remediation list; THE Technical Debt Agent output SHALL include a `quick_wins_count` (estimated items fixable in under 2 hours), `major_refactors_count`, an overall `risk_level`, and a `roi_assessment` field.
7. THE Executive CTO Agent SHALL synthesize results from all other Core Agents into a concise executive summary including overall risk level, top 3 strategic recommendations, and a production readiness assessment.
8. WHERE a Stub Agent is invoked, THE Stub Agent SHALL return a well-formed `AgentOutputPayload` containing a `status: "stub"` field and an empty results array, without raising an error.

---

### Requirement 4: Scoring System

**User Story:** As a developer, I want quantified scores across multiple dimensions so that I can benchmark repository health and track improvements over time.

#### Acceptance Criteria

1. WHEN an Analysis Job completes, THE Platform SHALL compute the following scores as integers in the range 0–100: Repository Health, Architecture, Security, Performance, Testing, Documentation, Maintainability, Production Readiness, Technical Debt, and Overall Grade.
2. THE Overall Grade SHALL be derived as a weighted average of the other nine scores; THE Platform SHALL document the weighting formula in the OpenAPI schema.
3. THE Platform SHALL map each Overall Grade integer to a letter grade: 90–100 = A, 80–89 = B, 70–79 = C, 60–69 = D, 0–59 = F.
4. WHEN an Analysis Job completes, THE Platform SHALL compute an Optimization Score (0–100 integer) representing the overall actionability and improvement potential of the repository, derived from the Repository Optimization Engine results.
5. WHEN an Analysis Job completes, THE Platform SHALL compute an Engineering Maturity Score (0–100 integer) and map it to a maturity level: 0–24 = Beginner, 25–49 = Intermediate, 50–74 = Advanced, 75–100 = Enterprise.
6. THE Dashboard SHALL display Optimization Score and Engineering Maturity Score prominently above the nine dimension scores.
7. WHEN a repository is analyzed more than once, THE Frontend SHALL display a score trend chart showing score history over time using Recharts.
8. IF any individual score cannot be computed because the required agent returned an error, THEN THE Platform SHALL set that score to `null` and exclude it from the Overall Grade calculation rather than failing the entire job.

---

### Requirement 5: Knowledge Graph Generation

**User Story:** As a developer, I want a visual knowledge graph of my repository so that I can understand the relationships between code entities.

#### Acceptance Criteria

1. WHEN an Analysis Job completes, THE Platform SHALL generate Knowledge Graph nodes for each identified code entity (classes, functions, modules, packages, external dependencies).
2. THE Platform SHALL extend Knowledge Graph node entity types to include: `api_endpoint`, `environment_variable`, `docker_service`, `sql_table`, `http_endpoint`, `celery_task`, `react_component`, `route`, and `hook` — in addition to the five base types (classes, functions, modules, packages, external dependencies).
3. THE Platform SHALL generate Knowledge Graph edges representing relationships between nodes, including: `imports`, `inherits`, `calls`, `implements`, and `depends_on`.
4. THE Platform SHALL enqueue Titan Embeddings generation asynchronously after node records are written, processed by a dedicated Celery worker, and update the node record with the embedding upon completion; THE system SHALL NOT block report generation waiting for embedding completion.
5. THE Frontend SHALL render the Knowledge Graph as an interactive force-directed graph on the Knowledge Graph page.
6. WHEN a user selects a node in the Knowledge Graph, THE Frontend SHALL display a detail panel showing: node metadata, connected edges, AI-generated summary, inferred purpose, complexity score, connected components count, and optimization suggestions for that entity.

---

### Requirement 6: Report Generation and Export

**User Story:** As a developer, I want to download analysis reports in multiple formats so that I can share findings with my team.

#### Acceptance Criteria

1. WHEN an Analysis Job completes, THE Backend SHALL generate a Report in all four standard formats: HTML, PDF, Markdown, and JSON.
2. THE HTML Report SHALL include all scores, agent findings, recommendations, and score trend charts.
3. THE PDF Report SHALL be a print-ready rendering of the HTML Report with embedded charts.
4. THE JSON Report SHALL be a machine-readable document conforming to the published OpenAPI schema for the Report entity.
5. THE Backend SHALL generate a fifth report type, the Optimization Report, structured as: Executive Summary → Optimization Score → Priority Matrix → Quick Wins → Architecture Findings → Security Findings → Technical Debt → Appendix; THE Optimization Report SHALL be generated in both HTML and PDF formats and available as a separate download alongside the four standard report formats.
6. WHEN a user requests a Report via the REST API, THE Backend SHALL return a pre-signed download URL valid for 1 hour.
7. THE Backend SHALL retain Report files for a minimum of 30 days after Analysis Job completion.

---

### Requirement 7: REST API

**User Story:** As a developer, I want a versioned, documented REST API so that I can integrate RepoGenius AI into my own tools and workflows.

#### Acceptance Criteria

1. THE Backend SHALL expose all public endpoints under the `/api/v1/` path prefix.
2. THE Backend SHALL serve an OpenAPI 3.1 specification and interactive Swagger UI at `/api/v1/docs`.
3. THE Backend SHALL enforce rate limiting on all API endpoints; unauthenticated requests SHALL be limited to 10 requests per minute per IP address; authenticated requests SHALL be limited to 120 requests per minute per user.
4. THE Backend SHALL support pagination on all list endpoints using `page` and `page_size` query parameters with a maximum `page_size` of 100.
5. THE Backend SHALL support filtering and sorting on list endpoints via query parameters documented in the OpenAPI specification.
6. WHEN a request body fails schema validation, THE Backend SHALL return HTTP 422 with a structured error response body that includes the field name and violation message for each failing field.
7. THE Backend SHALL return HTTP 401 for requests to protected endpoints that lack a valid JWT or API Key.
8. THE Backend SHALL return HTTP 403 for requests where the authenticated user lacks the RBAC permission required by the endpoint.

---

### Requirement 8: WebSocket Progress Updates

**User Story:** As a developer, I want real-time progress updates during long-running analysis jobs so that I know the Platform is working and can monitor completion.

#### Acceptance Criteria

1. THE Backend SHALL expose a WebSocket endpoint at `/ws/jobs/{job_id}` for clients to subscribe to progress events for a specific Analysis Job.
2. WHEN a client connects to the WebSocket endpoint, THE Backend SHALL immediately emit the current job status and last known progress percentage.
3. WHEN job progress changes, THE Backend SHALL emit a WebSocket event containing: `job_id`, `status`, `progress_percentage` (0–100), `current_step`, and `timestamp`.
4. WHEN an Analysis Job reaches a terminal state (`completed` or `failed`), THE Backend SHALL emit a final WebSocket event and close the connection cleanly.
5. IF a WebSocket client disconnects and reconnects within 60 seconds, THEN THE Backend SHALL replay all missed events for that job since the disconnection.

---

### Requirement 9: Authentication and Authorization

**User Story:** As a user, I want secure login via GitHub OAuth so that my repositories and reports are protected.

#### Acceptance Criteria

1. THE Platform SHALL support GitHub OAuth 2.0 as the sole interactive authentication method; WHEN a user completes the GitHub OAuth flow, THE Backend SHALL create or update the user record and issue a signed JWT.
2. THE Backend SHALL support JWT-based session authentication; issued JWTs SHALL have an expiry of 24 hours.
3. THE Backend SHALL support API Key authentication for programmatic access; API Keys SHALL be stored as bcrypt hashes in the database.
4. THE Backend SHALL implement RBAC with at minimum the following roles: `admin`, `analyst`, and `viewer`; THE Backend SHALL enforce role permissions on every protected endpoint.
5. WHEN a user logs out, THE Backend SHALL invalidate the user's current JWT by adding it to a Redis-backed denylist until the token's original expiry time.
6. THE Backend SHALL record every authentication event (login, logout, token refresh, API key usage) in the Audit Log with user ID, timestamp, IP address, and outcome.
7. IF a JWT is expired or present on the denylist, THEN THE Backend SHALL return HTTP 401 and SHALL NOT process the request.

---

### Requirement 10: Security and Data Protection

**User Story:** As a user, I want my credentials and repository data protected so that sensitive information is not exposed.

#### Acceptance Criteria

1. THE Platform SHALL NEVER store raw OAuth tokens or user passwords in plaintext; OAuth tokens SHALL be encrypted at rest using AES-256.
2. THE Platform SHALL NEVER modify any file in a user's original repository; all analysis operations SHALL be performed on read-only copies or isolated workspaces.
3. THE Backend SHALL delete the cloned repository workspace from disk within 1 hour of Analysis Job completion or failure.
4. THE Backend SHALL validate and sanitize all user-supplied inputs, including repository URLs, before passing them to GitPython or any shell invocation.
5. THE Backend SHALL validate that repository URLs match the permitted allowlist (`https://github.com/*`, `https://gitlab.com/*`, `https://bitbucket.org/*`) and SHALL reject `file://`, `ssh://`, local paths, and git hook execution before any cloning operation.
6. THE Backend SHALL include security headers (`Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`) in all HTTP responses via NGINX configuration.
7. WHEN a secret or credential is detected in repository source code by the Security Agent, THE Platform SHALL redact the secret value in all stored reports and display only the file path and line number.
8. THE Backend SHALL cache AI provider responses keyed by `hash(repo_content) + agent_name + prompt_hash` in Redis with a configurable TTL (default 24 hours); a cache hit SHALL skip provider invocation and return the cached response directly.

---

### Requirement 11: AI Provider Management

**User Story:** As a platform operator, I want a resilient AI backend that automatically falls back to alternative providers so that analysis continues even when the primary provider is unavailable.

#### Acceptance Criteria

1. THE Backend SHALL load AI provider priority order from configuration (environment variable `AI_PROVIDER_ORDER`, default: `["ollama", "claude", "bedrock"]`); THE primary provider SHALL be the first entry in the configured list; THE Backend SHALL attempt providers in the configured order for all agent inference requests.
2. IF a request to the configured primary provider fails or times out after 30 seconds, THEN THE Backend SHALL retry the request once against the configured secondary provider.
3. IF the configured secondary provider request also fails or times out after 30 seconds, THEN THE Backend SHALL retry the request against the configured tertiary provider.
4. IF all configured AI providers fail for a given agent invocation, THEN THE Backend SHALL mark that agent's result as `error` and continue with remaining agents.
5. THE Backend SHALL implement an `AIManager` abstraction layer with sub-components: `PromptBuilder`, `ProviderRouter`, `ResponseParser`, `ResponseCache`, and `InvocationLogger`; all agent AI calls SHALL go through `AIManager`.
6. THE Backend SHALL log each AI provider invocation with provider name, model name, latency in milliseconds, token counts, and outcome (success or failure).
7. THE Backend SHALL use Titan Embeddings exclusively for generating Knowledge Graph node vector embeddings via AWS Bedrock.
8. THE `ResponseParser` SHALL validate every AI provider response against the expected output schema for the invoking agent before returning it to the agent; IF validation fails, THE `AIManager` SHALL attempt one repair invocation (re-invoking the same provider with the original prompt plus a structured correction instruction); IF the repair invocation also fails validation, THE `AIManager` SHALL mark the invocation as `error` and return an error response to the agent.
9. THE `ResponseParser` SHALL use Pydantic model validation for structured outputs and a regex/JSON schema check for unstructured outputs.

---

### Requirement 12: Frontend Application

**User Story:** As a user, I want a comprehensive web dashboard so that I can manage repositories, view reports, and explore analysis results without using the API directly.

#### Acceptance Criteria

1. THE Frontend SHALL implement the following pages: Dashboard, Repository Analysis, Reports, Knowledge Graph, Agents, Settings, Profile, and Admin.
2. THE Frontend SHALL use React Query for all server state fetching and caching; THE Frontend SHALL display loading indicators while data is being fetched.
3. THE Frontend SHALL use Zustand for client-side global state management (e.g., authenticated user, active job, notification queue).
4. THE Frontend SHALL use ShadCN components built on TailwindCSS for all UI elements, maintaining a consistent design system.
5. THE Dashboard SHALL display Optimization Score, Repository Grade, Repository Health, and Engineering Maturity Score as the primary hero metrics, followed by the nine dimension scores as secondary metrics.
6. THE Frontend SHALL establish a WebSocket connection for any active Analysis Job and render real-time progress in a status panel.
7. THE Frontend SHALL be fully responsive and usable on viewports from 375px (mobile) to 1920px (desktop) width.
8. WHEN the user's JWT expires while the Frontend is active, THE Frontend SHALL automatically redirect the user to the login page and display an explanatory message.
9. THE Frontend SHALL support dark mode and light mode themes, togglable from the Settings page, with the preference persisted to localStorage.
10. THE Frontend SHALL provide a search interface on the Repository Analysis page allowing full-text search across all findings from a completed Analysis Job.
11. THE Frontend SHALL display a comparison view allowing two Analysis Jobs for the same repository to be shown side-by-side with score delta indicators.

---

### Requirement 13: Database Schema and Migrations

**User Story:** As a developer, I want a well-structured database schema managed by migrations so that the data model is maintainable and evolvable.

#### Acceptance Criteria

1. THE Backend SHALL use SQLAlchemy ORM models for all 12 database entities: Users, Organizations, Repositories, Analysis Jobs, Agent Results, Reports, Recommendations, Knowledge Graph Nodes, Knowledge Graph Edges, Audit Logs, Notifications, and API Keys; the `analysis_jobs` entity SHALL include `optimization_score` (integer, nullable) and `engineering_maturity_score` (integer, nullable) columns; the `recommendations` entity SHALL include fields: `title`, `description`, `severity`, `difficulty`, `estimated_hours` (float), `impact`, `roi`, `category`, `affected_files` (JSON array), `related_agent`, `confidence` (float 0–1), `references` (JSON array), and `suggested_sprint` (integer, nullable); the `audit_logs` entity SHALL include: `user_agent`, `request_id`, `endpoint`, `latency_ms`, and `session_id`.
2. THE Backend SHALL manage all schema changes via Alembic migration scripts; no schema changes SHALL be applied outside of Alembic migrations.
3. THE Backend SHALL define foreign key constraints and appropriate indexes on all entities to support the query patterns required by the REST API list endpoints.
4. WHEN the Backend starts, THE Backend SHALL verify database connectivity and that all Alembic migrations are applied before accepting HTTP requests; IF verification fails, THEN THE Backend SHALL exit with a non-zero status code and log the error.

---

### Requirement 14: Infrastructure and Deployment

**User Story:** As a platform operator, I want a containerized deployment so that the Platform can be run consistently across local development and production environments.

#### Acceptance Criteria

1. THE Platform SHALL provide a `docker-compose.yml` file that defines services for: Backend, Frontend, PostgreSQL, Redis, Celery worker, and NGINX.
2. THE Platform SHALL provide a `docker-compose.override.yml` for local development that mounts source code as volumes and enables hot-reload for both Backend and Frontend.
3. WHEN `docker compose up` is executed, THE Platform SHALL be fully operational within 3 minutes on a machine with a stable internet connection and Docker Desktop installed.
4. THE Platform SHALL provide a GitHub Actions CI workflow that runs linting, unit tests, and integration tests on every push to the main branch and every pull request.
5. THE NGINX service SHALL terminate TLS, serve Frontend static assets, and reverse-proxy API and WebSocket requests to the Backend.
6. THE Platform SHALL use environment variables for all secrets and environment-specific configuration; no secrets SHALL be hardcoded in any source file or Docker image.

---

### Requirement 15: Extensibility and Plugin Architecture

**User Story:** As a platform architect, I want a plugin-based agent system so that new agents can be added without modifying existing orchestration code.

#### Acceptance Criteria

1. THE Platform SHALL implement a plugin registry that discovers and registers Agent classes at startup by scanning a designated agents package directory.
2. WHEN a new Agent class is added to the agents package directory and inherits from `BaseAgent`, THE Platform SHALL register and invoke it in subsequent Analysis Jobs without requiring changes to Orchestrator code.
3. THE Platform SHALL define a complete `AgentInputPayload` and `AgentOutputPayload` Pydantic schema for all 25+ agents, including all Stub Agents, so that future implementations can be dropped in without schema changes.
4. THE Platform architecture SHALL be designed to support future extension points including: Code Translation engine, PR Review, VS Code extension API, GitHub App webhook integration, GitLab and Bitbucket repository support, MCP Server interface, and a Plugin Marketplace — without requiring breaking changes to the core Orchestrator or BaseAgent contract.

---

### Requirement 16: Repository Optimization Engine

**User Story:** As a developer, I want the platform to prioritize repository improvements so that I know exactly what to fix first and can plan work in meaningful sprints.

#### Acceptance Criteria

1. WHEN all Core Agents complete, THE Repository Optimization Agent SHALL merge all findings from every Core Agent into a unified finding set, eliminate duplicate findings by content similarity, and assign each finding a Priority of `critical`, `high`, `medium`, or `low`.
2. THE Repository Optimization Agent SHALL estimate for each finding: developer hours required, fix difficulty (`trivial`, `easy`, `medium`, `hard`, `complex`), business impact (`low`, `medium`, `high`, `critical`), engineering impact (`low`, `medium`, `high`, `critical`), and ROI score (0–10 float).
3. THE Repository Optimization Agent SHALL generate an Optimization Roadmap partitioning findings into sprints: Sprint 1 (Quick Wins — items with ROI ≥ 7 and difficulty ≤ `easy`), Sprint 2 (Security and Critical), Sprint 3 (Architecture), Sprint 4 (Performance and Debt).
4. THE Repository Optimization Agent SHALL produce a Quick Wins list of the top 10 findings with the highest ROI that can each be resolved in under 2 developer hours.
5. THE Repository Optimization Agent SHALL calculate the Optimization Score (0–100 integer) as a weighted function of: critical findings count (−5 each, max −50), high findings count (−2 each, max −20), and quick wins resolved (baseline 70, +3 each up to 100).
6. THE Repository Optimization Agent SHALL run after all other Core Agents complete; THE Orchestrator SHALL dispatch the Repository Optimization Agent as the final sequential step and SHALL NOT dispatch it as a concurrent task alongside other Core Agents.
7. WHEN the Repository Optimization Agent completes, THE Backend SHALL persist its output as an Agent Result and include the Optimization Roadmap in the Optimization Report.

---

### Requirement 17: Repository Analysis History and Trends

**User Story:** As a developer, I want to track repository changes over time so that I can demonstrate improvements to engineering leadership.

#### Acceptance Criteria

1. WHEN a repository is analyzed more than once, THE Platform SHALL store each Analysis Job's complete ScoreSet, Optimization Score, and Engineering Maturity Score as a historical record linked to the repository.
2. THE Frontend SHALL display a Repository Timeline chart showing: score history over time, Optimization Score trend, Architecture maturity change, and Technical Debt trend — all rendered using Recharts on the Repository Analysis page.
3. THE Frontend SHALL allow comparison of any two Analysis Jobs for the same repository, showing score deltas (positive or negative) for all eleven scores side-by-side.
4. THE Backend REST API SHALL expose a `GET /api/v1/repos/{repo_id}/history` endpoint returning paginated historical Analysis Job summaries with scores for each job.

---

### Requirement 18: Shared Analysis Context

**User Story:** As a platform engineer, I want all agents to share a pre-built analysis of the repository so that no agent re-parses files independently.

#### Acceptance Criteria

1. BEFORE the Orchestrator dispatches any agents, THE Backend SHALL build a `SharedAnalysisContext` by parsing the cloned repository exactly once; THE `SharedAnalysisContext` SHALL contain: AST cache (per language), Symbol Table, Dependency Graph, File Index (path → language mapping), Language Map, Git Metadata (commit SHA, branch, tags, contributors), and Framework Detection results.
2. THE Orchestrator SHALL inject the `SharedAnalysisContext` into every `AgentInputPayload` via the `metadata` field before dispatching agents.
3. NO agent SHALL independently clone, re-parse, or re-build any data already available in the `SharedAnalysisContext`; agents SHALL read exclusively from the injected context for file-level data.
4. THE `SharedAnalysisContext` build step SHALL complete within 60 seconds for repositories under the 2 GB / 500k file limits; IF the build step fails, THE Orchestrator SHALL abort the Analysis Job and mark it `failed`.
5. THE `SharedAnalysisContext` SHALL support the following language parsers: Python, JavaScript, TypeScript, Java, Go, Rust, C#, C++, PHP, Ruby, Kotlin, Swift; IF a repository contains files in an unsupported language, THE parser SHALL include those files in the file index with `language: "unsupported"` but SHALL NOT attempt AST generation for them.
6. IF AST parsing fails for a specific file due to syntax errors, THEN THE `SharedAnalysisContext` SHALL include that file in the file index with `parse_error: true` and SHALL NOT include it in the AST cache; the failure SHALL NOT prevent context construction from completing.

---

### Requirement 19: GitHub API Rate Limit Management

**User Story:** As a platform engineer, I want all GitHub API calls to respect rate limits automatically so that analysis jobs do not fail due to API exhaustion.

#### Acceptance Criteria

1. THE Backend SHALL implement a `GitHubService` that wraps all GitHub API calls (repository metadata, branch protection, PR templates, Actions workflows, etc.) with a `RateLimitManager`.
2. THE `RateLimitManager` SHALL inspect GitHub API response headers (`X-RateLimit-Remaining`, `X-RateLimit-Reset`) after every call and track remaining quota.
3. IF the remaining quota falls below 50 requests, THE `RateLimitManager` SHALL pause further GitHub API calls until the reset timestamp, then resume.
4. THE `GitHubService` SHALL implement conditional requests using `ETag` headers to avoid consuming quota for unchanged resources.
5. THE `GitHubService` SHALL implement exponential backoff with jitter on HTTP 429 and HTTP 403 rate-limit responses, retrying up to 3 times before marking the affected metadata field as unavailable (not failing the entire analysis).
6. ALL GitHub API calls across all agents and services SHALL go exclusively through `GitHubService`; no component SHALL make direct `requests` or `httpx` calls to `api.github.com`.

---

### Requirement 20: Clean Architecture Layer Separation

**User Story:** As a backend engineer, I want the codebase organized into distinct architectural layers so that business logic is never coupled to framework or infrastructure concerns.

#### Acceptance Criteria

1. THE Backend SHALL be organized into four layers: `Presentation` (FastAPI routes, request/response schemas, WebSocket handlers), `Application` (use case orchestration, service classes, event bus), `Domain` (entities, value objects, domain events, repository interfaces), `Infrastructure` (SQLAlchemy implementations, Redis adapters, Celery workers, external API clients).
2. THE `Presentation` layer SHALL depend only on the `Application` layer; THE `Application` layer SHALL depend only on the `Domain` layer; THE `Domain` layer SHALL have NO dependencies on `Presentation`, `Application`, or `Infrastructure`; THE `Infrastructure` layer SHALL implement interfaces defined in `Domain`.
3. ALL business logic SHALL reside in the `Domain` or `Application` layers; NO business logic SHALL be placed directly inside FastAPI route handlers or SQLAlchemy model methods.
4. THE Backend SHALL implement the Repository Pattern: a dedicated repository class (e.g., `AnalysisJobRepository`, `UserRepository`, `RecommendationRepository`) SHALL mediate all database access for each entity; service classes SHALL never import SQLAlchemy session objects directly.
5. THE Backend SHALL implement Unit of Work: a `UnitOfWork` context manager SHALL group related repository writes into a single atomic transaction; agents writing results simultaneously SHALL each use a separate `UnitOfWork` instance scoped to their result record.

---

### Requirement 21: Internal Event Bus

**User Story:** As a platform engineer, I want agent completions and system events to be published to an event bus so that new subscribers (metrics, notifications, audit) can be added without modifying the Orchestrator.

#### Acceptance Criteria

1. THE Backend SHALL implement an in-process `EventBus` with `publish(event: DomainEvent)` and `subscribe(event_type, handler)` interfaces.
2. WHEN an Agent completes (any status), THE Orchestrator SHALL publish an `AgentCompletedEvent` to the `EventBus` containing: `job_id`, `agent_name`, `status`, `duration_ms`, `finding_count`.
3. WHEN an Analysis Job reaches `completed` or `failed` status, THE Orchestrator SHALL publish a `JobCompletedEvent` or `JobFailedEvent` to the `EventBus`.
4. THE following components SHALL subscribe to relevant events via the `EventBus` rather than being called directly by the Orchestrator: WebSocket manager (on `AgentCompletedEvent`, `JobCompletedEvent`), Audit logger (on all events), Metrics collector (on all events), Notification service (on `JobCompletedEvent`, `JobFailedEvent`), Report trigger (on `JobCompletedEvent`).
5. THE `EventBus` SHALL be synchronous and in-process for V1; subscribers SHALL be called sequentially in subscription order; any subscriber exception SHALL be caught, logged, and NOT propagate to the Orchestrator.

---

### Requirement 22: Feature Flags

**User Story:** As a platform operator, I want to toggle platform capabilities via environment variables so that I can disable features without redeploying code.

#### Acceptance Criteria

1. THE Backend SHALL implement a `FeatureFlags` component within `ConfigRegistry` that reads the following boolean environment variables at startup: `ENABLE_KG` (default true), `ENABLE_OPTIMIZATION` (default true), `ENABLE_REPORTS` (default true), `ENABLE_EMBEDDINGS` (default true), `ENABLE_EXECUTIVE_CTO` (default true), `ENABLE_GITHUB_METADATA` (default true).
2. WHEN `ENABLE_KG` is false, THE Backend SHALL skip Knowledge Graph node and edge generation entirely for all Analysis Jobs.
3. WHEN `ENABLE_OPTIMIZATION` is false, THE Backend SHALL skip the Repository Optimization Agent for all Analysis Jobs and omit Optimization Score computation.
4. WHEN `ENABLE_EMBEDDINGS` is false, THE Backend SHALL skip Titan Embeddings enqueue for all KG nodes.
5. WHEN `ENABLE_EXECUTIVE_CTO` is false, THE Backend SHALL skip the Executive CTO Agent and omit its score dimension from the Overall Grade.
6. WHEN `ENABLE_GITHUB_METADATA` is false, THE Repository Understanding Agent SHALL skip all GitHub API metadata calls and return `null` for all GitHub metadata fields without failing.

---

### Requirement 23: LLM Cost Tracking

**User Story:** As a platform operator, I want every AI provider invocation's cost persisted so that I can analyze spend by job, agent, provider, and time period.

#### Acceptance Criteria

1. THE Backend SHALL persist a `ai_invocation_logs` database record for every AI provider call, including: `job_id`, `agent_name`, `provider`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `estimated_cost_usd` (float), `cached` (boolean), `created_at`.
2. THE `estimated_cost_usd` SHALL be computed using configurable per-provider, per-model token pricing constants loaded from `ConfigRegistry`.
3. THE REST API SHALL expose `GET /api/v1/admin/cost-report` (admin only) returning aggregated cost data grouped by: `provider`, `agent`, `model`, and `created_at` date.
4. IF an AI invocation was served from the `ResponseCache` (cache hit), THE `ai_invocation_logs` record SHALL set `cached = true` and `estimated_cost_usd = 0.0`.

---

### Requirement 24: Prompt Registry and Versioning

**User Story:** As an AI engineer, I want all prompts stored in a versioned registry so that prompt changes are traceable and reports are reproducible.

#### Acceptance Criteria

1. THE Backend SHALL maintain a `prompt_registry` database table with columns: `id` (UUID), `prompt_name`, `version` (integer), `content` (text), `checksum` (SHA-256 of content), `author`, `created_at`, `is_active` (boolean).
2. EACH agent SHALL reference a `prompt_name` and `prompt_version` rather than embedding prompt text directly in source code; THE `PromptBuilder` SHALL resolve the active prompt version from the registry at runtime.
3. WHEN a prompt is updated, a NEW record SHALL be inserted with an incremented `version`; the previous record SHALL remain in the table for reproducibility; only the record with `is_active = true` for a given `prompt_name` SHALL be used for new invocations.
4. EACH `ai_invocation_logs` record SHALL store the `prompt_name` and `prompt_version` used for that invocation.

---

### Requirement 25: Central Configuration Registry

**User Story:** As a backend engineer, I want all configuration accessed through a single typed registry so that configuration is never scattered across the codebase.

#### Acceptance Criteria

1. THE Backend SHALL implement a `ConfigRegistry` singleton (backed by Pydantic `BaseSettings`) that is the ONLY place where environment variables are read; all services, agents, and workers SHALL access configuration exclusively via `ConfigRegistry`.
2. THE `ConfigRegistry` SHALL expose typed, named accessors for all configuration groups: AI provider settings, feature flags, timeouts, retry policies, rate limits, agent concurrency, report settings, and database settings.
3. THE Backend SHALL validate the full `ConfigRegistry` on startup and exit with a non-zero status code and a descriptive error message if any required configuration value is missing or invalid.
4. THE `ConfigRegistry` SHALL provide a `get_agent_timeout(agent_name: str) -> int` method that returns a per-agent timeout in seconds; agents not listed in the per-agent override use the global default.

---

### Requirement 26: Job Lifecycle Management

**User Story:** As a developer, I want to cancel, retry, pause, and resume analysis jobs so that I have full control over long-running operations.

#### Acceptance Criteria

1. THE Analysis Job status state machine SHALL support the following states: `pending`, `queued`, `cloning`, `cloned`, `running`, `completed`, `failed`, `cancel_requested`, `cancelled`, `retrying`, `paused`, `cached`.
2. THE Backend SHALL expose `POST /api/v1/jobs/{job_id}/cancel` (analyst+); WHEN called on a job in state `queued`, `cloning`, or `running`, THE Backend SHALL set status to `cancel_requested`; THE Celery worker SHALL honour the request and transition to `cancelled` within 30 seconds.
3. THE Backend SHALL expose `POST /api/v1/jobs/{job_id}/retry` (analyst+); WHEN called on a `failed` or `cancelled` job, THE Backend SHALL create a new Analysis Job for the same repository and return the new job ID.
4. THE Backend SHALL expose `POST /api/v1/jobs/{job_id}/pause` and `POST /api/v1/jobs/{job_id}/resume` (analyst+); pausing a `running` job SHALL suspend agent dispatch; resuming SHALL continue from the last completed agent wave.
5. WHEN a job transitions to any terminal state (`completed`, `failed`, `cancelled`, `cached`), THE Backend SHALL publish a `JobTerminalEvent` to the EventBus containing the final status and reason.

---

### Requirement 27: Repository Cache Specification

**User Story:** As a platform engineer, I want repository analysis results cached by content hash so that unchanged repositories reuse prior work without re-cloning or re-running agents.

#### Acceptance Criteria

1. THE cache key for any cached Analysis Job artifact SHALL be the composite of: `repo_url`, `branch`, `commit_sha`, `analysis_version` (platform version string), and `prompt_version` (active prompt checksum for all agents).
2. THE following artifacts SHALL be eligible for cache reuse when all cache key fields match: cloned workspace (via symlink), SharedAnalysisContext (AST, symbol table, dependency graph), KG nodes and edges, agent results, Optimization Score, Engineering Maturity Score, and generated reports.
3. THE Platform SHALL invalidate a cached entry when any of the following change: `commit_sha` (new commit on the branch), `analysis_version` (platform upgrade), or `prompt_version` (any active agent prompt updated).
4. WHEN a cache hit is detected, THE Backend SHALL complete the new Analysis Job within 2 seconds, set `cache_hit=true` on the job record, emit a WebSocket `cached` event, and skip all cloning, parsing, and agent dispatch.
5. THE `repository_caches` table SHALL store: `id`, `repo_url`, `branch`, `commit_sha`, `analysis_version`, `prompt_versions_hash`, `job_id` (FK to cached job), `clone_path`, `size_bytes`, `last_used_at`, `created_at`.

---

### Requirement 28: Worker Specialization

**User Story:** As a platform operator, I want analysis work distributed across specialized Celery queues so that different workloads scale independently.

#### Acceptance Criteria

1. THE Platform SHALL define the following Celery queues and associated worker pools: `clone` (CloneWorker), `parse` (ParseWorker — runs SharedAnalysisContextBuilder), `ai` (AIWorker — runs all agent AI inference), `kg` (KGWorker — runs KG extraction), `embed` (EmbeddingWorker — runs Titan Embeddings), `report` (ReportWorker — generates all report formats), `cleanup` (CleanupWorker — workspace and file cleanup).
2. EACH Celery task SHALL be routed to its designated queue via task routing configuration; tasks MUST NOT be placed on the default queue.
3. THE `docker-compose.yml` SHALL define one `celery_worker` service per queue with the appropriate `--queues` flag; the dev `docker-compose.override.yml` MAY combine all queues into a single worker for simplicity.

---

### Requirement 29: Health and Observability Endpoints

**User Story:** As a platform operator, I want health and metrics endpoints so that I can monitor the platform and integrate it with standard infrastructure tooling.

#### Acceptance Criteria

1. THE Backend SHALL expose `GET /health` returning HTTP 200 with a JSON body containing the status of all subsystems: `database` (connected/disconnected), `redis` (connected/disconnected), `celery` (worker count and queue depths per queue), and `github_api` (remaining quota).
2. THE Backend SHALL expose `GET /ready` returning HTTP 200 when the Backend is ready to accept requests (DB connected, migrations applied) and HTTP 503 otherwise.
3. THE Backend SHALL expose `GET /live` returning HTTP 200 as a simple liveness check.
4. THE Backend SHALL expose `GET /metrics` returning Prometheus-format text with the following metrics: `repogenius_active_jobs`, `repogenius_queue_depth{queue}`, `repogenius_agent_duration_seconds{agent}`, `repogenius_ai_cost_usd_total{provider}`, `repogenius_cache_hit_ratio`, `repogenius_analysis_duration_seconds`.
5. ALL structured log entries SHALL include the following fields: `job_id`, `agent`, `request_id`, `trace_id`, `correlation_id`, `duration_ms`, `provider`, `status`, `level`, `message`, `timestamp`.

---

### Requirement 30: Explicit Performance SLAs

**User Story:** As a platform engineer, I want documented performance targets so that I can detect regressions and plan capacity.

#### Acceptance Criteria

1. THE Backend SHALL target the following p95 latency SLAs for an average repository (under 500 MB, under 100k files): repository clone ≤ 60 seconds, SharedAnalysisContext build ≤ 60 seconds, each individual agent execution ≤ 60 seconds, Knowledge Graph generation ≤ 90 seconds, all report formats generated ≤ 30 seconds, total end-to-end Analysis Job ≤ 10 minutes.
2. THE Backend SHALL log a warning-level structured log entry whenever any individual operation exceeds its SLA target.
3. THE `GET /metrics` endpoint SHALL expose a Prometheus histogram `repogenius_operation_duration_seconds{operation}` for each SLA-tracked operation so that p95 latency can be queried in real time.

---

### Requirement 31: Expanded Static Analysis Metrics

**User Story:** As a developer, I want richer code quality and architecture metrics so that I receive more actionable insights about maintainability and structural health.

#### Acceptance Criteria

1. THE Code Quality Agent SHALL additionally compute and include in its output: Maintainability Index (per-file and aggregate, 0–100), Cognitive Complexity (per-function and aggregate), Dead Code percentage (unreachable functions/classes), Unused Imports count, Unused Variables count, Long Methods count (functions exceeding 50 lines), Large Classes count (classes exceeding 300 lines), Magic Numbers count.
2. THE Architecture Agent SHALL additionally detect and report: God Classes (classes with > 20 methods or > 500 lines), Circular Dependencies between modules, Layer Violations (calls that cross architectural boundaries in the wrong direction), Fan-In (number of modules that import a given module), Fan-Out (number of modules a given module imports), Instability Index (Fan-Out / (Fan-In + Fan-Out)), Afferent Coupling, Efferent Coupling.
3. THE Technical Debt Agent SHALL additionally estimate: cost in USD (using configurable developer hourly rate from ConfigRegistry), Priority Score (0–10 composite of ROI and risk), Interest Rate (debt growth rate as % per sprint), and Debt Category (design debt, code debt, test debt, documentation debt).

---

### Requirement 32: Repository Cross-Reference Index

**User Story:** As a developer, I want a cross-reference index of the repository so that I can understand where every symbol is defined, referenced, and imported.

#### Acceptance Criteria

1. THE `SharedAnalysisContextBuilder` SHALL build a `CrossReferenceIndex` as part of the `SharedAnalysisContext`; the index SHALL map each symbol to: `defined_in` (file path and line number), `referenced_by` (list of file paths + line numbers), `imported_by` (list of file paths), `calls` (list of symbols this symbol invokes), `called_by` (list of symbols that invoke this symbol).
2. THE `CrossReferenceIndex` SHALL cover: functions, classes, methods, constants, exported variables, HTTP routes, React components, React hooks, and Celery tasks — for all supported languages.
3. THE `CrossReferenceIndex` SHALL be stored as part of the `SharedAnalysisContext` and injected into every agent; agents MUST read cross-reference data from the injected index and SHALL NOT re-build it independently.
4. THE Knowledge Graph service SHALL use the `CrossReferenceIndex` to populate `calls`, `called_by`, `imports`, and `depends_on` edges rather than re-parsing source files.

---

### Requirement 33: Additional Frontend Pages

**User Story:** As a developer, I want dedicated pages for job queue management, system health, cost tracking, and notification management so that I can operate the platform without needing CLI access.

#### Acceptance Criteria

1. THE Frontend SHALL implement the following additional pages: Analysis Queue, Notifications, API Keys, Cost Dashboard, and System Health.
2. THE Analysis Queue page SHALL display all active and pending Analysis Jobs with status, repository, progress percentage, and action buttons (Cancel, Retry, Pause/Resume).
3. THE Cost Dashboard page SHALL display: Provider Cost breakdown (bar chart), Agent Cost breakdown, Cache Hit %, Money Saved (Recharts), Daily Spend trend, Monthly Spend trend, Average Job Cost — fetched from `GET /api/v1/admin/cost-report`.
4. THE System Health page SHALL display the status of all subsystems (database, Redis, Celery queues with depth, GitHub API quota) fetched from `GET /health`; a refresh button SHALL re-poll the endpoint.
5. THE Notifications page SHALL list all notifications for the authenticated user with mark-as-read and clear-all actions.
6. THE API Keys page SHALL provide a dedicated interface for: creating new API keys (name + expiry), listing existing keys (name, last_used_at, created_at), and revoking individual keys.

---

### Requirement 34: Additional DB Tables and Discovery APIs

**User Story:** As a platform operator, I want dedicated metrics tables and provider discovery endpoints so that I can monitor performance and introspect the platform's AI configuration.

#### Acceptance Criteria

1. THE Backend SHALL maintain an `ai_models` table with columns: `id` (UUID), `provider`, `model_name`, `context_window` (int), `input_price_per_1k_tokens` (float), `output_price_per_1k_tokens` (float), `status` (`active`/`deprecated`), `updated_at`; `ConfigRegistry` SHALL load pricing from this table at startup.
2. THE Backend SHALL maintain a `job_metrics` table with columns: `id`, `job_id` (FK), `clone_duration_ms`, `parse_duration_ms`, `kg_duration_ms`, `report_duration_ms`, `total_duration_ms`, `peak_memory_mb`, `total_tokens`, `total_cost_usd`, `cache_hit_count`, `agent_error_count`, `created_at`.
3. THE Backend SHALL maintain an `agent_metrics` table with columns: `id`, `job_id` (FK), `agent_name`, `execution_time_ms`, `cache_hits`, `retry_count`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `status`, `created_at`.
4. THE Backend SHALL expose `GET /api/v1/agents` returning a list of all registered agents with their name, version, dependencies, and last-run status.
5. THE Backend SHALL expose `GET /api/v1/providers` returning the current AI provider configuration: provider names in order, active models per provider, and rate limit status.
6. THE Backend SHALL expose `GET /api/v1/system/status` returning platform version, uptime, active job count, queue depths, and feature flag state.

---

### Requirement 35: Analysis Versioning

**User Story:** As a platform engineer, I want every Analysis Job to record the exact versions of the analysis engine, agent bundle, and schema in use so that historical comparisons and cache invalidation are reliable.

#### Acceptance Criteria

1. THE `analysis_jobs` table SHALL include three additional version fields: `analysis_version` (platform release string, e.g., `"1.0.0"`), `agent_bundle_version` (a hash or semver tag representing the collective set of registered agent versions at dispatch time), and `schema_version` (the Alembic migration head revision at job creation time).
2. WHEN an Analysis Job is created, THE Backend SHALL populate `analysis_version`, `agent_bundle_version`, and `schema_version` from `ConfigRegistry` before persisting the record.
3. THE repository cache invalidation logic SHALL compare the `analysis_version` and `agent_bundle_version` of a candidate cached job against the current runtime values; IF either differs, THE cache entry SHALL be considered stale and SHALL NOT be reused.
4. THE `GET /api/v1/jobs/{job_id}` response SHALL include `analysis_version`, `agent_bundle_version`, and `schema_version` so that API consumers can detect when a job was produced by a different engine version.

---

### Requirement 36: Agent Version Tracking

**User Story:** As an AI engineer, I want every agent result to record the agent version, prompt version, model, and provider used so that I can reproduce any analysis exactly.

#### Acceptance Criteria

1. THE `agent_results` table SHALL include additional columns: `agent_version` (the `version` string declared on the `BaseAgent` subclass), `prompt_name` (the active prompt name used), `prompt_version` (the active prompt version integer), `model` (the AI model name used), and `provider` (the AI provider name used).
2. WHEN an Agent Result is persisted, THE Orchestrator SHALL populate all five new fields from the agent's class declaration and the `AIManager.InvocationLogger`'s last invocation record for that agent.
3. THE `GET /api/v1/jobs/{job_id}/results` response SHALL include `agent_version`, `prompt_version`, `model`, and `provider` for each agent result record so that callers can audit exactly which agent and prompt version produced each finding.

---

### Requirement 37: Partial Completion State

**User Story:** As a developer, I want to distinguish a fully successful analysis from one that completed with some agent failures so that reports accurately reflect confidence level.

#### Acceptance Criteria

1. THE Analysis Job status state machine SHALL include a `completed_with_warnings` state in addition to `completed`; THE Backend SHALL set status to `completed_with_warnings` when the job finishes but one or more Core Agent results have `status = "error"`.
2. WHEN the Orchestrator completes all agent dispatches and at least one Core Agent returned `status = "error"`, THE Orchestrator SHALL set the job status to `completed_with_warnings` rather than `completed` and SHALL include an `agent_errors` list in the job record containing the names of all failed agents.
3. THE Frontend SHALL display a visual indicator (e.g., a warning badge) on any Analysis Job with status `completed_with_warnings`; the Report page SHALL include a banner listing the agents that failed and which dimension scores are `null` as a result.
4. THE `GET /api/v1/jobs/{job_id}` response SHALL include an `agent_errors` field (list of agent names) when status is `completed_with_warnings`.

---

### Requirement 38: API Version Metadata Endpoint

**User Story:** As a developer, I want a lightweight version endpoint so that I can programmatically detect the API version, schema version, and deployment revision during debugging and integration.

#### Acceptance Criteria

1. THE Backend SHALL expose `GET /api/v1/system/version` (no authentication required) returning: `api_version` (semver string), `analysis_engine_version` (semver string), `schema_version` (Alembic migration head revision), `frontend_version` (semver string from build artifact), and `git_commit_sha` (the git SHA of the deployed backend build).
2. THE `api_version`, `analysis_engine_version`, and `schema_version` fields SHALL be populated from `ConfigRegistry`; `git_commit_sha` SHALL be injected at build time via a Docker build argument or environment variable and SHALL default to `"unknown"` if not set.
3. THE endpoint SHALL return HTTP 200 and SHALL NOT require authentication so that it is usable in unauthenticated health-check and deployment-verification scripts.

---

### Requirement 39: Consistent Error Taxonomy

**User Story:** As an API consumer, I want machine-readable error codes on all error responses so that I can build reliable automated error handling.

#### Acceptance Criteria

1. EVERY HTTP error response from the Backend SHALL include a top-level `error_code` field containing one of the defined machine-readable codes alongside the HTTP status code and human-readable `detail` message.
2. THE Platform SHALL define and document the following error codes in the OpenAPI specification:
   - `REPO_NOT_FOUND` (HTTP 422) — the submitted repository URL does not exist or is inaccessible
   - `REPO_TOO_LARGE` (HTTP 422) — repository exceeds 2 GB or any other cloning limit
   - `CLONE_TIMEOUT` (HTTP 500/job-level) — cloning exceeded the configured timeout
   - `GITHUB_RATE_LIMIT` (HTTP 429) — GitHub API quota exhausted before metadata could be fetched
   - `AI_PROVIDER_TIMEOUT` (HTTP 500/agent-level) — all configured AI providers timed out
   - `PARSER_FAILURE` (HTTP 500/job-level) — `SharedAnalysisContext` build failed
   - `REPORT_FAILED` (HTTP 500/job-level) — report generation failed for one or more formats
   - `CACHE_MISS` (informational, not an error) — no cache entry found; full analysis will run
   - `CACHE_CORRUPT` (HTTP 500) — a cache entry exists but its artifact integrity check failed
   - `INVALID_URL` (HTTP 422) — URL fails allowlist or format validation
   - `AGENT_TIMEOUT` (agent-level) — an individual agent exceeded its per-agent timeout
   - `DAG_CYCLE` (HTTP 500/startup) — a circular dependency was detected in the agent DAG
3. THE `error_code` SHALL be present on all 4xx and 5xx responses and SHALL be `null` on 2xx responses.

---

### Requirement 40: Configurable Data Retention Policies

**User Story:** As a platform operator, I want configurable retention periods for all persisted data types so that I can manage storage costs and compliance requirements without code changes.

#### Acceptance Criteria

1. THE `ConfigRegistry` SHALL expose configurable retention TTLs (in days) for the following data types, each with a documented default:
   - `RETENTION_WORKSPACE_HOURS` (default: 1 hour) — cloned repository workspace on disk
   - `RETENTION_LOGS_DAYS` (default: 90 days) — structured application log files
   - `RETENTION_JOB_METRICS_DAYS` (default: 365 days) — `job_metrics` and `agent_metrics` table rows
   - `RETENTION_AI_INVOCATION_LOGS_DAYS` (default: 90 days) — `ai_invocation_logs` table rows
   - `RETENTION_CACHE_HOURS` (default: same as `REPO_CACHE_TTL_HOURS`) — `repository_caches` table entries and cached artifacts
   - `RETENTION_KG_EMBEDDINGS_DAYS` (default: 30 days after job expiry) — `kg_nodes.embedding` vectors (set to `null` after expiry, node record retained)
   - `RETENTION_REPORTS_DAYS` (default: 30 days) — generated report files on disk
2. THE `CleanupWorker` Celery beat task SHALL enforce each retention policy on its scheduled run; enforcement SHALL be idempotent — if a resource is already deleted, the task SHALL log a debug message and continue.
3. WHEN any retention policy deletes a resource, THE Backend SHALL write an audit log entry recording the resource type, resource ID, and deletion reason (`retention_policy`).
