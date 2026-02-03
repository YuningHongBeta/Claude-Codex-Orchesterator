import { ListTodo, RefreshCw } from 'lucide-react';
import { PageContainer } from '../components/layout';
import { JobCard } from '../components/jobs';
import { useJobs } from '../hooks/useJobs';

export function Jobs() {
  const { jobs, loading, error, refresh, lastUpdatedAt } = useJobs();

  const lastUpdatedLabel = lastUpdatedAt
    ? new Date(lastUpdatedAt).toLocaleTimeString('ja-JP', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : null;

  return (
    <PageContainer>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-fuchsia-500/20 flex items-center justify-center">
              <ListTodo size={20} className="text-fuchsia-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">ジョブ一覧</h1>
              <p className="text-xs text-slate-400">
                {jobs.length}件のジョブ
                {lastUpdatedLabel ? ` ・ 最終更新 ${lastUpdatedLabel}` : ''}
              </p>
            </div>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-slate-700/50 transition-colors disabled:opacity-50"
          >
            <RefreshCw
              size={18}
              className="text-slate-400"
            />
          </button>
        </div>

        {/* Job list */}
        {loading && jobs.length === 0 ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="glass-light rounded-xl p-4 animate-pulse"
              >
                <div className="h-4 bg-slate-700/50 rounded w-1/4 mb-3" />
                <div className="h-5 bg-slate-700/50 rounded w-3/4 mb-2" />
                <div className="h-3 bg-slate-700/50 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : jobs.length > 0 ? (
          <div className="space-y-2">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        ) : (
          <div className="glass-light rounded-xl p-8 text-center">
            <ListTodo size={40} className="mx-auto mb-3 text-slate-600" />
            <p className="text-slate-400 text-sm">ジョブがありません</p>
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400">更新に失敗しました</div>
        )}
      </div>
    </PageContainer>
  );
}
