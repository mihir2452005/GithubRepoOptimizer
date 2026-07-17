import { useEffect, useState } from 'react';
import { getHistory } from '../api';
import type { HistoryEntry } from '../types';

interface HistoryListProps {
  onViewResult: (jobId: string) => void;
  onCompare?: (jobA: string, jobB: string) => void;
}

export function HistoryList({ onViewResult, onCompare }: HistoryListProps) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedForCompare, setSelectedForCompare] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    const data = await getHistory();
    setEntries(data);
    setLoading(false);
  };

  const handleCompareClick = (jobId: string) => {
    if (!selectedForCompare) {
      setSelectedForCompare(jobId);
    } else if (selectedForCompare !== jobId && onCompare) {
      onCompare(selectedForCompare, jobId);
      setSelectedForCompare(null);
    } else {
      setSelectedForCompare(null);
    }
  };

  const formatDate = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return timestamp;
    }
  };

  const getGradeColor = (grade: string | null) => {
    if (!grade) return 'text-slate-400';
    switch (grade.toUpperCase()) {
      case 'A': case 'A+': return 'text-green-400';
      case 'B': case 'B+': return 'text-blue-400';
      case 'C': case 'C+': return 'text-yellow-400';
      case 'D': case 'D+': return 'text-orange-400';
      default: return 'text-red-400';
    }
  };

  if (loading) {
    return (
      <div className="text-slate-400 text-sm py-4 text-center">
        Loading history...
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-6 text-center">
        <p>No analysis history yet.</p>
        <p className="mt-1">Analyze a repository to see it here.</p>
      </div>
    );
  }

  // Group entries by repo_url to enable compare functionality
  const repoGroups: Record<string, HistoryEntry[]> = {};
  for (const entry of entries) {
    if (!repoGroups[entry.repo_url]) {
      repoGroups[entry.repo_url] = [];
    }
    repoGroups[entry.repo_url].push(entry);
  }

  return (
    <div className="space-y-2">
      {selectedForCompare && (
        <div className="bg-blue-900/30 border border-blue-700 rounded-lg px-3 py-2 text-sm text-blue-300">
          Select another analysis to compare with. <button onClick={() => setSelectedForCompare(null)} className="underline ml-1">Cancel</button>
        </div>
      )}

      {entries.map((entry) => {
        const repoName = entry.repo_url.split('/').slice(-2).join('/').replace('.git', '');
        const hasMultipleRuns = (repoGroups[entry.repo_url]?.length ?? 0) > 1;
        const isSelected = selectedForCompare === entry.id;

        return (
          <div
            key={entry.id}
            className={`bg-slate-800/50 border rounded-lg px-4 py-3 flex items-center justify-between gap-3 transition-colors ${
              isSelected ? 'border-blue-500 bg-blue-900/20' : 'border-slate-700 hover:border-slate-600'
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-200 truncate">
                  {repoName}
                </span>
                {entry.optimization_score != null && (
                  <span className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">
                    {entry.optimization_score}/100
                  </span>
                )}
                {entry.health_grade && (
                  <span className={`text-xs font-bold ${getGradeColor(entry.health_grade)}`}>
                    {entry.health_grade}
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                {formatDate(entry.timestamp)} · {entry.findings_count} findings
              </div>
            </div>

            <div className="flex items-center gap-2">
              {hasMultipleRuns && onCompare && (
                <button
                  onClick={() => handleCompareClick(entry.id)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${
                    isSelected
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {isSelected ? 'Selected' : 'Compare'}
                </button>
              )}
              <button
                onClick={() => onViewResult(entry.id)}
                className="text-xs px-2 py-1 bg-slate-700 text-slate-300 rounded hover:bg-slate-600 transition-colors"
              >
                View
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
