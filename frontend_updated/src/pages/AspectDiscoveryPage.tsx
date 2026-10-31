import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api, pollJob, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { MetricCard } from '../components/MetricCard';
import { ProgressBar, EmptyState } from '../components/Progress';

interface Topic {
  Topic: number;
  Count: number;
  Aspect: string;
}

interface DiscoveryResult {
  topics: Topic[];
  summary: { total_topics: number; largest_topic: number; reviews: number; noise_reviews: number };
}

export function AspectDiscoveryPage() {
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 1, message: '' });
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ has_results: boolean; topics?: Topic[] }>('/aspect-discovery/results').then((res) => {
      if (res.has_results && res.topics) {
        setResult({ topics: res.topics, summary: { total_topics: res.topics.filter(t => t.Topic !== -1).length, largest_topic: 0, reviews: 0, noise_reviews: 0 } });
      }
    });
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { job_id } = await api.post<{ job_id: string }>('/aspect-discovery/run');
      const res = await pollJob<DiscoveryResult>(job_id, (job) => {
        setProgress({ current: job.current, total: job.total, message: job.message });
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Aspect discovery failed.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 3"
        title="Dynamic Aspect Discovery"
        description="Unsupervised topic modeling (BERTopic) discovers what customers are actually talking about — no predefined categories."
      />

      <button
        onClick={handleRun}
        disabled={running}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {running ? 'Discovering aspects…' : 'Run Aspect Discovery'}
      </button>

      {running && (
        <div className="mt-5 max-w-md">
          <ProgressBar current={progress.current} total={progress.total} message={progress.message} />
        </div>
      )}

      {error && <div className="mt-4 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{error}</div>}

      {!running && !result && !error && (
        <div className="mt-6">
          <EmptyState title="No aspects discovered yet" description="Run discovery once preprocessing is complete." />
        </div>
      )}

      {result && (
        <div className="mt-8 space-y-6">
          <div className="grid grid-cols-3 gap-3">
            <MetricCard label="Topics" value={result.summary.total_topics} />
            <MetricCard label="Reviews" value={result.topics.reduce((sum, topic) => sum + Number(topic.Count), 0)} />
            <MetricCard label="Noise Reviews" value={Number(result.topics.find((topic) => topic.Topic === -1)?.Count ?? 0)} />
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Topic Frequency</h2>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={result.topics.filter((t) => t.Topic !== -1)} layout="vertical" margin={{ left: 24 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="Aspect" width={160} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="Count" fill="var(--color-accent)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <button
            onClick={() => navigate('/sentiment')}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Continue to Sentiment Analysis →
          </button>
        </div>
      )}
    </div>
  );
}
