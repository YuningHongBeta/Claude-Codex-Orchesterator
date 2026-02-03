import { Clock, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { STAGE_LABELS, STAGE_ICONS } from '../../constants';
import type { Job } from '../../types';

interface RecentJobCardProps {
  job: Job;
}

function getStatusStyles(job: Job) {
  if (job.stage === 'error') return 'border-red-500/30 bg-red-500/5';
  if (job.stage === 'done') return 'border-blue-500/30 bg-blue-500/5';
  if (job.running) return 'border-emerald-500/30 bg-emerald-500/5';
  return 'border-yellow-500/30 bg-yellow-500/5';
}

function formatRelativeTime(date: string): string {
  const now = new Date();
  const then = new Date(date);
  const diff = Math.floor((now.getTime() - then.getTime()) / 1000);

  if (diff < 60) return `${diff}秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)}分前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}時間前`;
  return `${Math.floor(diff / 86400)}日前`;
}

export function RecentJobCard({ job }: RecentJobCardProps) {
  const progress = Math.round((job.progress || 0) * 100);
  const stageLabel = STAGE_LABELS[job.stage] || job.stage;
  const stageIcon = STAGE_ICONS[job.stage] || '📋';

  return (
    <Link
      to={`/jobs/${job.id}`}
      className={`block glass-light rounded-xl p-4 border ${getStatusStyles(job)} transition-colors`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white truncate">{job.task || '（無題）'}</h3>
          <div className="flex items-center gap-3 mt-2 text-sm text-slate-400">
            <span className="flex items-center gap-1">
              <span>{stageIcon}</span>
              <span>{stageLabel}</span>
            </span>
            <span className="flex items-center gap-1">
              <Clock size={14} />
              <span>{formatRelativeTime(job.updated_at)}</span>
            </span>
          </div>
        </div>
        <ArrowRight size={18} className="text-slate-500 flex-shrink-0 mt-1" />
      </div>

      {/* Progress bar */}
      <div className="mt-3 h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
        <div
          className="h-full progress-gradient rounded-full"
          style={{ width: `${progress}%` }}
        />
      </div>
    </Link>
  );
}
