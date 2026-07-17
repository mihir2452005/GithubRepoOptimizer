import { useState } from 'react';

interface AnalyzeFormProps {
  onSubmit: (repoUrl: string, githubToken?: string) => void;
  error: string | null;
}

export function AnalyzeForm({ onSubmit, error }: AnalyzeFormProps) {
  const [repoUrl, setRepoUrl] = useState('');
  const [githubToken, setGithubToken] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    onSubmit(repoUrl.trim(), githubToken.trim() || undefined);
  };

  const isValidUrl = repoUrl.match(/^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+/);

  return (
    <div className="max-w-2xl mx-auto mt-16 sm:mt-24">
      {/* Hero */}
      <div className="text-center mb-10">
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
          Optimize Your Repository
        </h2>
        <p className="text-lg text-slate-400 max-w-lg mx-auto">
          Get a comprehensive AI-powered analysis of your GitHub repository with
          actionable insights from 8 specialized agents.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="card space-y-5">
        <div>
          <label htmlFor="repo-url" className="block text-sm font-medium text-slate-300 mb-2">
            GitHub Repository URL <span className="text-red-400">*</span>
          </label>
          <input
            id="repo-url"
            type="url"
            className="input-field"
            placeholder="https://github.com/owner/repository"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            required
            autoFocus
          />
          {repoUrl && !isValidUrl && (
            <p className="mt-1.5 text-sm text-amber-400">
              Please enter a valid GitHub URL (https://github.com/owner/repo)
            </p>
          )}
        </div>

        <div>
          <label htmlFor="github-token" className="block text-sm font-medium text-slate-300 mb-2">
            GitHub Token{' '}
            <span className="text-slate-500 font-normal">(optional — for private repos)</span>
          </label>
          <input
            id="github-token"
            type="password"
            className="input-field"
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
          />
          <p className="mt-1.5 text-xs text-slate-500">
            Required for private repositories. Your token is sent directly to the backend and never stored.
          </p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={!repoUrl.trim() || (!!repoUrl && !isValidUrl)}
          className="btn-primary"
        >
          Analyze Repository
        </button>
      </form>

      {/* Features */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-10">
        {[
          { icon: '🔒', label: 'Security' },
          { icon: '📐', label: 'Architecture' },
          { icon: '⚡', label: 'Performance' },
          { icon: '📦', label: 'Dependencies' },
        ].map((feature) => (
          <div key={feature.label} className="text-center p-3">
            <div className="text-2xl mb-1">{feature.icon}</div>
            <div className="text-xs text-slate-400">{feature.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
