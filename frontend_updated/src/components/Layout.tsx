import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

const PIPELINE_STEPS = [
  { to: '/upload', label: 'Upload Dataset' },
  { to: '/preprocessing', label: 'Preprocessing' },
  { to: '/aspect-discovery', label: 'Aspect Discovery' },
  { to: '/sentiment', label: 'Sentiment Analysis' },
  { to: '/root-cause', label: 'Root Cause' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/report', label: 'Executive Report' },
];

export function Layout() {
  const { logout } = useAuth();
  const [gpuEnabled, setGpuEnabled] = useState(true);
  const [gpuSaving, setGpuSaving] = useState(false);

  useEffect(() => {
    api.get<{ settings: { use_gpu?: boolean } }>('/settings')
      .then((res) => setGpuEnabled(res.settings.use_gpu ?? true))
      .catch(() => undefined);
  }, []);

  async function handleGpuToggle() {
    setGpuSaving(true);
    const nextValue = !gpuEnabled;
    try {
      const current = await api.get<{ settings: Record<string, unknown> }>('/settings');
      await api.post('/settings', { ...current.settings, use_gpu: nextValue });
      setGpuEnabled(nextValue);
    } finally {
      setGpuSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col bg-ink text-white/90">
        <div className="flex items-center gap-2 border-b border-white/10 px-5 py-5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent font-display text-sm font-semibold text-white">
            AI
          </div>
          <div className="font-display text-sm font-semibold text-white">Feedback Intelligence</div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              `mb-4 flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white/90'
              }`
            }
          >
            Dashboard
          </NavLink>

          <div className="mb-2 px-3 mono text-[11px] text-white/35">Pipeline</div>
          <ol className="space-y-0.5">
            {PIPELINE_STEPS.map((step, idx) => (
              <li key={step.to}>
                <NavLink
                  to={step.to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                      isActive ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white/90'
                    }`
                  }
                >
                  <span className="mono flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/20 text-[10px]">
                    {idx + 1}
                  </span>
                  {step.label}
                </NavLink>
              </li>
            ))}
          </ol>

          <div className="mt-6 border-t border-white/10 pt-3">
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white/90'
                }`
              }
            >
              Settings
            </NavLink>
            <button
              type="button"
              onClick={handleGpuToggle}
              disabled={gpuSaving}
              className="mt-2 flex w-full items-center justify-between rounded-md px-3 py-2 text-sm text-white/60 transition-colors hover:bg-white/5 hover:text-white/90 disabled:opacity-50"
            >
              <span>GPU acceleration</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${gpuEnabled ? 'bg-positive-soft text-positive' : 'bg-white/10 text-white/50'}`}>
                {gpuEnabled ? 'On' : 'Off'}
              </span>
            </button>
          </div>
        </nav>

        <div className="border-t border-white/10 p-3">
          <button
            onClick={logout}
            className="w-full rounded-md px-3 py-2 text-left text-sm text-white/60 transition-colors hover:bg-white/5 hover:text-white/90"
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto px-8 py-8">
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
