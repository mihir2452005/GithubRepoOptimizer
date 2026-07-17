import { useState } from 'react';
import { AnalyzeForm } from './components/AnalyzeForm';
import { LoadingState } from './components/LoadingState';
import { ResultsDashboard } from './components/ResultsDashboard';
import { analyzeRepo } from './api';
import type { AnalyzeResponse } from './types';

type AppState = 'idle' | 'loading' | 'done';

function App() {
  const [state, setState] = useState<AppState>('idle');
  const [results, setResults] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (repoUrl: string, githubToken?: string) => {
    setState('loading');
    setError(null);

    try {
      const response = await analyzeRepo({
        repo_url: repoUrl,
        github_token: githubToken || undefined,
      });
      setResults(response);
      setState('done');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(message);
      setState('idle');
    }
  };

  const handleReset = () => {
    setState('idle');
    setResults(null);
    setError(null);
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
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {state === 'idle' && (
          <AnalyzeForm onSubmit={handleSubmit} error={error} />
        )}
        {state === 'loading' && <LoadingState />}
        {state === 'done' && results && (
          <ResultsDashboard data={results} onReset={handleReset} />
        )}
      </main>
    </div>
  );
}

export default App;
