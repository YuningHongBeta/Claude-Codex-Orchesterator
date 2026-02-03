import { useEffect, useMemo, useState } from 'react';
import { AUTH_CONFIG, AUTH_STORAGE_KEY } from '../../constants';

interface AuthGateProps {
  children: React.ReactNode;
}

type AuthState = {
  user: string;
  hash: string;
};

const STORAGE_KEY = AUTH_STORAGE_KEY;

function normalize(text: string): string {
  return text.trim();
}

async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export function AuthGate({ children }: AuthGateProps) {
  const config = AUTH_CONFIG;
  const enabled = config.enabled && config.user && (config.pass || config.passHash);
  const [ready, setReady] = useState(!enabled);
  const [authorized, setAuthorized] = useState(!enabled);
  const [entering, setEntering] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [passInput, setPassInput] = useState('');
  const [error, setError] = useState('');

  const stored = useMemo(() => {
    if (!enabled) return null;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as AuthState;
    } catch {
      return null;
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    if (!stored) {
      setReady(true);
      return;
    }
    const isValidUser = stored.user === config.user;
    const isValidHash = config.passHash ? stored.hash === config.passHash : true;
    if (isValidUser && isValidHash) {
      setAuthorized(true);
    }
    setReady(true);
  }, [enabled, stored, config.user, config.passHash]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    const user = normalize(userInput);
    const pass = normalize(passInput);

    if (!user || !pass) {
      setError('ID とパスワードを入力してください');
      return;
    }

    if (user !== config.user) {
      setError('ID またはパスワードが違います');
      return;
    }

    if (config.passHash) {
      const hash = await sha256Hex(pass);
      if (hash !== config.passHash) {
        setError('ID またはパスワードが違います');
        return;
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ user, hash }));
    } else if (config.pass && pass !== config.pass) {
      setError('ID またはパスワードが違います');
      return;
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ user, hash: '' }));
    }

    setAuthorized(true);
    setEntering(true);
    setTimeout(() => setEntering(false), 240);
  }

  if (!enabled) {
    return <>{children}</>;
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-400">
        認証を確認中...
      </div>
    );
  }

  if (authorized) {
    return <div className={entering ? 'auth-enter' : ''}>{children}</div>;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-white px-4">
      <div className="w-full max-w-md glass-light rounded-2xl p-6 border border-slate-700/40">
        <h1 className="text-lg font-semibold mb-2">ログイン</h1>
        <p className="text-sm text-slate-400 mb-6">
          続行するにはIDとパスワードを入力してください。
        </p>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm text-slate-300 mb-1">ID</label>
            <input
              type="text"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              className="w-full bg-slate-900/60 border border-slate-700/60 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500/40"
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-300 mb-1">パスワード</label>
            <input
              type="password"
              value={passInput}
              onChange={(e) => setPassInput(e.target.value)}
              className="w-full bg-slate-900/60 border border-slate-700/60 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500/40"
              autoComplete="current-password"
            />
          </div>
          {error && <div className="text-sm text-red-400">{error}</div>}
          <button
            type="submit"
            className="w-full bg-violet-600 hover:bg-violet-500 text-white rounded-lg py-2 font-semibold"
          >
            ログイン
          </button>
        </form>
      </div>
    </div>
  );
}
