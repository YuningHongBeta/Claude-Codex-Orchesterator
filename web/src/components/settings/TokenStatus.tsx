import { useState } from 'react';
import { RefreshCw, CheckCircle, XCircle, Loader2, Terminal } from 'lucide-react';
import { fetchTokenStatus } from '../../services/api';
import type { TokenStatusResponse } from '../../types';

function UsageBar({ percentage, color, label }: { percentage: number; color: string; label: string }) {
  const getBarColor = (pct: number) => {
    if (pct >= 85) return 'bg-red-500';
    if (pct >= 75) return 'bg-yellow-500';
    return color;
  };

  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className={percentage >= 85 ? 'text-red-400' : percentage >= 75 ? 'text-yellow-400' : 'text-emerald-400'}>
          {percentage}%
        </span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${getBarColor(percentage)} transition-all duration-300`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}

export function TokenStatus() {
  const [status, setStatus] = useState<TokenStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTokenStatus();
      setStatus(data);
    } catch (err) {
      setError('トークン状態の取得に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass rounded-2xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">CLI トークン状態</h3>
        <button
          onClick={loadStatus}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 rounded-lg text-white text-sm hover:bg-slate-600 transition-colors disabled:opacity-50"
        >
          {loading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <RefreshCw size={14} />
          )}
          {loading ? '取得中...' : '状態を取得'}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-xl text-red-400 text-sm mb-4">
          <XCircle size={16} />
          {error}
        </div>
      )}

      {!status && !loading && !error && (
        <p className="text-slate-500 text-sm text-center py-4">
          「状態を取得」ボタンをクリックして、CLIのトークン状態を確認してください
        </p>
      )}

      {status && (
        <div className="space-y-4">
          {/* Claude Code Status */}
          <div className="bg-slate-800/50 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Terminal size={16} className="text-violet-400" />
              <span className="text-sm font-medium text-white">Claude Code</span>
              {status.claude.available ? (
                <CheckCircle size={14} className="text-emerald-400 ml-auto" />
              ) : (
                <XCircle size={14} className="text-red-400 ml-auto" />
              )}
            </div>
            {status.claude.error ? (
              <p className="text-red-400 text-xs">{status.claude.error}</p>
            ) : (
              <>
                {/* Show usage bars for Claude (5-hour block and weekly) */}
                {status.claude.short_term_percentage != null && (
                  <UsageBar percentage={status.claude.short_term_percentage} color="bg-violet-500" label="5時間" />
                )}
                {status.claude.weekly_percentage != null && (
                  <UsageBar percentage={status.claude.weekly_percentage} color="bg-violet-400" label="週間" />
                )}
                {status.claude.raw_output && (
                  <p className="text-slate-300 text-xs mt-2 break-words whitespace-pre-wrap max-h-24 overflow-auto font-mono">
                    {status.claude.raw_output}
                  </p>
                )}
                {!status.claude.short_term_percentage && !status.claude.weekly_percentage && !status.claude.raw_output && (
                  <p className="text-slate-500 text-xs">出力なし</p>
                )}
              </>
            )}
          </div>

          {/* Codex Status */}
          <div className="bg-slate-800/50 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Terminal size={16} className="text-fuchsia-400" />
              <span className="text-sm font-medium text-white">Codex</span>
              {status.codex.available ? (
                <CheckCircle size={14} className="text-emerald-400 ml-auto" />
              ) : (
                <XCircle size={14} className="text-red-400 ml-auto" />
              )}
            </div>
            {status.codex.error ? (
              <p className="text-red-400 text-xs">{status.codex.error}</p>
            ) : (
              <>
                {status.codex.short_term_percentage != null && (
                  <UsageBar percentage={status.codex.short_term_percentage} color="bg-fuchsia-500" label="5時間" />
                )}
                {status.codex.weekly_percentage != null && (
                  <UsageBar percentage={status.codex.weekly_percentage} color="bg-fuchsia-400" label="週間" />
                )}
                {status.codex.raw_output && (
                  <p className="text-slate-300 text-xs mt-2 break-words whitespace-pre-wrap max-h-24 overflow-auto font-mono">
                    {status.codex.raw_output}
                  </p>
                )}
                {!status.codex.short_term_percentage && !status.codex.weekly_percentage && !status.codex.raw_output && (
                  <p className="text-slate-500 text-xs">出力なし</p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
