import { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';

interface SettingsData {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  use_gpu: boolean;
  seed_topics: string;
}

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [modelOptions, setModelOptions] = useState<Record<string, string[]>>({});
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ settings: SettingsData; model_options: Record<string, string[]> }>('/settings').then((res) => {
      setSettings(res.settings);
      setModelOptions(res.model_options);
    });
  }, []);

  async function handleSave() {
    if (!settings) return;
    setSaveError(null);
    setSaveMsg(null);
    try {
      await api.post('/settings', settings);
      setSaveMsg('Settings saved successfully!');
      setTimeout(() => setSaveMsg(null), 3000);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Settings could not be saved.');
    }
  }

  async function handleTest() {
    if (!settings) return;
    setTesting(true);
    setTestMsg(null);
    try {
      const res = await api.post<{ success: boolean; response?: string; error?: string }>('/settings/test', settings);
      setTestMsg(res.success ? { ok: true, text: res.response ?? 'Connected' } : { ok: false, text: res.error ?? 'Failed' });
    } catch (err) {
      setTestMsg({ ok: false, text: err instanceof ApiError ? err.message : 'Connection test failed.' });
    } finally {
      setTesting(false);
    }
  }

  if (!settings) return <div className="text-sm text-ink-soft/50">Loading…</div>;

  const models = modelOptions[settings.provider] ?? [];

  return (
    <div>
      <PageHeader eyebrow="Configuration" title="AI Settings" description="Configure recommendation generation and guided aspect keywords." />

      <div className="max-w-md space-y-5">
        <label className="flex items-center justify-between rounded-md border border-line bg-surface px-3 py-3 text-sm text-ink">
          <span>Use GPU acceleration for supported local models</span>
          <input
            type="checkbox"
            checked={settings.use_gpu}
            onChange={(e) => setSettings({ ...settings, use_gpu: e.target.checked })}
          />
        </label>

        <div>
          <label className="block text-xs font-medium text-ink-soft/70">LLM Provider</label>
          <select
            value={settings.provider}
            onChange={(e) => setSettings({ ...settings, provider: e.target.value, model: (modelOptions[e.target.value] ?? [])[0] ?? '' })}
            className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          >
            {Object.keys(modelOptions).map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-soft/70">Model</label>
          <select
            value={settings.model}
            onChange={(e) => setSettings({ ...settings, model: e.target.value })}
            className="mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          >
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-soft/70">Temperature: {settings.temperature}</label>
          <input
            type="range" min={0} max={1} step={0.1}
            value={settings.temperature}
            onChange={(e) => setSettings({ ...settings, temperature: Number(e.target.value) })}
            className="mt-1.5 w-full"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-soft/70">Max Tokens: {settings.max_tokens}</label>
          <input
            type="range" min={500} max={4000} step={100}
            value={settings.max_tokens}
            onChange={(e) => setSettings({ ...settings, max_tokens: Number(e.target.value) })}
            className="mt-1.5 w-full"
          />
        </div>

        <div>
          <label htmlFor="seed-topics" className="block text-xs font-medium text-ink-soft/70">Guided topic keywords (JSON)</label>
          <textarea
            id="seed-topics"
            rows={4}
            value={settings.seed_topics ?? ''}
            onChange={(e) => setSettings({ ...settings, seed_topics: e.target.value })}
            placeholder={'[["login", "password"], ["crash", "freeze"]]'}
            className="mt-1.5 w-full resize-y rounded-md border border-line bg-surface px-3 py-2 font-mono text-xs text-ink outline-none focus:border-accent"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={handleSave} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90">
            Save Settings
          </button>
          <button onClick={handleTest} disabled={testing} className="rounded-md border border-line bg-surface px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-canvas disabled:opacity-50">
            {testing ? 'Testing…' : 'Test Connection'}
          </button>
        </div>

        {saveMsg && <div className="rounded-md bg-positive-soft px-3 py-2 text-sm text-positive">{saveMsg}</div>}
        {saveError && <div className="rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{saveError}</div>}
        {testMsg && (
          <div className={`rounded-md px-3 py-2 text-sm ${testMsg.ok ? 'bg-positive-soft text-positive' : 'bg-negative-soft text-negative'}`}>
            {testMsg.text}
          </div>
        )}
      </div>
    </div>
  );
}
