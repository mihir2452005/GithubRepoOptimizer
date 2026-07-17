import { AnalyzeRequest, AnalyzeResponse } from './types';

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

export async function analyzeRepo(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 min timeout

  try {
    const body: Record<string, string> = { repo_url: request.repo_url };
    if (request.github_token) {
      body.github_token = request.github_token;
    }

    const response = await fetch('/api/v1/repos/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new ApiError(
        errorData.detail || `Request failed with status ${response.status}`,
        response.status,
        errorData.detail
      );
    }

    const data: AnalyzeResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request timed out. The analysis is taking too long.', 408);
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
    const response = await fetch('/health');
    return response.ok;
  } catch {
    return false;
  }
}
