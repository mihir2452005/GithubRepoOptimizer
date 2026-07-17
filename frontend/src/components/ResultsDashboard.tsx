import { useState } from 'react';
import type { AnalyzeResponse, AgentResult, QuickWin, SprintItem } from '../types';
import { ScoreBadge } from './ScoreBadge';
import { FindingCard } from './FindingCard';

interface ResultsDashboardProps {
  data: AnalyzeResponse;
  onReset: () => void;
}

const gradeColors: Record<string, string> = {
  'A+': 'bg-green-500/20 text-green-300 border-green-500/40',
  'A': 'bg-green-500/20 text-green-300 border-green-500/40',
  'B+': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  'B': 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  'C+': 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  'C': 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  'D': 'bg-red-500/20 text-red-300 border-red-500/40',
  'F': 'bg-red-600/20 text-red-300 border-red-600/40',
};

const agentLabels: Record<string, { name: string; icon: string }> = {
  security: { name: 'Security Analysis', icon: '🔒' },
  code_quality: { name: 'Code Quality', icon: '✨' },
  architecture: { name: 'Architecture Review', icon: '📐' },
  dependency: { name: 'Dependency Audit', icon: '📦' },
  technical_debt: { name: 'Technical Debt', icon: '🔧' },
  executive_cto: { name: 'Executive Summary', icon: '📊' },
  repository_optimization: { name: 'Repository Optimization', icon: '⚡' },
  repository_understanding: { name: 'Repository Understanding', icon: '🧠' },
};

export function ResultsDashboard({ data, onReset }: ResultsDashboardProps) {
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const toggleAgent = (agent: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(agent)) next.delete(agent);
      else next.add(agent);
      return next;
    });
  };

  const quickWins = extractQuickWins(data);
  const sprintRoadmap = extractSprintRoadmap(data);
  const gradeClass = gradeColors[data.health_grade] || gradeColors['C'];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="card">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <ScoreBadge score={data.optimization_score} />
          <div className="flex-1 text-center sm:text-left">
            <h2 className="text-2xl font-bold text-white mb-1">Analysis Complete</h2>
            <p className="text-slate-400 font-mono text-sm mb-3 break-all">
              {data.repo_url}
            </p>
            <div className="flex items-center gap-3 flex-wrap justify-center sm:justify-start">
              <span className={`px-3 py-1 rounded-full border text-sm font-medium ${gradeClass}`}>
                Grade: {data.health_grade}
              </span>
              <span className="text-sm text-slate-400">
                {data.context.total_files} files analyzed
              </span>
              <span className="text-sm text-slate-400">
                {data.context.languages?.join(', ')}
              </span>
              {data.context.framework && (
                <span className="text-sm text-slate-500">
                  Framework: {data.context.framework}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Wins */}
      {quickWins.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            ⚡ Quick Wins
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {quickWins.map((win, i) => (
              <div key={i} className="card">
                <div className="flex items-start gap-3">
                  <span className="text-lg">🎯</span>
                  <div>
                    <h4 className="text-sm font-medium text-white">{win.title}</h4>
                    <p className="text-xs text-slate-400 mt-1">{win.description}</p>
                    <div className="flex gap-2 mt-2">
                      {win.priority && (
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                          {win.priority}
                        </span>
                      )}
                      {win.effort && (
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                          Effort: {win.effort}
                        </span>
                      )}
                      {win.impact && (
                        <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">
                          Impact: {win.impact}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Agent Results */}
      <section>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          🤖 Agent Results
        </h3>
        <div className="space-y-3">
          {Object.entries(data.results).map(([key, result]) => (
            <AgentSection
              key={key}
              agentKey={key}
              result={result}
              isExpanded={expandedAgents.has(key)}
              onToggle={() => toggleAgent(key)}
            />
          ))}
        </div>
      </section>

      {/* Sprint Roadmap */}
      {sprintRoadmap.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            🗺️ Sprint Roadmap
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {sprintRoadmap.map((sprint, i) => (
              <div key={i} className="card">
                <div className="text-xs text-blue-400 font-medium mb-2">
                  Sprint {sprint.sprint || i + 1}
                </div>
                <h4 className="text-sm font-medium text-white mb-2">{sprint.title}</h4>
                <p className="text-xs text-slate-400 mb-3">{sprint.description}</p>
                {sprint.tasks && sprint.tasks.length > 0 && (
                  <ul className="space-y-1">
                    {sprint.tasks.map((task, ti) => (
                      <li key={ti} className="text-xs text-slate-500 flex items-start gap-1.5">
                        <span className="text-slate-600 mt-0.5">•</span>
                        {task}
                      </li>
                    ))}
                  </ul>
                )}
                {sprint.effort_days && (
                  <p className="text-xs text-slate-600 mt-2">
                    ~{sprint.effort_days} days
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Metrics Overview */}
      <section>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          📈 Repository Metrics
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricCard label="Total Files" value={String(data.context.total_files)} />
          <MetricCard label="Languages" value={String(data.context.languages?.length || 0)} />
          <MetricCard label="Health Grade" value={data.health_grade} />
          <MetricCard label="Score" value={`${data.optimization_score}/100`} />
        </div>
      </section>

      {/* Reset Button */}
      <div className="text-center pt-4">
        <button onClick={onReset} className="btn-primary max-w-sm mx-auto">
          Analyze Another Repository
        </button>
      </div>
    </div>
  );
}

/* --- Sub-components --- */

function AgentSection({
  agentKey,
  result,
  isExpanded,
  onToggle,
}: {
  agentKey: string;
  result: AgentResult;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const label = agentLabels[agentKey] || { name: agentKey, icon: '🔹' };
  const findingsCount = result.findings?.length || 0;

  return (
    <div className="card !p-0 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-slate-700/30 transition-colors"
      >
        <span className="text-lg">{label.icon}</span>
        <span className="flex-1 text-sm font-medium text-white">{label.name}</span>
        {result.status === 'success' && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-300">
            ✓ Success
          </span>
        )}
        {result.status === 'error' && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-300">
            ✗ Error
          </span>
        )}
        {findingsCount > 0 && (
          <span className="text-xs text-slate-400">
            {findingsCount} finding{findingsCount > 1 ? 's' : ''}
          </span>
        )}
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="px-5 pb-5 border-t border-slate-700/50">
          {result.summary && (
            <p className="text-sm text-slate-300 mt-4 mb-4">{result.summary}</p>
          )}
          {result.error && (
            <p className="text-sm text-red-400 mt-4">{result.error}</p>
          )}
          {result.findings && result.findings.length > 0 && (
            <div className="space-y-3 mt-4">
              {result.findings.map((finding, i) => (
                <FindingCard key={i} finding={finding} />
              ))}
            </div>
          )}
          {result.metrics && Object.keys(result.metrics).length > 0 && (
            <div className="mt-4">
              <h5 className="text-xs font-medium text-slate-400 uppercase mb-2">Metrics</h5>
              <div className="bg-slate-900/50 rounded-lg p-3 text-xs font-mono text-slate-400 overflow-x-auto">
                <pre>{JSON.stringify(result.metrics, null, 2)}</pre>
              </div>
            </div>
          )}
          {!result.summary && !result.findings?.length && !result.error && (
            <p className="text-sm text-slate-500 mt-4 italic">No detailed findings available.</p>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card text-center">
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  );
}

/* --- Helper functions --- */

function extractQuickWins(data: AnalyzeResponse): QuickWin[] {
  const optimization = data.results.repository_optimization;
  if (!optimization?.metrics) return [];

  const quickWins = optimization.metrics.quick_wins;
  if (Array.isArray(quickWins)) {
    return quickWins.map((win) => {
      if (typeof win === 'string') {
        return { title: win, description: '', priority: '', effort: '', impact: '' };
      }
      return {
        title: win.title || win.name || '',
        description: win.description || '',
        priority: win.priority || '',
        effort: win.effort || '',
        impact: win.impact || '',
      };
    });
  }
  return [];
}

function extractSprintRoadmap(data: AnalyzeResponse): SprintItem[] {
  const optimization = data.results.repository_optimization;
  if (!optimization?.metrics) return [];

  const roadmap = optimization.metrics.sprint_roadmap;
  if (Array.isArray(roadmap)) {
    return roadmap.map((item, index) => {
      if (typeof item === 'string') {
        return { sprint: index + 1, title: item, description: '', tasks: [] };
      }
      return {
        sprint: item.sprint || index + 1,
        title: item.title || item.name || '',
        description: item.description || '',
        tasks: Array.isArray(item.tasks) ? item.tasks : [],
        effort_days: item.effort_days,
      };
    });
  }
  return [];
}
