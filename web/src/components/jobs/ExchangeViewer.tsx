import { useEffect, useMemo, useState } from 'react';
import { MessageSquare, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
import { fetchExchange, fetchExchanges, fetchScore } from '../../services/api';
import { REFRESH_INTERVAL } from '../../constants';
import type { ExchangeDetail, ExchangeSummary, Score } from '../../types';

interface ExchangeViewerProps {
  jobId: string;
}

function formatTime(value?: string): string {
  if (!value) return '';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
}

function stageLabel(status?: string): string {
  if (!status) return '待機中';
  if (status === 'waiting_for_user') return 'ユーザー確認待ち';
  if (status === 'waiting_for_concertmaster') return 'コンマス待ち';
  if (status === 'waiting_for_performer') return '演奏者待ち';
  if (status === 'done') return '完了';
  return status;
}

export function ExchangeViewer({ jobId }: ExchangeViewerProps) {
  const [score, setScore] = useState<Score | null>(null);
  const [exchanges, setExchanges] = useState<ExchangeSummary[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, ExchangeDetail | null>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(`orchestrator:exchangeExpanded:${jobId}`);
    setExpanded(saved || null);
  }, [jobId]);

  useEffect(() => {
    const key = `orchestrator:exchangeExpanded:${jobId}`;
    if (expanded) {
      sessionStorage.setItem(key, expanded);
    } else {
      sessionStorage.removeItem(key);
    }
  }, [expanded, jobId]);

  useEffect(() => {
    let timer: number;
    async function refresh() {
      try {
        const [scoreData, exchangeData] = await Promise.all([
          fetchScore(jobId),
          fetchExchanges(jobId),
        ]);
        if (scoreData) {
          setScore(scoreData);
        }
        setExchanges(exchangeData);
        setError(null);
        if (expanded) {
          const detail = await fetchExchange(jobId, expanded);
          setDetails((prev) => ({ ...prev, [expanded]: detail }));
        }
      } catch {
        setError('交換情報の取得に失敗しました');
      }
    }
    refresh();
    timer = window.setInterval(refresh, REFRESH_INTERVAL);
    return () => window.clearInterval(timer);
  }, [jobId, expanded]);

  const sortedExchanges = useMemo(() => {
    return [...exchanges].sort((a, b) => (a.id || '').localeCompare(b.id || '', undefined, { numeric: true }));
  }, [exchanges]);

  const handleToggle = async (exchangeId: string) => {
    if (expanded === exchangeId) {
      setExpanded(null);
      return;
    }
    setExpanded(exchangeId);
    const detail = await fetchExchange(jobId, exchangeId);
    setDetails((prev) => ({ ...prev, [exchangeId]: detail }));
  };

  return (
    <div className="glass-light rounded-2xl overflow-hidden">
      <div className="p-4 border-b border-slate-700/50">
        <div className="flex items-center gap-2 text-slate-300">
          <MessageSquare size={20} />
          <h3 className="font-semibold">指揮者 / コンマス</h3>
        </div>
      </div>
      <div className="p-4 space-y-4">
        {score?.refined_task && (
          <div className="glass rounded-xl p-4">
            <div className="text-xs text-slate-400 mb-2">指揮者の言い直し</div>
            <div className="text-sm text-slate-200 whitespace-pre-wrap">{score.refined_task}</div>
            {score.global_notes && (
              <div className="mt-3 text-xs text-slate-500 whitespace-pre-wrap">{score.global_notes}</div>
            )}
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400">{error}</div>
        )}

        {sortedExchanges.length === 0 ? (
          <div className="text-sm text-slate-500">交換情報がありません</div>
        ) : (
          <div className="space-y-2">
            {sortedExchanges.map((ex) => {
              const detail = details[ex.id];
              return (
                <div key={ex.id} className="border border-slate-700/40 rounded-xl">
                  <button
                    onClick={() => handleToggle(ex.id)}
                    className="w-full flex items-center gap-2 px-3 py-3 text-left"
                  >
                    {expanded === ex.id ? (
                      <ChevronDown size={16} className="text-slate-500" />
                    ) : (
                      <ChevronRight size={16} className="text-slate-500" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-slate-200 truncate">
                        {ex.performer?.name || `演奏者 ${ex.id}`}
                      </div>
                      <div className="text-xs text-slate-500">
                        {stageLabel(ex.status)} {ex.updated_at ? `・${formatTime(ex.updated_at)}` : ''}
                      </div>
                    </div>
                    {ex.status === 'waiting_for_user' && (
                      <span className="text-xs text-amber-400 flex items-center gap-1">
                        <AlertCircle size={14} /> 要確認
                      </span>
                    )}
                  </button>
                  {expanded === ex.id && detail && (
                    <div className="px-4 pb-4 space-y-3">
                      {(detail.history || []).map((item, idx) => (
                        <div key={idx} className="text-xs text-slate-300 whitespace-pre-wrap">
                          <span className="text-slate-500 mr-2">
                            {item.role === 'concertmaster' ? 'コンマス' : item.role === 'performer' ? '演奏者' : item.role}
                          </span>
                          {item.content}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
