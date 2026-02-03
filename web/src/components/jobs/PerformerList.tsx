import { useState, useEffect } from 'react';
import { Users, Loader2 } from 'lucide-react';
import { fetchScore } from '../../services/api';
import { PerformerCard } from './PerformerCard';
import type { Job, Score } from '../../types';

interface PerformerListProps {
  job: Job;
}

export function PerformerList({ job }: PerformerListProps) {
  const [score, setScore] = useState<Score | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadScore() {
      setLoading(true);
      const data = await fetchScore(job.id);
      setScore(data);
      setLoading(false);
    }
    loadScore();
  }, [job.id]);

  if (loading) {
    return (
      <div className="glass-light rounded-2xl p-6">
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 size={20} className="animate-spin" />
          <span>演奏者情報を読み込み中...</span>
        </div>
      </div>
    );
  }

  if (!score || !score.performers || score.performers.length === 0) {
    return null;
  }

  const isPerformerStage =
    job.stage === 'performer' || job.stage === 'performer_done';
  const currentIndex = isPerformerStage ? (job.performer_index ?? 1) - 1 : undefined;
  const isRunning = job.running && job.stage === 'performer';

  return (
    <div className="glass-light rounded-2xl overflow-hidden">
      <div className="p-4 border-b border-slate-700/50">
        <div className="flex items-center gap-2 text-slate-300">
          <Users size={20} />
          <h3 className="font-semibold">演奏者</h3>
          <span className="text-xs text-slate-500">
            ({score.performers.length}名)
          </span>
          {job.performer_name && isRunning && (
            <span className="ml-auto text-sm text-violet-400">
              現在: {job.performer_name}
            </span>
          )}
        </div>
      </div>

      <div className="p-4 grid gap-3 sm:grid-cols-2">
        {score.performers.map((performer, index) => (
          <PerformerCard
            key={index}
            performer={performer}
            index={index}
            currentIndex={
              job.stage === 'conductor' || job.stage === 'conductor_done'
                ? -1
                : job.stage === 'done' || job.stage === 'mix' || job.stage === 'mix_done'
                  ? score.performers.length
                  : currentIndex
            }
            total={score.performers.length}
            isRunning={isRunning}
          />
        ))}
      </div>
    </div>
  );
}
