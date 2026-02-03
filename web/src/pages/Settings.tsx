import { Settings as SettingsIcon } from 'lucide-react';
import { PageContainer } from '../components/layout';
import { ConfigForm } from '../components/settings';
import { TokenStatus } from '../components/settings/TokenStatus';

export function Settings() {
  return (
    <PageContainer>
      <div className="space-y-6">
        {/* Header */}
        <div className="text-center py-4">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-slate-600 to-slate-700 mb-3">
            <SettingsIcon size={28} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-white mb-1">設定</h1>
          <p className="text-slate-400 text-sm">
            Orchestrator の構成を管理
          </p>
        </div>

        {/* Token Status */}
        <TokenStatus />

        {/* Config Form */}
        <ConfigForm />
      </div>
    </PageContainer>
  );
}
