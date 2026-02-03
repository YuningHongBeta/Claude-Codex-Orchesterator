import { LogOut, Zap } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AUTH_CONFIG, AUTH_STORAGE_KEY } from '../../constants';

export function Header() {
  const showLogout = AUTH_CONFIG.enabled;

  const handleLogout = () => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    window.location.reload();
  };

  return (
    <header className="glass sticky top-0 z-10 px-4 py-4 border-b border-slate-700/50">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
            <Zap size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Orchestrator</h1>
            <p className="text-xs text-slate-400">Claude × Codex</p>
          </div>
        </Link>
        {showLogout && (
          <button
            onClick={handleLogout}
            className="inline-flex items-center gap-2 text-xs text-slate-300 hover:text-white border border-slate-700/60 px-3 py-2 rounded-full transition-colors"
          >
            <LogOut size={14} />
            ログアウト
          </button>
        )}
      </div>
    </header>
  );
}
