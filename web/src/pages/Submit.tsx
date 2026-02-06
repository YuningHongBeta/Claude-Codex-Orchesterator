import { useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { PageContainer } from '../components/layout';
import { SubmitForm } from '../components/submit';
import { useCreateJob } from '../hooks/useJobs';

export function Submit() {
  const navigate = useNavigate();
  const { submit } = useCreateJob();

  const handleSubmit = async (task: string, expertReview?: boolean) => {
    const result = await submit(task, expertReview);
    if (result) {
      // Navigate to job detail after short delay
      setTimeout(() => {
        navigate(`/jobs/${result.id}`);
      }, 1500);
      return { id: result.id };
    }
    throw new Error('ジョブの作成に失敗しました');
  };

  return (
    <PageContainer>
      <div className="space-y-6">
        {/* Header */}
        <div className="text-center py-4">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 mb-3">
            <Sparkles size={28} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-white mb-1">新規ジョブ作成</h1>
          <p className="text-slate-400 text-sm">
            AIに実行させたいタスクを入力
          </p>
        </div>

        {/* Form */}
        <SubmitForm onSubmit={handleSubmit} />

        {/* Tips */}
        <div className="glass rounded-xl p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-2">💡 ヒント</h3>
          <ul className="text-xs text-slate-400 space-y-1">
            <li>• 具体的な目標や期待する結果を明記する</li>
            <li>• 必要なファイルやディレクトリを指定する</li>
            <li>• 複雑なタスクは小さく分割して投入する</li>
          </ul>
        </div>
      </div>
    </PageContainer>
  );
}
