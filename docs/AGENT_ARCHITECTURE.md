# RepoGenius AI — Agent Architecture

## How It Works (Simple Flow)

```
User enters in UI:
  ┌─────────────────────────────┐
  │  GitHub Repo URL            │
  │  GitHub Username (optional) │
  │  GitHub Token / Password    │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │  Clone Repository           │
  │  (GitPython, shallow clone) │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │  Parse Repository ONCE      │
  │  (SharedAnalysisContext)    │
  │  AST, Symbols, Deps, etc.  │
  └──────────────┬──────────────┘
                 │
                 ▼
  ┌─────────────────────────────────────────────────────────┐
  │  ALL AGENTS RUN IN PARALLEL (asyncio.gather)            │
  │                                                         │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
  │  │ Security │ │  Code    │ │  Arch    │ │   Dep    │  │
  │  │  Agent   │ │ Quality  │ │  Agent   │ │  Agent   │  │
  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐   │
  │  │  Tech    │ │   CTO    │ │  Optimization Agent  │   │
  │  │  Debt    │ │  Agent   │ │  (merges all results)│   │
  │  └──────────┘ └──────────┘ └──────────────────────┘   │
  └─────────────────────────────┬───────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────┐
  │  OPTIMIZATION REPORT                                    │
  │  • Optimization Score (0-100)                           │
  │  • Priority Matrix (Critical → Low)                     │
  │  • Quick Wins (fix in <2 hours)                         │
  │  • Sprint Roadmap (Sprint 1-4)                          │
  │  • Architecture Diagrams (Mermaid)                      │
  │  • Security Findings (OWASP + CVE)                      │
  │  • Technical Debt Estimate ($USD + hours)               │
  └─────────────────────────────────────────────────────────┘
```

---

## Agent List — What Each Agent Does + Free Tools Used

### 1. Repository Understanding Agent
**Purpose:** Extract repository metadata — languages, frameworks, structure, contributors.

**Free/Open-Source Tools Used:**
- `GitPython` — git operations, commit history, contributors
- `linguist` patterns — language detection by file extension
- `tree-sitter` — multi-language AST parsing (free, MIT license)
- File system traversal — directory structure, file counts

**Output:** Language map, file count, framework detection, commit stats, contributor count

---

### 2. Security Agent
**Purpose:** Find security vulnerabilities — secrets, CVEs, insecure patterns.

**Free/Open-Source Tools Used:**
- `detect-secrets` (Yelp, Apache 2.0) — hardcoded secrets detection
- `bandit` (PyCQA, Apache 2.0) — Python security linting
- `semgrep` (community rules, LGPL) — multi-language pattern matching for insecure code
- `safety` / `pip-audit` (free) — Python dependency CVE scanning
- `osv.dev` API (Google, free) — cross-language CVE database lookup
- `trivy` (Aqua Security, Apache 2.0) — dependency vulnerability scanning

**Output:** Findings with severity, OWASP category, CWE ID, exploitability, fix time

---

### 3. Code Quality Agent
**Purpose:** Measure code health — complexity, duplication, naming, dead code.

**Free/Open-Source Tools Used:**
- `radon` (MIT) — cyclomatic complexity, Maintainability Index, Halstead metrics (Python)
- `flake8` + plugins (MIT) — style violations, unused imports, unused variables
- `pylint` (GPL) — comprehensive Python linting
- `vulture` (MIT) — dead code detection
- `jscpd` (MIT) — cross-language copy-paste / code duplication detection
- `tree-sitter` — AST-based metrics for any language
- `cognitive-complexity` (MIT) — cognitive complexity calculation
- `eslint` (MIT) — JavaScript/TypeScript quality

**Output:** Per-file and aggregate metrics — cyclomatic complexity, duplication %, Maintainability Index, dead code %, cognitive complexity

---

### 4. Architecture Agent
**Purpose:** Detect architectural patterns, anti-patterns, and generate diagrams.

**Free/Open-Source Tools Used:**
- `tree-sitter` — AST parsing for import/module relationships
- `pydeps` (BSD) — Python package dependency visualization
- `madge` (MIT) — JavaScript/TypeScript module dependency graphs + circular dependency detection
- `arkit` (MIT) — architecture diagram generation
- Custom analysis on import graphs — fan-in, fan-out, instability index, coupling metrics
- `Mermaid` syntax generation — output diagrams as Mermaid markdown (free rendering)

**Output:** Patterns detected, anti-patterns with file references, 3 Mermaid diagrams (component, sequence, call graph), coupling metrics

---

### 5. Dependency Agent
**Purpose:** Audit all dependencies — outdated, vulnerable, license conflicts.

**Free/Open-Source Tools Used:**
- `pip-audit` (Apache 2.0) — Python dependency vulnerabilities
- `npm audit` (free, built-in) — Node.js vulnerability check
- `osv-scanner` (Google, Apache 2.0) — multi-language vulnerability scanning
- `pipdeptree` (MIT) — Python dependency tree (direct + transitive)
- `license-checker` (BSD) — npm license compliance scanning
- `pip-licenses` (MIT) — Python license extraction
- `libyear` (MIT) — measure how outdated dependencies are (in years)

**Output:** Direct deps, transitive deps, outdated packages (with version diff), license incompatibilities, known CVEs

---

### 6. Technical Debt Agent
**Purpose:** Estimate total debt in hours + cost, categorize, prioritize remediation.

**Free/Open-Source Tools Used:**
- `radon` — complexity-based debt estimation
- `pylint` — code smell detection
- `jscpd` — duplication-based debt
- `vulture` — dead code debt
- `coverage.py` (Apache 2.0) — test coverage gap identification
- Custom scoring — maps each smell to estimated hours based on industry averages

**Output:** Total debt (hours + $USD), breakdown by category, quick wins count, major refactors count, prioritized remediation list

---

### 7. Executive CTO Agent
**Purpose:** Synthesize all findings into an executive summary with strategic recommendations.

**Free/Open-Source Tools Used:**
- **Ollama** (MIT) — local LLM inference (Llama 3, CodeLlama, Qwen — all free)
- Custom prompt engineering — structured synthesis prompt
- No external API needed — runs locally for $0 cost

**Output:** Overall risk level, top 3 strategic recommendations, production readiness assessment

---

### 8. Repository Optimization Agent
**Purpose:** Merge all findings, deduplicate, prioritize, generate Optimization Roadmap.

**Free/Open-Source Tools Used:**
- **Ollama** (MIT) — LLM for prioritization reasoning and ROI estimation
- Custom deduplication — content-similarity matching across agent findings
- Sprint planning logic — categorize findings into 4 sprints by priority/effort

**Output:** Optimization Score (0-100), Engineering Maturity Level, Quick Wins (top 10), 4-Sprint Roadmap, per-finding effort estimates

---

## Free Open-Source Tool Summary

| Tool | Language Support | License | Used For |
|------|-----------------|---------|----------|
| tree-sitter | 40+ languages | MIT | AST parsing, symbol extraction |
| detect-secrets | All | Apache 2.0 | Hardcoded secret detection |
| bandit | Python | Apache 2.0 | Security patterns |
| semgrep | 30+ languages | LGPL | Security + quality patterns |
| radon | Python | MIT | Complexity + Maintainability Index |
| vulture | Python | MIT | Dead code detection |
| jscpd | All | MIT | Code duplication detection |
| pylint | Python | GPL | Comprehensive linting |
| flake8 | Python | MIT | Style + unused import detection |
| eslint | JS/TS | MIT | JavaScript quality |
| madge | JS/TS | MIT | Module dependency + circular deps |
| pip-audit | Python | Apache 2.0 | Dependency CVE scanning |
| osv-scanner | All | Apache 2.0 | Cross-language CVE scanning |
| trivy | All | Apache 2.0 | Container + dependency scanning |
| coverage.py | Python | Apache 2.0 | Test coverage gaps |
| Ollama | — | MIT | Local LLM (free, no API cost) |
| GitPython | — | BSD | Git operations |
| Mermaid | — | MIT | Diagram generation |

**Total cost for analysis: $0.00** when using Ollama locally. Optional paid fallback to Claude/Bedrock for higher quality on complex tasks.

---

## BaseAgent Interface

```python
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    name: str                          # Unique identifier
    version: str = "1.0.0"            # Agent version (tracked per result)
    dependencies: list[str] = []       # Empty = runs immediately in parallel

    @abstractmethod
    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        """Core analysis logic. Every agent implements this."""
        ...

    async def pre_run(self, payload) -> None:
        """Optional setup hook."""
        pass

    async def post_run(self, result) -> None:
        """Optional cleanup hook."""
        pass

    async def on_error(self, exc: Exception) -> None:
        """Called when run() raises. Default: log error."""
        pass
```

---

## How Agents Run In Parallel

```python
# ALL agents dispatched simultaneously using asyncio.gather
async def run_all_agents(context: SharedAnalysisContext):
    agents = [
        SecurityAgent(),
        CodeQualityAgent(),
        ArchitectureAgent(),
        DependencyAgent(),
        TechnicalDebtAgent(),
        ExecutiveCTOAgent(),
        RepositoryOptimizationAgent(),
    ]

    # Run ALL at the same time — no waiting between agents
    results = await asyncio.gather(
        *[run_single_agent(agent, context) for agent in agents],
        return_exceptions=True
    )

    return results

async def run_single_agent(agent, context):
    """Run one agent with timeout protection."""
    try:
        payload = build_payload(agent, context)
        return await asyncio.wait_for(agent.run(payload), timeout=60)
    except asyncio.TimeoutError:
        return AgentOutputPayload(agent=agent.name, status="error", error_message="Timeout")
    except Exception as e:
        return AgentOutputPayload(agent=agent.name, status="error", error_message=str(e))
```

**Key point:** `asyncio.gather` runs all agents at the SAME TIME. If you have 8 agents and each takes 30 seconds, total time is ~30 seconds (not 240 seconds).

---

## Adding a New Agent (Zero Changes to Orchestrator)

1. Create a file in `agents/core/my_new_agent.py`
2. Inherit from `BaseAgent`
3. Set `name` and implement `run()`
4. Done — auto-discovered at startup

```python
# agents/core/my_new_agent.py
class MyNewAgent(BaseAgent):
    name = "my_new_analysis"
    version = "1.0.0"
    dependencies = []  # runs in parallel with everything

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        ctx = payload.metadata["analysis_context"]
        # ... your analysis logic using free tools ...
        return AgentOutputPayload(agent=self.name, status="success", findings=[...])
```
