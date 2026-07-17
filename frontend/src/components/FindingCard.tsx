import { useState } from 'react';
import type { AgentFinding } from '../types';

interface FindingCardProps {
  finding: AgentFinding;
}

const severityConfig = {
  critical: { icon: '🔴', label: 'Critical', color: 'border-red-500/50 bg-red-500/5' },
  high: { icon: '🟠', label: 'High', color: 'border-orange-500/50 bg-orange-500/5' },
  medium: { icon: '🟡', label: 'Medium', color: 'border-amber-500/50 bg-amber-500/5' },
  low: { icon: '🔵', label: 'Low', color: 'border-blue-500/50 bg-blue-500/5' },
  info: { icon: 'ℹ️', label: 'Info', color: 'border-slate-500/50 bg-slate-500/5' },
};

export function FindingCard({ finding }: FindingCardProps) {
  const [showSolution, setShowSolution] = useState(false);
  const [copied, setCopied] = useState(false);
  const config = severityConfig[finding.severity] || severityConfig.info;
  const hasSolution = finding.solution || finding.solution_code;

  const handleCopyCode = async () => {
    if (!finding.solution_code) return;
    try {
      await navigator.clipboard.writeText(finding.solution_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = finding.solution_code;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={`border rounded-lg p-4 ${config.color}`}>
      <div className="flex items-start gap-3">
        <span className="text-lg flex-shrink-0 mt-0.5">{config.icon}</span>
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
              {config.label}
            </span>
            {finding.category && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700/50 text-slate-400">
                {finding.category}
              </span>
            )}
            {finding.estimated_fix_minutes && (
              <span className="text-xs text-slate-500">
                ⏱️ ~{finding.estimated_fix_minutes}min
              </span>
            )}
          </div>

          {/* Description */}
          <p className="text-sm text-slate-200 mb-2">{finding.description}</p>

          {/* File location */}
          {finding.file_path && (
            <p className="text-xs text-slate-500 font-mono mb-2">
              📄 {finding.file_path}
              {finding.line_number ? `:${finding.line_number}` : ''}
            </p>
          )}

          {/* Solution toggle button */}
          {hasSolution && (
            <button
              onClick={() => setShowSolution(!showSolution)}
              className="text-xs font-medium text-emerald-400 hover:text-emerald-300 
                         transition-colors flex items-center gap-1 mt-1"
            >
              {showSolution ? '▾ Hide Solution' : '▸ Show Solution'}
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                💡 Fix Available
              </span>
            </button>
          )}

          {/* Solution content */}
          {showSolution && hasSolution && (
            <div className="mt-3 p-3 rounded-lg bg-slate-800/80 border border-emerald-500/20">
              {/* Solution explanation */}
              {finding.solution && (
                <div className="mb-3">
                  <h5 className="text-xs font-semibold text-emerald-400 uppercase mb-1">
                    How to Fix
                  </h5>
                  <p className="text-sm text-slate-300">{finding.solution}</p>
                </div>
              )}

              {/* Code fix */}
              {finding.solution_code && (
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <h5 className="text-xs font-semibold text-blue-400 uppercase">
                      Code Example
                    </h5>
                    <button
                      onClick={handleCopyCode}
                      className="text-xs px-2 py-1 rounded bg-slate-700 text-slate-300 
                                 hover:bg-slate-600 transition-colors flex items-center gap-1"
                      aria-label="Copy code to clipboard"
                    >
                      {copied ? (
                        <span className="text-green-400">✓ Copied!</span>
                      ) : (
                        <>📋 Copy Code</>
                      )}
                    </button>
                  </div>
                  <pre className="text-xs font-mono text-slate-400 bg-slate-900/60 
                                  rounded p-2 overflow-x-auto whitespace-pre-wrap">
                    {finding.solution_code}
                  </pre>
                </div>
              )}

              {/* Reference link */}
              {finding.solution_reference && (
                <div>
                  <a
                    href={finding.solution_reference}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:text-blue-300 underline"
                  >
                    📚 Learn more →
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
