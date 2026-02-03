import { useState } from 'react';
import { Send, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

interface SubmitFormProps {
  onSubmit: (task: string) => Promise<{ id: string }>;
}

export function SubmitForm({ onSubmit }: SubmitFormProps) {
  const [task, setTask] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || submitting) return;

    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await onSubmit(task.trim());
      setSuccess(`ジョブを作成しました (ID: ${result.id})`);
      setTask('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ジョブの作成に失敗しました');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Task input */}
      <div className="glass-light rounded-2xl p-6">
        <label className="block text-sm font-medium text-slate-300 mb-3">
          タスク内容
        </label>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="実行したいタスクを入力してください..."
          rows={6}
          className="w-full bg-slate-900/50 border border-slate-700/50 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all resize-none"
          disabled={submitting}
        />
        <p className="mt-2 text-xs text-slate-500">
          タスクは自然言語で記述できます。具体的に書くほど良い結果が得られます。
        </p>
      </div>

      {/* Success message */}
      {success && (
        <div className="glass-light rounded-xl p-4 border border-emerald-500/30 bg-emerald-500/5 animate-fade-in">
          <div className="flex items-center gap-3">
            <CheckCircle size={20} className="text-emerald-400 flex-shrink-0" />
            <p className="text-emerald-300 text-sm">{success}</p>
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="glass-light rounded-xl p-4 border border-red-500/30 bg-red-500/5 animate-fade-in">
          <div className="flex items-center gap-3">
            <AlertCircle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        </div>
      )}

      {/* Submit button */}
      <button
        type="submit"
        disabled={!task.trim() || submitting}
        className="w-full glass-light rounded-xl py-4 px-6 font-semibold text-white flex items-center justify-center gap-3 hover:bg-slate-700/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 group"
      >
        {submitting ? (
          <>
            <Loader2 size={20} className="animate-spin" />
            <span>送信中...</span>
          </>
        ) : (
          <>
            <Send size={20} className="group-hover:translate-x-1 transition-transform" />
            <span>ジョブを投入</span>
          </>
        )}
      </button>
    </form>
  );
}
