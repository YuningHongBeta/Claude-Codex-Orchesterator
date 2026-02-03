import { Clock, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { STAGE_LABELS, STAGE_ICONS } from '../../constants';
import type { Job } from '../../types';

interface JobCardProps {
  job: Job;
}

function getStatusBadge(job: Job) {
  if (job.stage === 'error') return { text: 'エラー', class: 'bg-status-error status-error' };
  if (job.stage === 'done') return { text: '完了', class: 'bg-status-done status-done' };
  if (job.running) return { text: '実行中', class: 'bg-status-running status-running' };
  return { text: '待機中', class: 'bg-status-pending status-pending' };
}

function formatTime(date: string): string {
  return new Date(date).toLocaleString('ja-JP', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function JobCard({ job }: JobCardProps) {
  const progress = Math.round((job.progress || 0) * 100);
  const stageLabel = STAGE_LABELS[job.stage] || job.stage;
  const stageIcon = STAGE_ICONS[job.stage] || '📋';
  const status = getStatusBadge(job);

  return (
    <Link
      to={`/jobs/${job.id}`}
      className="block glass-light rounded-xl p-4 hover:bg-slate-700/40 transition-colors"
    >
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${status.class}`}>
              {status.text}
            </span>
          </div>
          <h3 className="font-semibold text-white truncate">
            {job.task || '（無題のタスク）'}
          </h3>
          <div className="flex items-center gap-4 mt-2 text-sm text-slate-400">
            <span className="flex items-center gap-1">
              <span>{stageIcon}</span>
              <span>{stageLabel}</span>
            </span>
            <span className="flex items-center gap-1">
              <Clock size={14} />
              <span>{formatTime(job.updated_at)}</span>
            </span>
            <span className="text-violet-400 font-medium">{progress}%</span>
          </div>

          {/* Progress bar */}
          <div className="mt-3 h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
            <div
              className="h-full progress-gradient rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <ChevronRight
          size={20}
          className="text-slate-500 flex-shrink-0 mt-2"
        />
      </div>
    </Link>
  );
}
