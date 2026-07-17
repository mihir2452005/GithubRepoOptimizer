import { useEffect, useState } from 'react';
import { getDiff } from '../api';
import type { DiffResult } from '../types';

interface DiffViewProps {
  jobA: string;
  jobB: string;
  onClose: () => void;
}

export function DiffView({ jobA, jobB, onClose }: DiffViewProps) {
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDiff();
  }, [jobA, jobB]);

  const loadDiff = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getDiff(jobA, jobB);
      setDiff(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load comparison');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <div className="text-slate-400 text-center">Loading comparison...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <div className="text-red-400 text-center">{error}</div>
        <button
          onClick={onClose}
          className="mt-3 mx-auto block text-sm text-slate-400 hover:text-slate-200"
        >
          Close
        </button>
      </div>
    );
  }

  if (!diff) return null;

  const scoreDelta = diff.score_delta;
  const isImproved = scoreDelta != null && scoreDelta > 0;
  const isWorse = scoreDelta != null && scoreDelta < 0;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-slate-200">Run Comparison</h3>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 text-xl"
          aria-label="Close comparison"
        >
          ×
        </button>
      </div>

      {/* Score Delta */}
      {scoreDelta != null && (
        <div className={`text-center mb-6 p-4 rounded-lg border ${
          isImproved
            ? 'bg-green-900/20 border-green-800'
            : isWorse
            ? 'bg-red-900/20 border-red-800'
            : 'bg-slate-700/50 border-slate-600'
        }`}>
          <div className={`text-3xl font-bold ${
            isImproved ? 'text-green-400' : isWorse ? 'text-red-400' : 'text-slate-300'
          }`}>
            {isImproved ? '+' : ''}{scoreDelta}
          </div>
          <div className="text-sm text-slate-400 mt-1">
            Score {isImproved ? 'improvement' : isWorse ? 'regression' : 'unchanged'}
          </div>
        </div>
      )}

      {/* Metrics Summary */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-green-900/20 border border-green-800/50 rounded-lg p-3 text-center">
          <div className="text-xl font-bold text-green-400">
            {diff.resolved_findings.length}
          </div>
          <div className="text-xs text-green-300/70">Resolved</div>
        </div>
        <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-3 text-center">
          <div className="text-xl font-bold text-red-400">
            {diff.new_findings.length}
          </div>
          <div className="text-xs text-red-300/70">New Issues</div>
        </div>
        <div className="bg-slate-700/50 border border-slate-600 rounded-lg p-3 text-center">
          <div className="text-xl font-bold text-slate-300">
            {diff.unchanged_findings.length}
          </div>
          <div className="text-xs text-slate-400">Unchanged</div>
        </div>
      </div>

      {/* Resolved Findings */}
      {diff.resolved_findings.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-green-400 mb-2">
            ✓ Resolved ({diff.resolved_findings.length})
          </h4>
          <div className="space-y-1">
            {diff.resolved_findings.slice(0, 10).map((finding, i) => (
              <div key={i} className="text-xs text-slate-400 pl-4 border-l-2 border-green-800">
                <span className="text-green-300/70">[{finding.severity}]</span>{' '}
                {finding.description?.slice(0, 100)}
              </div>
            ))}
            {diff.resolved_findings.length > 10 && (
              <div className="text-xs text-slate-500 pl-4">
                ...and {diff.resolved_findings.length - 10} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* New Findings */}
      {diff.new_findings.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-red-400 mb-2">
            ✗ New Issues ({diff.new_findings.length})
          </h4>
          <div className="space-y-1">
            {diff.new_findings.slice(0, 10).map((finding, i) => (
              <div key={i} className="text-xs text-slate-400 pl-4 border-l-2 border-red-800">
                <span className="text-red-300/70">[{finding.severity}]</span>{' '}
                {finding.description?.slice(0, 100)}
              </div>
            ))}
            {diff.new_findings.length > 10 && (
              <div className="text-xs text-slate-500 pl-4">
                ...and {diff.new_findings.length - 10} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* Net Summary */}
      <div className="mt-4 pt-4 border-t border-slate-700 text-center">
        <span className="text-xs text-slate-400">
          {diff.metrics_delta.findings_count_before} findings → {diff.metrics_delta.findings_count_after} findings
          {' '}
          ({diff.metrics_delta.findings_delta >= 0 ? '+' : ''}{diff.metrics_delta.findings_delta} net)
        </span>
      </div>
    </div>
  );
}
