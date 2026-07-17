import { useEffect, useRef, useState } from 'react';
import type { ProgressEvent } from '../types';

interface AgentStatus {
  name: string;
  status: 'pending' | 'success' | 'error' | 'timeout';
}

interface ProgressStreamProps {
  jobId: string;
  onComplete: () => void;
  onError?: (error: string) => void;
}

// Known agent names for display
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  security: 'Security Analysis',
  code_quality: 'Code Quality',
  architecture: 'Architecture Review',
  dependency: 'Dependency Analysis',
  repository_optimization: 'Optimization Scoring',
  technical_debt: 'Technical Debt',
  repo_understanding: 'Repository Understanding',
  executive_cto: 'Executive Summary',
};

export function ProgressStream({ jobId, onComplete, onError }: ProgressStreamProps) {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [progress, setProgress] = useState(0);
  const [totalAgents, setTotalAgents] = useState(0);
  const [completed, setCompleted] = useState(0);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/analysis/${jobId}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data: ProgressEvent = JSON.parse(event.data);

          if (data.type === 'agent_complete') {
            const agentName = data.agent || 'unknown';

            setAgents((prev) => {
              const exists = prev.find((a) => a.name === agentName);
              if (exists) {
                return prev.map((a) =>
                  a.name === agentName
                    ? { ...a, status: (data.status as AgentStatus['status']) || 'success' }
                    : a
                );
              }
              return [
                ...prev,
                { name: agentName, status: (data.status as AgentStatus['status']) || 'success' },
              ];
            });

            if (data.progress != null) setProgress(data.progress);
            if (data.total_agents != null) setTotalAgents(data.total_agents);
            if (data.completed != null) setCompleted(data.completed);
          } else if (data.type === 'complete') {
            setProgress(100);
            onComplete();
          } else if (data.type === 'error') {
            onError?.(data.error || 'Analysis failed');
          }
          // Ignore heartbeat messages
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        setConnected(false);
        // WebSocket failed — parent should fall back to polling
      };

      ws.onclose = () => {
        setConnected(false);
      };

      return () => {
        ws.close();
      };
    } catch {
      // WebSocket not supported or connection failed
      setConnected(false);
    }
  }, [jobId, onComplete, onError]);

  const getStatusIcon = (status: AgentStatus['status']) => {
    switch (status) {
      case 'success': return '✓';
      case 'error': return '✗';
      case 'timeout': return '⏱';
      default: return '⏳';
    }
  };

  const getStatusColor = (status: AgentStatus['status']) => {
    switch (status) {
      case 'success': return 'text-green-400';
      case 'error': return 'text-red-400';
      case 'timeout': return 'text-yellow-400';
      default: return 'text-slate-400 animate-pulse';
    }
  };

  const getDisplayName = (agentName: string) => {
    return AGENT_DISPLAY_NAMES[agentName] || agentName.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 max-w-md mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-slate-200">Analysis Progress</h3>
        {connected && (
          <span className="flex items-center gap-1.5 text-xs text-green-400">
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
            Live
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-700 rounded-full h-2 mb-4">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="text-xs text-slate-400 mb-4">
        {completed > 0
          ? `${completed} of ${totalAgents} agents completed`
          : 'Starting analysis...'}
      </div>

      {/* Agent status list */}
      <div className="space-y-2">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className="flex items-center gap-2 text-sm"
          >
            <span className={`font-mono ${getStatusColor(agent.status)}`}>
              {getStatusIcon(agent.status)}
            </span>
            <span className="text-slate-300">
              {getDisplayName(agent.name)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
