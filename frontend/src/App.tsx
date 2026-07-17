import { useState, useCallback } from 'react';
import { AnalyzeForm } from './components/AnalyzeForm';
import { LoadingState } from './components/LoadingState';
import { ResultsDashboard } from './components/ResultsDashboard';
import { HistoryList } from './components/HistoryList';
import { ProgressStream } from './components/ProgressStream';
import { DiffView } from './components/DiffView';
import { analyzeRepo, getReportHtml, getJobStatus } from './api';
import type { AnalyzeResponse } from './types';

type AppState = 'idle' | 'loading' | 'done';

function App() {
  const [state, setState] = useState<AppState>('idle');
  const [results, setResults] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState<{ jobA: string; jobB: string } | null>(null);

  const handleSubmit = async (repoUrl: string, githubToken?: string) => {
    setState('loading');
    setError(null);
    setCurrentJobId(null);

    try {
      const response = await analyzeRepo({
        repo_url: repoUrl,
        github_token: githubToken || undefined,
      });

      if (response.status === 'running' && response.job_id) {
        // Async mode — use WebSocket progress
        setCurrentJobId(response.job_id);
      } else {
        setResults(response);
        setState('done');
      }
    } catch (err) {
      let message: string;
      if (err instanceof Error) {
        message = err.message;
      } else if (typeof err === 'object' && err !== null && 'detail' in err) {
        message = String((err as { detail: unknown }).detail);
      } else {
        message = 'An unexpected error occurred. Please try again.';
      }
      setError(message);
      setState('idle');
    }
  };

  const handleProgressComplete = useCallback(async () => {
    // Analysis complete via WebSocket — fetch the results
    if (currentJobId) {
      const result = await getJobStatus(currentJobId);
      if (result && result.status === 'completed') {
        setResults(result);
        setState('done');
      }
    }
  }, [currentJobId]);

  const handleProgressError = useCallback((errorMsg: string) => {
    setError(errorMsg);
    setState('idle');
    setCurrentJobId(null);
  }, []);

  const handleReset = () => {
    setState('idle');
    setResults(null);
    setError(null);
    setCurrentJobId(null);
    setShowDiff(null);
  };

  const handleViewHistoryResult = async (jobId: string) => {
    // Load a past result from history API directly
    try {
      const API_BASE = import.meta.env.VITE_API_URL || '';
      const response = await fetch(`${API_BASE}/api/v1/history/${jobId}`);
      if (response.ok) {
        const entry = await response.json();
        // Map history entry to AnalyzeResponse format
        setResults({
          job_id: entry.id,
          status: 'completed',
          repo_url: entry.repo_url,
          context: entry.context || { total_files: 0, languages: [] },
          results: entry.results || {},
          optimization_score: entry.optimization_score,
          health_grade: entry.health_grade,
        });
        setState('done');
      }
    } catch {
      setError('Failed to load analysis from history.');
    }
  };

  const handleCompare = (jobA: string, jobB: string) => {
    setShowDiff({ jobA, jobB });
  };

  const handleDownloadReport = async () => {
    if (!results?.job_id) return;
    try {
      const html = await getReportHtml(results.job_id);
      // Open in a new window
      const newWindow = window.open('', '_blank');
      if (newWindow) {
        newWindow.document.write(html);
        newWindow.document.close();
      }
    } catch {
      // Fallback: download as file
      try {
        const html = await getReportHtml(results.job_id);
        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `repogenius-report-${results.job_id.slice(0, 8)}.html`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        // Silently fail
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">R</span>
            </div>
            <h1 className="text-xl font-semibold text-white">
              RepoGenius <span className="text-blue-400">AI</span>
            </h1>
            {state === 'done' && (
              <button
                onClick={handleReset}
                className="ml-auto text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                ← New Analysis
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {state === 'idle' && (
          <>
            <AnalyzeForm onSubmit={handleSubmit} error={error} />

            {/* History Section */}
            <div className="mt-8">
              <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wide mb-3">
                Recent Analyses
              </h2>
              <HistoryList
                onViewResult={handleViewHistoryResult}
                onCompare={handleCompare}
              />
            </div>

            {/* Diff View Modal */}
            {showDiff && (
              <div className="mt-6">
                <DiffView
                  jobA={showDiff.jobA}
                  jobB={showDiff.jobB}
                  onClose={() => setShowDiff(null)}
                />
              </div>
            )}
          </>
        )}

        {state === 'loading' && (
          <div>
            {currentJobId ? (
              <ProgressStream
                jobId={currentJobId}
                onComplete={handleProgressComplete}
                onError={handleProgressError}
              />
            ) : (
              <LoadingState />
            )}
          </div>
        )}

        {state === 'done' && results && (
          <>
            {/* Action buttons above results */}
            <div className="flex items-center gap-3 mb-6">
              <button
                onClick={handleDownloadReport}
                className="text-sm px-4 py-2 bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 hover:text-white transition-colors"
              >
                📄 Download HTML Report
              </button>
            </div>

            <ResultsDashboard data={results} onReset={handleReset} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
