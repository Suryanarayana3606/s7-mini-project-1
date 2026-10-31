import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { api } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { MetricCard } from '../components/MetricCard';
import { EmptyState } from '../components/Progress';
import { Badge } from '../components/Badge';
import { DownloadButton } from '../components/DownloadButton';

interface ReportData {
  has_data: boolean;
  kpis?: { reviews: number; aspects: number; negative: number; recommendations: number; departments: number };
  sentiment_distribution?: { positive: number; negative: number; neutral: number };
  top_root_causes?: { cause: string; frequency: number }[];
  top_recommendations?: { aspect: string; priority: string; department: string; recommendation: string }[];
  insights?: { highest_risk: string; top_department: string; recommendations_count: number; best_improvement: string };
  executive_summary?: string;
}

const COLORS: Record<string, string> = { positive: '#0F9D6C', neutral: '#B7791F', negative: '#C4351E' };

function getSummaryBullets(summary: string) {
  return summary
    .split(/\r?\n/)
    .flatMap((line) => {
      const text = line.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim();
      if (!text) return [];
      return text.match(/[^.!?]+(?:[.!?]+(?=\s|$)|$)/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [text];
    });
}

export function ReportPage() {
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<ReportData>('/report').then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-sm text-ink-soft/50">Loading…</div>;

  if (!data?.has_data) {
    return (
      <div>
        <PageHeader eyebrow="Step 7" title="Executive Business Report" />
        <EmptyState title="No processed dataset found" description="Complete the earlier pipeline steps first." />
      </div>
    );
  }

  const pieData = data.sentiment_distribution
    ? Object.entries(data.sentiment_distribution).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div>
      <PageHeader
        eyebrow="Step 7"
        title="Executive Business Report"
        description="AI-powered customer feedback intelligence summary."
      />

      <div className="mb-6 flex justify-end">
        <DownloadButton path="/report/export" label="Download Excel Report" fallbackName="customer-feedback-report.xlsx" />
      </div>

      <div className="grid grid-cols-5 gap-3">
        <MetricCard label="Reviews" value={data.kpis?.reviews ?? 0} />
        <MetricCard label="Aspects" value={data.kpis?.aspects ?? 0} />
        <MetricCard label="Negative" value={data.kpis?.negative ?? 0} tone="negative" />
        <MetricCard label="Recommendations" value={data.kpis?.recommendations ?? 0} />
        <MetricCard label="Departments" value={data.kpis?.departments ?? 0} />
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Sentiment Distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75}>
                {pieData.map((entry) => <Cell key={entry.name} fill={COLORS[entry.name] ?? '#999'} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Executive Insights</h2>
          <div className="space-y-2.5 text-sm">
            <div className="flex justify-between"><span className="text-ink-soft/60">Highest risk aspect</span><span className="font-medium">{data.insights?.highest_risk}</span></div>
            <div className="flex justify-between"><span className="text-ink-soft/60">Top department</span><span className="font-medium">{data.insights?.top_department}</span></div>
            <div className="flex justify-between"><span className="text-ink-soft/60">Recommendations</span><span className="font-medium">{data.insights?.recommendations_count}</span></div>
            <div className="flex justify-between"><span className="text-ink-soft/60">Best expected improvement</span><span className="font-medium">{data.insights?.best_improvement}</span></div>
          </div>
        </div>
      </div>

      {data.top_recommendations && data.top_recommendations.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Top AI Recommendations</h2>
          <div className="space-y-3">
            {data.top_recommendations.map((rec, i) => (
              <div key={i} className="rounded-lg border border-line bg-surface p-4">
                <div className="flex items-center justify-between">
                  <div className="font-medium text-ink">{rec.aspect}</div>
                  <Badge label={rec.priority} />
                </div>
                <p className="mt-1.5 text-sm text-ink-soft/80">{rec.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.executive_summary && (
        <div className="mt-6">
          <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">AI Executive Summary</h2>
          <div className="rounded-lg border border-line bg-surface p-4 text-sm leading-relaxed text-ink-soft/80">
            <ul className="list-disc space-y-2 pl-5">
              {getSummaryBullets(data.executive_summary).map((bullet, index) => (
                <li key={index}>{bullet}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
