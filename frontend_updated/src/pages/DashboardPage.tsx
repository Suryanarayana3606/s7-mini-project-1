import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { MetricCard } from '../components/MetricCard';
import { EmptyState } from '../components/Progress';

interface DashboardData {
  has_data: boolean;
  total_reviews?: number;
  columns?: number;
  missing_values?: number;
  preview?: Record<string, unknown>[];
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<DashboardData>('/dataset/dashboard').then(setData).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description="A quick pulse check on your uploaded feedback dataset."
      />

      {loading && <div className="text-sm text-ink-soft/50">Loading…</div>}

      {!loading && data && !data.has_data && (
        <EmptyState
          title="No dataset uploaded yet"
          description={
            <>
              Head to <Link to="/upload" className="text-accent underline">Upload Dataset</Link> to get started.
            </>
          }
        />
      )}

      {!loading && data?.has_data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <MetricCard label="Total Reviews" value={data.total_reviews ?? 0} />
            <MetricCard label="Columns" value={data.columns ?? 0} />
            <MetricCard label="Missing Values" value={data.missing_values ?? 0} />
          </div>

          <h2 className="mt-8 mb-3 text-sm font-semibold text-ink-soft/70">Recent Reviews</h2>
          <div className="overflow-hidden rounded-lg border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="bg-canvas text-xs uppercase tracking-wide text-ink-soft/50">
                <tr>
                  {data.preview && data.preview[0] &&
                    Object.keys(data.preview[0]).map((col) => (
                      <th key={col} className="px-4 py-2 font-medium">{col}</th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {data.preview?.map((row, i) => (
                  <tr key={i} className="border-t border-line">
                    {Object.values(row).map((val, j) => (
                      <td key={j} className="max-w-xs truncate px-4 py-2 text-ink-soft/80">{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
