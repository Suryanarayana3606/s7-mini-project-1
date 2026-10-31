import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';

interface PreviewResponse {
  columns: string[];
  detected_review_column: string | null;
  preview: Record<string, unknown>[];
  row_count: number;
}

interface ConfirmResponse {
  success: boolean;
  rows: number;
  removed_empty_reviews: number;
  duplicates_removed: number;
  missing_values_filled: number;
}

export function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [reviewColumn, setReviewColumn] = useState<string>('');
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<ConfirmResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleFileChange(f: File) {
    setFile(f);
    setPreview(null);
    setResult(null);
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', f);
      const res = await api.postForm<PreviewResponse>('/dataset/preview', form);
      setPreview(res);
      setReviewColumn(res.detected_review_column ?? res.columns[0]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to read file.');
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.postForm<ConfirmResponse>(
        `/dataset/confirm?review_column=${encodeURIComponent(reviewColumn)}`,
        form,
      );
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save dataset.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Step 1"
        title="Upload Dataset"
        description="Upload a customer feedback CSV file for analysis."
      />

      {!preview && (
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-line bg-surface px-6 py-14 text-center transition-colors hover:border-accent">
          <div className="text-sm font-medium text-ink">Click to choose a CSV file</div>
          <div className="mt-1 text-xs text-ink-soft/50">or drag and drop it here</div>
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
          />
        </label>
      )}

      {busy && <div className="mt-4 text-sm text-ink-soft/50">Working…</div>}
      {error && <div className="mt-4 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{error}</div>}

      {preview && !result && (
        <div className="mt-6 space-y-5">
          <div>
            <label className="block text-xs font-medium text-ink-soft/70">Which column contains the review text?</label>
            <select
              value={reviewColumn}
              onChange={(e) => setReviewColumn(e.target.value)}
              className="mt-1.5 w-72 rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            >
              {preview.columns.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            {preview.detected_review_column && (
              <div className="mt-1.5 text-xs text-positive">Auto-detected: {preview.detected_review_column}</div>
            )}
          </div>

          <div className="max-h-80 overflow-auto rounded-lg border border-line bg-surface">
            <table className="w-max min-w-full text-left text-sm">
              <thead className="bg-canvas text-xs uppercase tracking-wide text-ink-soft/50">
                <tr>{preview.columns.map((c) => <th key={c} className="sticky top-0 whitespace-nowrap bg-canvas px-4 py-2 font-medium">{c}</th>)}</tr>
              </thead>
              <tbody>
                {preview.preview.map((row, i) => (
                  <tr key={i} className="border-t border-line">
                    {preview.columns.map((c) => (
                      <td key={c} className="max-w-xs truncate whitespace-nowrap px-4 py-2 text-ink-soft/80">{String(row[c] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-soft/80">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            I confirm this column contains the customer review text.
          </label>

          <button
            disabled={!confirmed || busy}
            onClick={handleConfirm}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            Save Dataset & Continue
          </button>
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="rounded-md bg-positive-soft px-4 py-3 text-sm text-positive">
            Dataset saved — {result.rows} rows ready for analysis.
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm text-ink-soft/70">
            <div>Empty reviews removed: <span className="font-medium text-ink">{result.removed_empty_reviews}</span></div>
            <div>Duplicates removed: <span className="font-medium text-ink">{result.duplicates_removed}</span></div>
            <div>Missing values filled: <span className="font-medium text-ink">{result.missing_values_filled}</span></div>
          </div>

          <button
            onClick={() => navigate('/preprocessing')}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Continue to Preprocessing →
          </button>
        </div>
      )}
    </div>
  );
}
