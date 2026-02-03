import { Link } from 'react-router-dom';
import { Send, ListTodo, Zap, TrendingUp } from 'lucide-react';
import { PageContainer } from '../components/layout';
import { StatsCard, RecentJobCard } from '../components/home';
import { useJobs } from '../hooks/useJobs';

export function Home() {
  const { jobs, loading } = useJobs();

  const runningJobs = jobs.filter((j) => j.running).length;
  const completedJobs = jobs.filter((j) => j.stage === 'done').length;
  const errorJobs = jobs.filter((j) => j.stage === 'error').length;
  const recentJobs = jobs.slice(0, 3);

  return (
    <PageContainer>
      <div className="space-y-6">
        {/* Hero section */}
        <div className="text-center py-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 mb-4 animate-float">
            <Zap size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">
            Claude Orchestrator
          </h1>
          <p className="text-slate-400 text-sm">
            AIタスクを簡単に管理・実行
          </p>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-2 gap-3">
          <Link
            to="/submit"
            className="glass-light rounded-xl p-4 flex flex-col items-center gap-2 hover:bg-slate-700/40 transition-all duration-200 group"
          >
            <div className="w-12 h-12 rounded-xl bg-violet-500/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Send size={24} className="text-violet-400" />
            </div>
            <span className="text-white font-medium text-sm">新規ジョブ</span>
          </Link>
          <Link
            to="/jobs"
            className="glass-light rounded-xl p-4 flex flex-col items-center gap-2 hover:bg-slate-700/40 transition-all duration-200 group"
          >
            <div className="w-12 h-12 rounded-xl bg-fuchsia-500/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <ListTodo size={24} className="text-fuchsia-400" />
            </div>
            <span className="text-white font-medium text-sm">ジョブ一覧</span>
          </Link>
        </div>

        {/* Stats */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <TrendingUp size={20} className="text-violet-400" />
            統計
          </h2>
          <div className="grid grid-cols-3 gap-3">
            <StatsCard
              label="実行中"
              value={runningJobs}
              color="emerald"
              loading={loading}
            />
            <StatsCard
              label="完了"
              value={completedJobs}
              color="blue"
              loading={loading}
            />
            <StatsCard
              label="エラー"
              value={errorJobs}
              color="red"
              loading={loading}
            />
          </div>
        </div>

        {/* Recent jobs */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">最近のジョブ</h2>
            {jobs.length > 3 && (
              <Link
                to="/jobs"
                className="text-sm text-violet-400 hover:text-violet-300 transition-colors"
              >
                すべて見る
              </Link>
            )}
          </div>
          {loading ? (
            <div className="glass-light rounded-xl p-8 text-center">
              <div className="animate-pulse text-slate-400">読み込み中...</div>
            </div>
          ) : recentJobs.length > 0 ? (
            <div className="space-y-2">
              {recentJobs.map((job) => (
                <RecentJobCard key={job.id} job={job} />
              ))}
            </div>
          ) : (
            <div className="glass-light rounded-xl p-8 text-center">
              <p className="text-slate-400 text-sm">ジョブがありません</p>
              <Link
                to="/submit"
                className="inline-block mt-3 text-violet-400 hover:text-violet-300 text-sm"
              >
                最初のジョブを作成 →
              </Link>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
