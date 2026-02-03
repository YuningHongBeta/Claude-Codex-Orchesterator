import { NavLink } from 'react-router-dom';
import { Home, Send, ListTodo, Settings } from 'lucide-react';

const navItems = [
  { to: '/', icon: Home, label: 'ホーム' },
  { to: '/submit', icon: Send, label: '投入' },
  { to: '/jobs', icon: ListTodo, label: 'ジョブ' },
  { to: '/settings', icon: Settings, label: '設定' },
];

export function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 glass border-t border-slate-700/50 safe-bottom z-20">
      <div className="max-w-4xl mx-auto flex items-center justify-around h-16">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center px-6 py-2 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'text-violet-400 bg-violet-500/10'
                  : 'text-slate-400 hover:text-slate-200'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
                <span className="text-xs mt-1 font-medium">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
