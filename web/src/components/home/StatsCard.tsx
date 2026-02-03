interface StatsCardProps {
  label: string;
  value: number | string;
  color: 'emerald' | 'blue' | 'red';
  loading?: boolean;
}

const colorClasses = {
  emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30',
  blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/30',
  red: 'from-red-500/20 to-red-600/10 border-red-500/30',
};

const textColors = {
  emerald: 'text-emerald-400',
  blue: 'text-blue-400',
  red: 'text-red-400',
};

export function StatsCard({ label, value, color, loading }: StatsCardProps) {
  return (
    <div className={`glass-light rounded-xl p-4 bg-gradient-to-br ${colorClasses[color]} text-center`}>
      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">{label}</p>
      {loading ? (
        <div className="h-7 bg-slate-700/50 rounded animate-pulse" />
      ) : (
        <p className={`text-2xl font-bold ${textColors[color]}`}>{value}</p>
      )}
    </div>
  );
}
