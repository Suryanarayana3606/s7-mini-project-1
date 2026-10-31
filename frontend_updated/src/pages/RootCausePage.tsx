import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api, pollJob, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { MetricCard } from '../components/MetricCard';
import { ProgressBar, EmptyState } from '../components/Progress';
import { DownloadButton } from '../components/DownloadButton';

interface RootCauseResults {
  has_results: boolean;
  summary?: { total_aspects: number; negative_reviews: number; root_causes: number; top_aspect: string };
  table?: { Aspect: string; 'Negative Reviews': number; 'Root Causes': string[] }[];
  top_causes?: { 'Root Cause': string; Frequency: number }[];
}

export function RootCausePage() {
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 1, message: '' });
  const [results, setResults] = useState<RootCauseResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<RootCauseResults>('/rootcause/results').then((res) => res.has_results && setResults(res));
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { job_id } = await api.post<{ job_id: string }>('/rootcause/run');
      const res = await pollJob<RootCauseResults>(job_id, (job) =>
        setProgress({ current: job.current, total: job.total, message: job.message }),
      );
      setResults(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Root cause analysis failed.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 5"
        title="AI Root Cause Analysis"
        description="TF-IDF phrase ranking over negative reviews surfaces the specific complaints behind each aspect."
      />

      <button
        onClick={handleRun}
        disabled={running}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {running ? 'Analyzing…' : 'Start Root Cause Analysis'}
      </button>

      {running && (
        <div className="mt-5 max-w-md">
          <ProgressBar current={progress.current} total={progress.total} message={progress.message} />
        </div>
      )}

      {error && <div className="mt-4 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{error}</div>}

      {!running && !results && !error && (
        <div className="mt-6">
          <EmptyState title="No root cause results yet" description="Run analysis once sentiment scoring is complete." />
        </div>
      )}

      {results?.has_results && results.summary && (
        <div className="mt-8 space-y-6">
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="Aspects" value={results.summary.total_aspects} />
            <MetricCard label="Negative Reviews" value={results.summary.negative_reviews} tone="negative" />
            <MetricCard label="Root Causes" value={results.summary.root_causes} />
            <MetricCard label="Top Aspect" value={results.summary.top_aspect} />
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Top Root Causes</h2>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={results.top_causes} layout="vertical" margin={{ left: 24 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="Root Cause" width={180} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="Frequency" fill="var(--color-negative)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-ink-soft/70">Root Cause Table</h2>
              <div className="flex gap-2">
                <DownloadButton path="/rootcause/export?format=csv" label="CSV" fallbackName="root-cause-analysis.csv" />
                <DownloadButton path="/rootcause/export?format=xlsx" label="Excel" fallbackName="root-cause-analysis.xlsx" />
              </div>
            </div>
            <div className="space-y-3">
              {results.table?.map((row) => (
                <div key={row.Aspect} className="rounded-lg border border-line bg-surface p-4">
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-ink">{row.Aspect}</div>
                    <div className="text-xs text-ink-soft/50">{row['Negative Reviews']} negative reviews</div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {row['Root Causes'].map((cause) => (
                      <span key={cause} className="rounded-full bg-canvas px-2.5 py-1 text-xs text-ink-soft/70">
                        {cause}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => navigate('/recommendations')}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Continue to Recommendations →
          </button>
        </div>
      )}
    </div>
  );
}
