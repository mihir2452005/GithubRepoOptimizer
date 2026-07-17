import { AnalyzeRequest, AnalyzeResponse, HistoryEntry, DiffResult } from './types';

/**
 * API base URL — uses VITE_API_URL env var in production (points to Render backend).
 * Falls back to empty string (same-origin) for local development with Vite proxy.
 */
const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Request timeout in milliseconds.
 * 3 minutes to account for Render cold starts + clone + analysis.
 */
const TIMEOUT_MS = 180_000;

const HISTORY_STORAGE_KEY = 'repogenius_history';

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Parse error response body from the backend, extracting
 * the most useful message for display.
 */
async function parseErrorResponse(response: Response): Promise<string> {
  try {
    const errorBody = await response.json();
    return errorBody?.detail || errorBody?.error || `Server error: ${response.status}`;
  } catch {
    return `Server error: ${response.status}`;
  }
}

export async function analyzeRepo(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const body: Record<string, string> = { repo_url: request.repo_url };
    if (request.github_token) {
      body.github_token = request.github_token;
    }

    const response = await fetch(`${API_BASE}/api/v1/repos/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const message = await parseErrorResponse(response);
      throw new ApiError(message, response.status, message);
    }

    const data: AnalyzeResponse = await response.json();

    // Save to localStorage cache for instant history on return
    try {
      const historyCache: HistoryEntry[] = JSON.parse(
        localStorage.getItem(HISTORY_STORAGE_KEY) || '[]'
      );

      // Calculate findings count from results
      let findingsCount = 0;
      if (data.results) {
        for (const agentResult of Object.values(data.results)) {
          findingsCount += agentResult.findings?.length ?? 0;
        }
      }

      historyCache.unshift({
        id: data.job_id,
        repo_url: request.repo_url,
        timestamp: new Date().toISOString(),
        optimization_score: data.optimization_score ?? null,
        health_grade: data.health_grade ?? null,
        findings_count: findingsCount,
      });

      // Keep only the 50 most recent entries
      localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(historyCache.slice(0, 50)));
    } catch {
      // localStorage unavailable — continue without caching
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(
        'Request timed out. The analysis is taking longer than expected — the server may be starting up. Please try again in a moment.',
        408
      );
    }
    if (error instanceof TypeError) {
      throw new ApiError(
        'Unable to connect to the server. Please ensure the backend is running.',
        0
      );
    }
    throw new ApiError(
      error instanceof Error ? error.message : 'An unexpected error occurred',
      500
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

// === History API ===

export async function getHistory(): Promise<HistoryEntry[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/history`);
    if (!response.ok) {
      return [];
    }
    return await response.json();
  } catch {
    return [];
  }
}

export async function getHistoryByRepo(repoUrl: string): Promise<HistoryEntry[]> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/history/repo?url=${encodeURIComponent(repoUrl)}`);
    if (!response.ok) {
      return [];
    }
    return await response.json();
  } catch {
    return [];
  }
}

// === Diff API ===

export async function getDiff(jobA: string, jobB: string): Promise<DiffResult> {
  const response = await fetch(`${API_BASE}/api/v1/diff?job_a=${encodeURIComponent(jobA)}&job_b=${encodeURIComponent(jobB)}`);
  if (!response.ok) {
    const message = await parseErrorResponse(response);
    throw new ApiError(message, response.status);
  }
  return await response.json();
}

// === Reports API ===

export async function getReportHtml(jobId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/v1/reports/${encodeURIComponent(jobId)}/html`);
  if (!response.ok) {
    const message = await parseErrorResponse(response);
    throw new ApiError(message, response.status);
  }
  return await response.text();
}

// === Job Status (polling fallback) ===

export async function getJobStatus(jobId: string): Promise<AnalyzeResponse | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/repos/jobs/${encodeURIComponent(jobId)}/status`);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch {
    return null;
  }
}
