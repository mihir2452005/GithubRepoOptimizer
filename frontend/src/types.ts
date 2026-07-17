export interface AnalyzeRequest {
  repo_url: string;
  github_token?: string;
}

export interface AgentFinding {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  title: string;
  description: string;
  file_path?: string;
  line_number?: number;
  category?: string;
  recommendation?: string;

  // Solution fields — how to fix this issue
  solution?: string;           // Step-by-step explanation of the fix
  solution_code?: string;      // Code snippet showing the fix
  solution_reference?: string; // URL to docs/guide for more info

  // Security enrichment
  owasp_category?: string;
  cwe_id?: string;
  exploitability?: string;
  fix_difficulty?: 'easy' | 'medium' | 'hard';
  estimated_fix_minutes?: number;
}

export interface AgentMetrics {
  [key: string]: unknown;
}

export interface AgentResult {
  agent: string;
  status: 'success' | 'error' | 'partial';
  findings?: AgentFinding[];
  metrics?: AgentMetrics;
  summary?: string;
  error?: string;
}

export interface QuickWin {
  title: string;
  description: string;
  priority: string;
  effort: string;
  impact: string;
}

export interface SprintItem {
  sprint: number;
  title: string;
  description: string;
  tasks: string[];
  effort_days?: number;
}

export interface RepositoryContext {
  total_files: number;
  languages: string[];
  framework?: string;
  primary_language?: string;
  repo_size?: string;
}

export interface AnalyzeResponse {
  job_id: string;
  status: string;
  repo_url: string;
  context: RepositoryContext;
  results: Record<string, AgentResult>;
  optimization_score: number;
  health_grade: string;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

// === History ===
export interface HistoryEntry {
  id: string;
  repo_url: string;
  timestamp: string;
  optimization_score: number | null;
  health_grade: string | null;
  findings_count: number;
  results_summary?: Record<string, { status: string; findings_count: number; summary: string }>;
}

// === Diff ===
export interface DiffResult {
  job_id_a: string;
  job_id_b: string;
  repo_url_a: string;
  repo_url_b: string;
  score_delta: number | null;
  new_findings: AgentFinding[];
  resolved_findings: AgentFinding[];
  unchanged_findings: AgentFinding[];
  metrics_delta: {
    findings_count_before: number;
    findings_count_after: number;
    findings_delta: number;
    new_findings_count: number;
    resolved_findings_count: number;
    health_grade_before: string | null;
    health_grade_after: string | null;
  };
}

// === WebSocket Progress ===
export interface ProgressEvent {
  type: 'agent_complete' | 'complete' | 'error' | 'heartbeat';
  agent?: string;
  status?: string;
  progress?: number;
  total_agents?: number;
  completed?: number;
  job_id?: string;
  error?: string;
}
