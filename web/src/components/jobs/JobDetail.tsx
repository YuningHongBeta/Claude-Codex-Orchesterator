import { useState } from 'react';
import { ArrowLeft, Clock, Folder, AlertCircle, FileText, Loader2, XCircle, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';
import { STAGE_LABELS, STAGE_ICONS } from '../../constants';
import { PerformerList } from './PerformerList';
import { PendingConfirmations } from './PendingConfirmations';
import { ExchangeViewer } from './ExchangeViewer';
import { LogViewer } from './LogViewer';
import { killJob } from '../../services/api';
import type { Job } from '../../types';

interface JobDetailProps {
  job: Job | null;
  loading: boolean;
  error: string | null;
  lastUpdatedAt?: string | null;
}

function formatTime(date: string): string {
  return new Date(date).toLocaleString('ja-JP');
}

function getStatusStyles(job: Job) {
  if (job.stage === 'error' || job.stage === 'killed') return 'border-red-500/30 bg-red-500/10 text-red-400';
  if (job.stage === 'stalled' || job.stalled) return 'border-orange-500/30 bg-orange-500/10 text-orange-400';
  if (job.stage === 'done') return 'border-blue-500/30 bg-blue-500/10 text-blue-400';
  if (job.stage === 'token_warning') return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400';
  if (job.running) return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400';
  return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400';
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}時間${remainingMinutes}分`;
}

export function JobDetail({ job, loading, error, lastUpdatedAt }: JobDetailProps) {
  const [killing, setKilling] = useState(false);
  const [killError, setKillError] = useState<string | null>(null);

  const handleKill = async () => {
    if (!job) return;
    if (!confirm('このジョブを強制終了しますか？')) return;

    setKilling(true);
    setKillError(null);
    try {
      const result = await killJob(job.id);
      if (!result.ok) {
        setKillError(result.error || 'ジョブの終了に失敗しました');
      }
    } catch (err) {
      setKillError('ジョブの終了に失敗しました');
    } finally {
      setKilling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400">
        <Loader2 size={40} className="animate-spin mb-4" />
        <p>読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-light rounded-2xl p-6 text-center">
        <AlertCircle size={48} className="mx-auto mb-4 text-red-400" />
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="glass-light rounded-2xl p-6 text-center">
        <p className="text-slate-400">ジョブが見つかりません</p>
      </div>
    );
  }

  const progress = Math.round((job.progress || 0) * 100);
  const stageLabel = STAGE_LABELS[job.stage] || job.stage;
  const stageIcon = STAGE_ICONS[job.stage] || '📋';
  const lastUpdatedLabel = lastUpdatedAt
    ? new Date(lastUpdatedAt).toLocaleTimeString('ja-JP', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : null;

  return (
    <div className="space-y-6">
      <PendingConfirmations jobId={job.id} />
      {/* Back button */}
      <Link
        to="/jobs"
        className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft size={18} />
        <span>ジョブ一覧に戻る</span>
      </Link>
      <div className="text-xs text-slate-500 min-h-[16px]">
        {lastUpdatedLabel ? `最終更新 ${lastUpdatedLabel}` : ''}
      </div>

      {/* Kill Error */}
      {killError && (
        <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-xl text-red-400 text-sm">
          <AlertCircle size={18} />
          {killError}
        </div>
      )}

      {/* Main card */}
      <div className="glass-light rounded-2xl overflow-hidden">
        {/* Header */}
        <div className={`p-6 border-b ${getStatusStyles(job)}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{stageIcon}</span>
              <span className="font-semibold">{stageLabel}</span>
            </div>
            <button
              onClick={handleKill}
              disabled={killing}
              className={`flex items-center gap-2 px-3 py-1.5 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-red-600/80 hover:bg-red-600`}
              title="ジョブを強制終了する"
            >
              {killing ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <XCircle size={16} />
              )}
              {killing ? '終了中...' : '強制終了'}
            </button>
          </div>
          <h2 className="text-xl font-bold text-white">{job.task || '（無題のタスク）'}</h2>
        </div>

        {/* Progress */}
        <div className="p-6 border-b border-slate-700/50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400">進捗</span>
            <span className="text-white font-bold">{progress}%</span>
          </div>
          <div className="h-3 bg-slate-700/50 rounded-full overflow-hidden">
            <div
              className="h-full progress-gradient rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Meta info */}
        <div className="p-6 grid grid-cols-2 gap-4">
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 text-slate-400 mb-1">
              <Clock size={16} />
              <span className="text-xs uppercase tracking-wide">開始</span>
            </div>
            <p className="text-white font-medium text-sm">
              {formatTime(job.started_at || job.updated_at)}
            </p>
          </div>
          <div className="glass rounded-xl p-4">
            <div className="flex items-center gap-2 text-slate-400 mb-1">
              <Clock size={16} />
              <span className="text-xs uppercase tracking-wide">更新</span>
            </div>
            <p className="text-white font-medium text-sm">{formatTime(job.updated_at)}</p>
          </div>
          {/* Last log update indicator */}
          <div className={`glass rounded-xl p-4 col-span-2 ${
            job.stalled || job.stage === 'stalled'
              ? 'border border-orange-500/30 bg-orange-500/5'
              : job.seconds_since_log_update && job.seconds_since_log_update > 60
              ? 'border border-yellow-500/30 bg-yellow-500/5'
              : ''
          }`}>
            <div className="flex items-center gap-2 mb-1">
              <Activity size={16} className={
                job.stalled || job.stage === 'stalled'
                  ? 'text-orange-400'
                  : job.seconds_since_log_update && job.seconds_since_log_update > 60
                  ? 'text-yellow-400'
                  : 'text-slate-400'
              } />
              <span className={`text-xs uppercase tracking-wide ${
                job.stalled || job.stage === 'stalled'
                  ? 'text-orange-400'
                  : job.seconds_since_log_update && job.seconds_since_log_update > 60
                  ? 'text-yellow-400'
                  : 'text-slate-400'
              }`}>
                最終ログ更新
              </span>
            </div>
            <div className="flex items-center justify-between">
              <p className="text-white font-medium text-sm">
                {job.last_log_update ? formatTime(job.last_log_update) : '更新なし'}
              </p>
              {job.seconds_since_log_update !== undefined && job.seconds_since_log_update !== null && (
                <span className={`text-sm ${
                  job.stalled || job.stage === 'stalled'
                    ? 'text-orange-400 font-semibold'
                    : job.seconds_since_log_update > 60
                    ? 'text-yellow-400'
                    : 'text-slate-500'
                }`}>
                  {formatDuration(job.seconds_since_log_update)}前
                  {(job.stalled || job.stage === 'stalled') && ' (停滞)'}
                </span>
              )}
            </div>
          </div>
          {job.run_dir && (
            <div className="glass rounded-xl p-4 col-span-2">
              <div className="flex items-center gap-2 text-slate-400 mb-1">
                <Folder size={16} />
                <span className="text-xs uppercase tracking-wide">保存先</span>
              </div>
              <p className="text-white font-mono text-sm truncate">{job.run_dir}</p>
            </div>
          )}
        </div>
      </div>

      {/* Performers */}
      <PerformerList job={job} />

      {/* Exchanges */}
      <ExchangeViewer jobId={job.id} />

      {/* Logs */}
      <LogViewer jobId={job.id} />

      {/* Error */}
      {job.error && (
        <div className="glass-light rounded-2xl p-6 border border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-2 text-red-400 mb-3">
            <AlertCircle size={20} />
            <h3 className="font-semibold">エラー</h3>
          </div>
          <pre className="text-red-300 text-sm whitespace-pre-wrap font-mono bg-red-950/30 rounded-lg p-4 overflow-x-auto">
            {job.error}
          </pre>
        </div>
      )}

      {/* Output */}
      <div className="glass-light rounded-2xl p-6">
        <div className="flex items-center gap-2 text-slate-300 mb-4">
          <FileText size={20} />
          <h3 className="font-semibold">結果</h3>
        </div>
        {job.final_text ? (
          <pre className="text-slate-200 text-sm whitespace-pre-wrap font-mono bg-slate-900/50 rounded-lg p-4 max-h-96 overflow-auto">
            {job.final_text}
          </pre>
        ) : (
          <p className="text-slate-500 text-center py-8">結果はまだ生成されていません</p>
        )}
      </div>
    </div>
  );
}
