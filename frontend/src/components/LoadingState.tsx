import { useState, useEffect } from 'react';

const agents = [
  { name: 'Security Analysis', icon: '🔒' },
  { name: 'Code Quality', icon: '✨' },
  { name: 'Architecture Review', icon: '📐' },
  { name: 'Dependency Audit', icon: '📦' },
  { name: 'Technical Debt', icon: '🔧' },
  { name: 'Executive Summary', icon: '📊' },
  { name: 'Repository Optimization', icon: '⚡' },
  { name: 'Repository Understanding', icon: '🧠' },
];

export function LoadingState() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const agentInterval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % agents.length);
    }, 2000);

    const timerInterval = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);

    return () => {
      clearInterval(agentInterval);
      clearInterval(timerInterval);
    };
  }, []);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  return (
    <div className="max-w-lg mx-auto mt-24 text-center">
      {/* Spinner */}
      <div className="relative w-20 h-20 mx-auto mb-8">
        <div className="absolute inset-0 rounded-full border-4 border-slate-700" />
        <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-500 animate-spin" />
        <div className="absolute inset-2 rounded-full border-4 border-transparent border-b-indigo-400 animate-spin-slow" />
      </div>

      {/* Text */}
      <h2 className="text-2xl font-semibold text-white mb-2">
        Analyzing Repository...
      </h2>
      <p className="text-slate-400 mb-2">
        Analyzing 8 agents in parallel...
      </p>

      {/* Progress indicator */}
      <div className="w-full bg-slate-700 rounded-full h-2 mb-4 max-w-xs mx-auto">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-1000"
          style={{ width: `${Math.min((elapsed / 60) * 100, 95)}%` }}
        />
      </div>

      {/* Slow connection message */}
      {elapsed >= 10 && (
        <p className="text-sm text-amber-400/80 mb-6 animate-fade-in">
          Server is analyzing your repository... This typically takes 30-60 seconds
        </p>
      )}

      {/* Agent list */}
      <div className="card text-left space-y-2">
        {agents.map((agent, index) => (
          <div
            key={agent.name}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-300 ${
              index === activeIndex
                ? 'bg-blue-500/10 border border-blue-500/30'
                : index < activeIndex
                ? 'opacity-60'
                : 'opacity-40'
            }`}
          >
            <span className="text-lg">{agent.icon}</span>
            <span className="text-sm text-slate-300 flex-1">{agent.name}</span>
            {index < activeIndex && (
              <span className="text-green-400 text-xs">✓</span>
            )}
            {index === activeIndex && (
              <span className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            )}
          </div>
        ))}
      </div>

      {/* Timer */}
      <p className="text-sm text-slate-500 mt-4">
        Elapsed: {formatTime(elapsed)}
      </p>
    </div>
  );
}
