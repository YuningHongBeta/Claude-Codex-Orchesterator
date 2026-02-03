import { CheckCircle, Loader2, Clock } from 'lucide-react';
import type { Performer } from '../../types';

interface PerformerCardProps {
  performer: Performer;
  index: number;
  currentIndex?: number;
  total: number;
  isRunning: boolean;
}

type Status = 'completed' | 'running' | 'pending';

function getStatus(index: number, currentIndex: number | undefined, isRunning: boolean): Status {
  if (currentIndex === undefined) return 'pending';
  if (index < currentIndex) return 'completed';
  if (index === currentIndex && isRunning) return 'running';
  if (index === currentIndex) return 'completed';
  return 'pending';
}

const statusStyles: Record<Status, string> = {
  completed: 'border-emerald-500/30 bg-emerald-500/5',
  running: 'border-violet-500/30 bg-violet-500/10',
  pending: 'border-slate-700/50 bg-slate-800/30',
};

const statusIcons: Record<Status, React.ReactNode> = {
  completed: <CheckCircle size={18} className="text-emerald-400" />,
  running: <Loader2 size={18} className="text-violet-400" />,
  pending: <Clock size={18} className="text-slate-500" />,
};

export function PerformerCard({
  performer,
  index,
  currentIndex,
  total,
  isRunning,
}: PerformerCardProps) {
  const status = getStatus(index, currentIndex, isRunning);

  return (
    <div
      className={`glass-light rounded-xl p-4 border ${statusStyles[status]}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">{statusIcons[status]}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-slate-500 font-mono">
              {index + 1}/{total}
            </span>
            <h4 className="font-semibold text-white truncate">{performer.name}</h4>
          </div>
          <p className="text-sm text-slate-400 line-clamp-2">{performer.task}</p>
          {performer.notes && (
            <p className="text-xs text-slate-500 mt-1 italic">{performer.notes}</p>
          )}
        </div>
      </div>
    </div>
  );
}
