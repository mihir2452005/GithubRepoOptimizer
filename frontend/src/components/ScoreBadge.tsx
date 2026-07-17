interface ScoreBadgeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
}

function getScoreColor(score: number): { ring: string; text: string; bg: string } {
  if (score >= 90) return { ring: 'stroke-green-500', text: 'text-green-400', bg: 'bg-green-500/10' };
  if (score >= 70) return { ring: 'stroke-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10' };
  if (score >= 50) return { ring: 'stroke-orange-500', text: 'text-orange-400', bg: 'bg-orange-500/10' };
  return { ring: 'stroke-red-500', text: 'text-red-400', bg: 'bg-red-500/10' };
}

export function ScoreBadge({ score, size = 'lg' }: ScoreBadgeProps) {
  const colors = getScoreColor(score);
  const circumference = 2 * Math.PI * 45;
  const progress = ((100 - score) / 100) * circumference;

  const dimensions = {
    sm: 'w-16 h-16',
    md: 'w-24 h-24',
    lg: 'w-32 h-32',
  };

  const textSize = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-4xl',
  };

  return (
    <div className={`relative ${dimensions[size]} ${colors.bg} rounded-full flex items-center justify-center`}>
      <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          strokeWidth="6"
          className="stroke-slate-700"
        />
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={progress}
          strokeLinecap="round"
          className={`${colors.ring} transition-all duration-1000 ease-out`}
        />
      </svg>
      <span className={`${textSize[size]} font-bold ${colors.text}`}>
        {score}
      </span>
    </div>
  );
}
