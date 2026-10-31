import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { api, pollJob, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { MetricCard } from '../components/MetricCard';
import { ProgressBar, EmptyState } from '../components/Progress';
import { Badge } from '../components/Badge';
import { DownloadButton } from '../components/DownloadButton';

interface SentimentResults {
  has_results: boolean;
  sentiment_counts?: Record<string, number>;
  average_confidence?: number;
  rows?: Record<string, unknown>[];
}

const COLORS: Record<string, string> = { positive: '#0F9D6C', neutral: '#B7791F', negative: '#C4351E' };

export function SentimentPage() {
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 1, message: '' });
  const [results, setResults] = useState<SentimentResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SentimentResults>('/sentiment/results').then((res) => res.has_results && setResults(res));
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { job_id } = await api.post<{ job_id: string }>('/sentiment/run');
      await pollJob(job_id, (job) => setProgress({ current: job.current, total: job.total, message: job.message }));
      const res = await api.get<SentimentResults>('/sentiment/results');
      setResults(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sentiment analysis failed.');
    } finally {
      setRunning(false);
    }
  }

  const pieData = results?.sentiment_counts
    ? Object.entries(results.sentiment_counts).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div>
      <PageHeader
        eyebrow="Step 4"
        title="Aspect Sentiment Analysis"
        description="A dedicated aspect-based sentiment model judges sentiment toward each specific aspect in a review, not the review as a whole."
      />

      <button
        onClick={handleRun}
        disabled={running}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {running ? 'Analyzing…' : 'Run Aspect Sentiment Analysis'}
      </button>

      {running && (
        <div className="mt-5 max-w-md">
          <ProgressBar current={progress.current} total={progress.total} message={progress.message} />
        </div>
      )}

      {error && <div className="mt-4 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{error}</div>}

      {!running && !results && !error && (
        <div className="mt-6">
          <EmptyState title="No sentiment results yet" description="Run analysis once aspects have been discovered." />
        </div>
      )}

      {results?.has_results && (
        <div className="mt-8 space-y-6">
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="Positive" value={results.sentiment_counts?.positive ?? 0} tone="positive" />
            <MetricCard label="Neutral" value={results.sentiment_counts?.neutral ?? 0} />
            <MetricCard label="Negative" value={results.sentiment_counts?.negative ?? 0} tone="negative" />
            <MetricCard label="Avg Confidence" value={`${results.average_confidence ?? 0}%`} />
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Sentiment Distribution</h2>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={COLORS[entry.name] ?? '#999'} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-ink-soft/70">Review-Level Results</h2>
              <div className="flex gap-2">
                <DownloadButton path="/sentiment/export?format=csv" label="CSV" fallbackName="sentiment-analysis.csv" />
                <DownloadButton path="/sentiment/export?format=xlsx" label="Excel" fallbackName="sentiment-analysis.xlsx" />
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border border-line bg-surface">
              <table className="w-full text-left text-sm">
                <thead className="bg-canvas text-xs uppercase tracking-wide text-ink-soft/50">
                  <tr>
                    <th className="px-4 py-2 font-medium">Review</th>
                    <th className="px-4 py-2 font-medium">Aspect</th>
                    <th className="px-4 py-2 font-medium">Sentiment</th>
                  </tr>
                </thead>
                <tbody>
                  {results.rows?.slice(0, 10).map((row, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="max-w-md truncate px-4 py-2 text-ink-soft/80">{String(row.review)}</td>
                      <td className="px-4 py-2 text-ink-soft/80">{String(row.Aspect ?? row.Topic)}</td>
                      <td className="px-4 py-2"><Badge label={String(row.Sentiment)} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <button
            onClick={() => navigate('/root-cause')}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Continue to Root Cause →
          </button>
        </div>
      )}
    </div>
  );
}
