import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, pollJob, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { ProgressBar } from '../components/Progress';

interface RunResult {
  success: boolean;
  reason?: string;
  rows?: number;
  sample?: { review: string; clean_review: string }[];
}

export function PreprocessingPage() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 1, message: '' });
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ is_preprocessed: boolean; row_count: number; sample?: RunResult['sample'] }>('/preprocessing/status')
      .then((status) => {
        if (status.is_preprocessed) {
          setResult({ success: true, rows: status.row_count, sample: status.sample ?? [] });
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load saved preprocessing results.'));
  }, []);

  async function handleRun() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const { job_id } = await api.post<{ job_id: string }>('/preprocessing/run');
      const res = await pollJob<RunResult>(job_id, (job) => {
        setProgress({ current: job.current, total: job.total, message: job.message });
      });
      if (!res.success) setError(res.reason ?? 'Preprocessing failed.');
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Preprocessing failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 2"
        title="Text Preprocessing"
        description="Lowercase, strip HTML/URLs/emails/numbers/punctuation, remove stopwords, and lemmatize each review before topic modeling. Runs as a batched background job so it stays fast on large datasets."
      />

      <button
        onClick={handleRun}
        disabled={busy}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {busy ? 'Cleaning reviews…' : 'Run Preprocessing'}
      </button>

      {busy && (
        <div className="mt-5 max-w-md">
          <ProgressBar current={progress.current} total={progress.total} message={progress.message} />
        </div>
      )}

      {error && <div className="mt-4 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{error}</div>}

      {result?.success && (
        <div className="mt-6 space-y-5">
          <div className="rounded-md bg-positive-soft px-4 py-3 text-sm text-positive">
            Preprocessing complete — {result.rows} reviews cleaned.
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink-soft/70">Before / After</h2>
            <div className="space-y-3">
              {result.sample?.slice(0, 5).map((row, i) => (
                <div key={i} className="rounded-lg border border-line bg-surface p-3 text-sm">
                  <div className="text-ink-soft/60">{row.review}</div>
                  <div className="mono mt-1.5 text-accent">{row.clean_review}</div>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => navigate('/aspect-discovery')}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Continue to Aspect Discovery →
          </button>
        </div>
      )}
    </div>
  );
}
