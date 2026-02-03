import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { fetchExchanges, postExchangeReply } from '../../services/api';
import { REFRESH_INTERVAL } from '../../constants';
import type { ExchangeSummary } from '../../types';

interface PendingConfirmationsProps {
  jobId: string;
}

const NOTIFY_KEY = 'orchestrator:notify';

function getQuestion(ex: ExchangeSummary): string {
  const pending = ex.pending || {};
  const question = (pending.question || '').trim();
  if (question) return question;
  return '確認内容が未設定です';
}

function getReason(ex: ExchangeSummary): string {
  const pending = ex.pending || {};
  return (pending.reason || '').trim();
}

function getPendingType(ex: ExchangeSummary): 'ok_ng' | 'choice' | 'free_text' {
  const pending = ex.pending || {};
  const t = pending.type;
  if (t === 'choice') return 'choice';
  if (t === 'free_text') return 'free_text';
  return 'ok_ng';
}

export function PendingConfirmations({ jobId }: PendingConfirmationsProps) {
  const [exchanges, setExchanges] = useState<ExchangeSummary[]>([]);
  const [sending, setSending] = useState<Record<string, boolean>>({});
  const [choiceDraft, setChoiceDraft] = useState<Record<string, string>>({});
  const [freeTextDraft, setFreeTextDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: number;
    async function refresh() {
      try {
        const exchangeData = await fetchExchanges(jobId);
        setExchanges(exchangeData);
        setError(null);
      } catch {
        setError('確認情報の取得に失敗しました');
      }
    }
    refresh();
    timer = window.setInterval(refresh, REFRESH_INTERVAL);
    return () => window.clearInterval(timer);
  }, [jobId]);

  useEffect(() => {
    if (!exchanges.length) return;
    if (typeof Notification === 'undefined') return;
    const pending = exchanges.filter((ex) => ex.status === 'waiting_for_user');
    if (!pending.length) return;

    const permission = Notification.permission;
    if (permission === 'default') {
      Notification.requestPermission().catch(() => { });
    }
    if (Notification.permission !== 'granted') {
      return;
    }
    pending.forEach((ex) => {
      const stamp = ex.updated_at || '';
      const key = `${NOTIFY_KEY}:${jobId}:${ex.id}:${stamp}`;
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, '1');
      new Notification('オーケストレータ: 追加確認があります', {
        body: `${ex.performer?.name || '演奏者'} の確認が必要です`,
      });
    });
  }, [exchanges, jobId]);

  const pendingExchanges = useMemo(() => {
    return exchanges.filter((ex) => ex.status === 'waiting_for_user');
  }, [exchanges]);

  const handleOk = async (exchangeId: string) => {
    setSending((prev) => ({ ...prev, [exchangeId]: true }));
    const ok = await postExchangeReply(jobId, exchangeId, { decision: 'ok' });
    setSending((prev) => ({ ...prev, [exchangeId]: false }));
    if (!ok) {
      setError('送信に失敗しました');
    }
  };

  const handleNg = async (exchangeId: string) => {
    setSending((prev) => ({ ...prev, [exchangeId]: true }));
    const ok = await postExchangeReply(jobId, exchangeId, { decision: 'ng' });
    setSending((prev) => ({ ...prev, [exchangeId]: false }));
    if (!ok) {
      setError('送信に失敗しました');
    }
  };

  const handleChoiceSubmit = async (exchangeId: string) => {
    const choice = choiceDraft[exchangeId];
    if (!choice) return;
    setSending((prev) => ({ ...prev, [exchangeId]: true }));
    const ok = await postExchangeReply(jobId, exchangeId, { choice, approved: true, reply: choice });
    setSending((prev) => ({ ...prev, [exchangeId]: false }));
    if (!ok) {
      setError('送信に失敗しました');
    }
  };

  const handleFreeTextSubmit = async (exchangeId: string) => {
    const text = freeTextDraft[exchangeId];
    if (!text) return;
    setSending((prev) => ({ ...prev, [exchangeId]: true }));
    const ok = await postExchangeReply(jobId, exchangeId, { reply: text, approved: true });
    setSending((prev) => ({ ...prev, [exchangeId]: false }));
    if (!ok) {
      setError('送信に失敗しました');
    }
  };

  if (pendingExchanges.length === 0) {
    return null;
  }

  return (
    <div className="glass-light rounded-2xl border border-amber-500/30 bg-amber-500/10 overflow-hidden">
      <div className="p-4 border-b border-amber-500/20 flex items-center gap-2 text-amber-200">
        <AlertCircle size={18} />
        <span className="font-semibold">要確認</span>
        <span className="text-xs text-amber-300/80">({pendingExchanges.length}件)</span>
      </div>
      <div className="p-4 space-y-4">
        {error && <div className="text-xs text-red-400">{error}</div>}
        {pendingExchanges.map((ex) => {
          const pending = ex.pending || {};
          const pendingType = getPendingType(ex);
          const question = getQuestion(ex);
          const reason = getReason(ex);
          const showReason = Boolean(reason) && reason !== question;
          const options = pending.options || [];
          const selected = choiceDraft[ex.id] || '';
          const isSending = Boolean(sending[ex.id]);
          const alreadyReplied = Boolean(pending.user_reply) || Boolean(pending.user_choice) || pending.user_approved === true;

          return (
            <div key={ex.id} className="glass rounded-xl p-4 space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm text-slate-200">
                <span className="font-semibold">{ex.performer?.name || `演奏者 ${ex.id}`}</span>
                <span className="text-xs text-amber-300/80">
                  {pendingType === 'choice' ? '選択式' : pendingType === 'free_text' ? '自由入力' : 'OK / NG'}
                </span>
              </div>
              <div className="text-sm text-slate-100 whitespace-pre-wrap">{question}</div>
              {showReason && (
                <div className="text-xs text-amber-200/80 whitespace-pre-wrap">理由: {reason}</div>
              )}

              {pendingType === 'ok_ng' && (
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleOk(ex.id)}
                    disabled={isSending || alreadyReplied}
                    className="inline-flex items-center gap-2 bg-emerald-500/80 hover:bg-emerald-500 text-white text-sm px-4 py-2 rounded-lg disabled:opacity-60"
                  >
                    <CheckCircle2 size={16} />
                    OK
                  </button>
                  <button
                    onClick={() => handleNg(ex.id)}
                    disabled={isSending || alreadyReplied}
                    className="inline-flex items-center gap-2 bg-slate-700/70 hover:bg-slate-600 text-white text-sm px-4 py-2 rounded-lg disabled:opacity-60"
                  >
                    <XCircle size={16} />
                    NG
                  </button>
                </div>
              )}

              {pendingType === 'choice' && (
                <div className="space-y-2">
                  {options.length > 0 ? (
                    <div className="space-y-2">
                      {options.map((option) => (
                        <label key={option} className="flex items-center gap-2 text-sm text-slate-200">
                          <input
                            type="radio"
                            name={`choice-${ex.id}`}
                            value={option}
                            checked={selected === option}
                            onChange={() => setChoiceDraft((prev) => ({ ...prev, [ex.id]: option }))}
                            className="text-amber-400"
                          />
                          <span>{option}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400">選択肢が見つかりません</div>
                  )}
                  <button
                    onClick={() => handleChoiceSubmit(ex.id)}
                    disabled={isSending || alreadyReplied || !selected}
                    className="bg-amber-500/80 hover:bg-amber-500 text-white text-sm px-4 py-2 rounded-lg disabled:opacity-60"
                  >
                    {isSending ? '送信中...' : '選択を送信'}
                  </button>
                </div>
              )}

              {pendingType === 'free_text' && (
                <div className="space-y-2">
                  <textarea
                    value={freeTextDraft[ex.id] || ''}
                    onChange={(e) => setFreeTextDraft((prev) => ({ ...prev, [ex.id]: e.target.value }))}
                    placeholder="回答を入力してください..."
                    className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                    rows={3}
                  />
                  <button
                    onClick={() => handleFreeTextSubmit(ex.id)}
                    disabled={isSending || alreadyReplied || !freeTextDraft[ex.id]}
                    className="bg-amber-500/80 hover:bg-amber-500 text-white text-sm px-4 py-2 rounded-lg disabled:opacity-60"
                  >
                    {isSending ? '送信中...' : '回答を送信'}
                  </button>
                </div>
              )}

              {alreadyReplied && (
                <div className="text-xs text-emerald-300">回答済みです。反映まで少しお待ちください。</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
