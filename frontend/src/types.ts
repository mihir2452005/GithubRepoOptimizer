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
