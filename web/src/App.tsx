import { HashRouter, Routes, Route } from 'react-router-dom';
import { Header, BottomNav } from './components/layout';
import { AuthGate } from './components/auth';
import { Home, Submit, Jobs, JobDetailPage, Settings } from './pages';

export default function App() {
  return (
    <HashRouter>
      <AuthGate>
        <div className="min-h-screen bg-slate-900 text-white">
          <Header />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/submit" element={<Submit />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/jobs/:id" element={<JobDetailPage />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
          <BottomNav />
        </div>
      </AuthGate>
    </HashRouter>
  );
}
