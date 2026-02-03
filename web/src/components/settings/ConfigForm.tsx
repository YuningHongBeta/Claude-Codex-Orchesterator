import { useState, useEffect } from 'react';
import { Save, RefreshCw, AlertCircle, CheckCircle, Loader2, Shield, Plus, X } from 'lucide-react';
import { fetchConfig, updateConfig } from '../../services/api';
import type { OrchestratorConfig, TokenManagement, ClaudePermissions, CodexPermissions } from '../../types';

export function ConfigForm() {
  const [config, setConfig] = useState<OrchestratorConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchConfig();
      setConfig(data);
    } catch (err) {
      setError('設定の読み込みに失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateConfig(config);
      setSuccess('設定を保存しました');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('設定の保存に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  const updateTokenManagement = (key: keyof TokenManagement, value: number) => {
    if (!config) return;
    setConfig({
      ...config,
      token_management: {
        max_tokens: config.token_management?.max_tokens ?? 200000,
        warning_threshold: config.token_management?.warning_threshold ?? 0.75,
        compact_threshold: config.token_management?.compact_threshold ?? 0.85,
        max_compact_attempts: config.token_management?.max_compact_attempts ?? 3,
        [key]: value,
      },
    });
  };

  const updateInstrumentPool = (value: string) => {
    if (!config) return;
    const instruments = value.split(',').map(s => s.trim()).filter(Boolean);
    setConfig({ ...config, instrument_pool: instruments });
  };

  const updateClaudePermissions = (key: keyof ClaudePermissions, value: ClaudePermissions[keyof ClaudePermissions]) => {
    if (!config) return;
    setConfig({
      ...config,
      permissions: {
        ...config.permissions,
        claude: {
          mode: config.permissions?.claude?.mode ?? 'default',
          add_dirs: config.permissions?.claude?.add_dirs ?? [],
          [key]: value,
        },
      },
    });
  };

  const updateCodexPermissions = (key: keyof CodexPermissions, value: CodexPermissions[keyof CodexPermissions]) => {
    if (!config) return;
    setConfig({
      ...config,
      permissions: {
        ...config.permissions,
        codex: {
          sandbox: config.permissions?.codex?.sandbox ?? 'workspace-write',
          approval: config.permissions?.codex?.approval ?? 'never',
          add_dirs: config.permissions?.codex?.add_dirs ?? [],
          [key]: value,
        },
      },
    });
  };

  const addClaudeDir = () => {
    if (!config) return;
    const dirs = config.permissions?.claude?.add_dirs ?? [];
    updateClaudePermissions('add_dirs', [...dirs, '']);
  };

  const removeClaudeDir = (index: number) => {
    if (!config) return;
    const dirs = [...(config.permissions?.claude?.add_dirs ?? [])];
    dirs.splice(index, 1);
    updateClaudePermissions('add_dirs', dirs);
  };

  const updateClaudeDir = (index: number, value: string) => {
    if (!config) return;
    const dirs = [...(config.permissions?.claude?.add_dirs ?? [])];
    dirs[index] = value;
    updateClaudePermissions('add_dirs', dirs);
  };

  const addCodexDir = () => {
    if (!config) return;
    const dirs = config.permissions?.codex?.add_dirs ?? [];
    updateCodexPermissions('add_dirs', [...dirs, '']);
  };

  const removeCodexDir = (index: number) => {
    if (!config) return;
    const dirs = [...(config.permissions?.codex?.add_dirs ?? [])];
    dirs.splice(index, 1);
    updateCodexPermissions('add_dirs', dirs);
  };

  const updateCodexDir = (index: number, value: string) => {
    if (!config) return;
    const dirs = [...(config.permissions?.codex?.add_dirs ?? [])];
    dirs[index] = value;
    updateCodexPermissions('add_dirs', dirs);
  };

  if (loading) {
    return (
      <div className="glass rounded-2xl p-6 text-center">
        <Loader2 className="animate-spin mx-auto mb-2" size={24} />
        <p className="text-slate-400 text-sm">読み込み中...</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="glass rounded-2xl p-6">
        <div className="flex items-center gap-2 text-red-400 mb-4">
          <AlertCircle size={20} />
          <span>設定を読み込めませんでした</span>
        </div>
        <button
          onClick={loadConfig}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition-colors"
        >
          <RefreshCw size={16} />
          再読み込み
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Success/Error Messages */}
      {success && (
        <div className="flex items-center gap-2 p-3 bg-emerald-500/20 border border-emerald-500/30 rounded-xl text-emerald-400 text-sm">
          <CheckCircle size={18} />
          {success}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-xl text-red-400 text-sm">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* General Settings */}
      <div className="glass rounded-2xl p-4">
        <h3 className="text-sm font-semibold text-white mb-4">一般設定</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">言語</label>
            <select
              value={config.language || 'ja'}
              onChange={(e) => setConfig({ ...config, language: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            >
              <option value="ja">日本語</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">楽器プール (カンマ区切り)</label>
            <input
              type="text"
              value={(config.instrument_pool || []).join(', ')}
              onChange={(e) => updateInstrumentPool(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
              placeholder="ヴァイオリン, ビオラ, チェロ, フルート"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">演奏者の最大ターン数</label>
            <input
              type="number"
              min="1"
              max="10"
              value={config.max_turns_performer ?? 3}
              onChange={(e) => setConfig({ ...config, max_turns_performer: parseInt(e.target.value) || 3 })}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
          </div>
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="mix_with_conductor"
              checked={config.mix_with_conductor ?? false}
              onChange={(e) => setConfig({ ...config, mix_with_conductor: e.target.checked })}
              className="w-4 h-4 rounded bg-slate-800 border-slate-600 text-violet-500 focus:ring-violet-500/50"
            />
            <label htmlFor="mix_with_conductor" className="text-sm text-slate-300">
              指揮者によるミックスを有効化
            </label>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">停滞検出タイムアウト（秒）</label>
            <input
              type="number"
              min="30"
              max="600"
              step="30"
              value={config.stall_timeout_sec ?? 120}
              onChange={(e) => setConfig({ ...config, stall_timeout_sec: parseInt(e.target.value) || 120 })}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
            <p className="text-xs text-slate-500 mt-1">この秒数ログ更新がないと「停滞」と判定</p>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">停滞→エラー移行タイムアウト（秒）</label>
            <input
              type="number"
              min="60"
              max="3600"
              step="60"
              value={config.stall_error_timeout_sec ?? 600}
              onChange={(e) => setConfig({ ...config, stall_error_timeout_sec: parseInt(e.target.value) || 600 })}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
            <p className="text-xs text-slate-500 mt-1">停滞がこの秒数続くと「エラー」に移行（デフォルト: 10分）</p>
          </div>
        </div>
      </div>

      {/* Permissions Settings */}
      <div className="glass rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={18} className="text-emerald-400" />
          <h3 className="text-sm font-semibold text-white">パーミッション設定</h3>
        </div>
        <div className="space-y-6">
          {/* Claude Code Permissions */}
          <div className="bg-slate-800/30 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-violet-400 mb-3">Claude Code</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">パーミッションモード</label>
                <select
                  value={config.permissions?.claude?.mode ?? 'default'}
                  onChange={(e) => updateClaudePermissions('mode', e.target.value as ClaudePermissions['mode'])}
                  className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                >
                  <option value="default">default (確認あり)</option>
                  <option value="bypassPermissions">bypassPermissions (全許可)</option>
                  <option value="acceptEdits">acceptEdits (編集自動承認)</option>
                  <option value="dontAsk">dontAsk (質問なし)</option>
                </select>
                <p className="text-xs text-slate-500 mt-1">bypassPermissions でディレクトリ読み取りエラーを回避</p>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">追加許可ディレクトリ</label>
                {(config.permissions?.claude?.add_dirs ?? []).map((dir, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={dir}
                      onChange={(e) => updateClaudeDir(idx, e.target.value)}
                      placeholder="/path/to/directory"
                      className="flex-1 px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                    />
                    <button
                      type="button"
                      onClick={() => removeClaudeDir(idx)}
                      className="px-2 py-2 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 hover:bg-red-500/30 transition-colors"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addClaudeDir}
                  className="flex items-center gap-1 px-3 py-1.5 bg-slate-700/50 border border-slate-600/50 rounded-lg text-slate-300 text-xs hover:bg-slate-600/50 transition-colors"
                >
                  <Plus size={14} />
                  ディレクトリを追加
                </button>
              </div>
            </div>
          </div>

          {/* Codex Permissions */}
          <div className="bg-slate-800/30 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-fuchsia-400 mb-3">Codex</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">サンドボックスモード</label>
                <select
                  value={config.permissions?.codex?.sandbox ?? 'workspace-write'}
                  onChange={(e) => updateCodexPermissions('sandbox', e.target.value as CodexPermissions['sandbox'])}
                  className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/50"
                >
                  <option value="read-only">read-only (読み取りのみ)</option>
                  <option value="workspace-write">workspace-write (ワークスペース書き込み可)</option>
                  <option value="danger-full-access">danger-full-access (フルアクセス)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">承認ポリシー</label>
                <select
                  value={config.permissions?.codex?.approval ?? 'never'}
                  onChange={(e) => updateCodexPermissions('approval', e.target.value as CodexPermissions['approval'])}
                  className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/50"
                >
                  <option value="untrusted">untrusted (信頼コマンドのみ自動)</option>
                  <option value="on-failure">on-failure (失敗時のみ確認)</option>
                  <option value="on-request">on-request (要求時のみ確認)</option>
                  <option value="never">never (確認なし)</option>
                </select>
                <p className="text-xs text-slate-500 mt-1">never でディレクトリアクセスエラーを回避</p>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">追加許可ディレクトリ</label>
                {(config.permissions?.codex?.add_dirs ?? []).map((dir, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={dir}
                      onChange={(e) => updateCodexDir(idx, e.target.value)}
                      placeholder="/path/to/directory"
                      className="flex-1 px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/50"
                    />
                    <button
                      type="button"
                      onClick={() => removeCodexDir(idx)}
                      className="px-2 py-2 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 hover:bg-red-500/30 transition-colors"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addCodexDir}
                  className="flex items-center gap-1 px-3 py-1.5 bg-slate-700/50 border border-slate-600/50 rounded-lg text-slate-300 text-xs hover:bg-slate-600/50 transition-colors"
                >
                  <Plus size={14} />
                  ディレクトリを追加
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Token Management */}
      <div className="glass rounded-2xl p-4">
        <h3 className="text-sm font-semibold text-white mb-4">トークン管理 (自動コンパクト)</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">最大トークン数</label>
            <input
              type="number"
              min="10000"
              step="10000"
              value={config.token_management?.max_tokens ?? 200000}
              onChange={(e) => updateTokenManagement('max_tokens', parseInt(e.target.value) || 200000)}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
            <p className="text-xs text-slate-500 mt-1">コンテキストの最大サイズ</p>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              警告しきい値: {Math.round((config.token_management?.warning_threshold ?? 0.75) * 100)}%
            </label>
            <input
              type="range"
              min="0.5"
              max="0.95"
              step="0.05"
              value={config.token_management?.warning_threshold ?? 0.75}
              onChange={(e) => updateTokenManagement('warning_threshold', parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-yellow-500"
            />
            <p className="text-xs text-slate-500 mt-1">この割合に達すると警告を表示</p>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              自動コンパクトしきい値: {Math.round((config.token_management?.compact_threshold ?? 0.85) * 100)}%
            </label>
            <input
              type="range"
              min="0.6"
              max="0.99"
              step="0.01"
              value={config.token_management?.compact_threshold ?? 0.85}
              onChange={(e) => updateTokenManagement('compact_threshold', parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
            />
            <p className="text-xs text-slate-500 mt-1">この割合に達すると自動的に /compact を実行</p>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">最大コンパクト試行回数</label>
            <input
              type="number"
              min="1"
              max="10"
              value={config.token_management?.max_compact_attempts ?? 3}
              onChange={(e) => updateTokenManagement('max_compact_attempts', parseInt(e.target.value) || 3)}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
            />
            <p className="text-xs text-slate-500 mt-1">コンパクト処理の最大リトライ回数</p>
          </div>
        </div>
      </div>

      {/* Command Configuration (read-only display) */}
      <div className="glass rounded-2xl p-4">
        <h3 className="text-sm font-semibold text-white mb-4">コマンド設定</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Rewriter (Claude)</label>
            <code className="block text-xs bg-slate-800/50 p-2 rounded text-slate-300 overflow-x-auto">
              {(config.rewriter?.cmd || []).join(' ')}
            </code>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Concertmaster (Codex)</label>
            <code className="block text-xs bg-slate-800/50 p-2 rounded text-slate-300 overflow-x-auto">
              {(config.concertmaster?.cmd || []).join(' ')}
            </code>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Performer (Codex)</label>
            <code className="block text-xs bg-slate-800/50 p-2 rounded text-slate-300 overflow-x-auto">
              {(config.performer?.cmd || []).join(' ')}
            </code>
          </div>
          <p className="text-xs text-slate-500">
            コマンド設定は config.json を直接編集してください
          </p>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex gap-3">
        <button
          onClick={loadConfig}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-slate-700 rounded-xl text-white font-medium hover:bg-slate-600 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={18} />
          リセット
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-xl text-white font-medium hover:from-violet-600 hover:to-fuchsia-600 transition-colors disabled:opacity-50"
        >
          {saving ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  );
}
