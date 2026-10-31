import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api, pollJob, ApiError } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { MetricCard } from '../components/MetricCard';
import { ProgressBar, EmptyState } from '../components/Progress';
import { Badge } from '../components/Badge';

interface Evidence {
  phrase: string;
  review: string;
  confidence: number | null;
}

interface Recommendation {
  rec_id: string;
  aspect: string;
  priority: string;
  department: string;
  recommendation: string;
  business_impact: string;
  expected_improvement: string;
  status: 'Pending' | 'Accepted' | 'Rejected' | 'Implemented';
  reviewer_note?: string;
  evidence?: Evidence[];
}

interface FeedbackStats {
  total: number;
  by_status: Record<string, number>;
  acceptance_rate: number | null;
  by_department: { department: string; total: number; accepted: number; acceptance_rate: number | null }[];
}

interface RecoResults {
  has_results: boolean;
  kpis?: Record<string, number>;
  priority_distribution?: { priority: string; count: number }[];
  recommendations?: Recommendation[];
  executive_summary?: string;
  feedback_stats?: FeedbackStats;
}

const STATUS_OPTIONS: Recommendation['status'][] = ['Pending', 'Accepted', 'Rejected', 'Implemented'];

const STATUS_TONE: Record<string, string> = {
  Pending: 'bg-line text-ink-soft',
  Accepted: 'bg-positive-soft text-positive',
  Rejected: 'bg-negative-soft text-negative',
  Implemented: 'bg-accent-soft text-accent',
};

const PRIORITY_LEVELS = ['Critical', 'High', 'Medium', 'Low'] as const;
type Priority = (typeof PRIORITY_LEVELS)[number];

function expectedImprovementMidpoint(value: string) {
  const values = value.match(/\d+(?:\.\d+)?/g)?.map(Number);
  return values?.length ? values.reduce((total, number) => total + number, 0) / values.length : null;
}

function getSummaryBullets(summary: string) {
  return summary
    .split(/\r?\n/)
    .flatMap((line) => {
      const text = line.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim();
      if (!text) return [];
      return text.match(/[^.!?]+(?:[.!?]+(?=\s|$)|$)/g)?.map((sentence) => sentence.trim()).filter(Boolean) ?? [text];
    });
}

export function RecommendationPage() {
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 1, message: '' });
  const [results, setResults] = useState<RecoResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openEvidence, setOpenEvidence] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [selectedPriorities, setSelectedPriorities] = useState<Set<Priority> | null>(null);
  const [improvementOrder, setImprovementOrder] = useState<'highest' | 'lowest'>('highest');

  useEffect(() => {
    api.get<RecoResults>('/recommendations/results').then((res) => res.has_results && setResults(res));
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { job_id } = await api.post<{ job_id: string }>('/recommendations/run');
      const res = await pollJob<RecoResults>(job_id, (job) =>
        setProgress({ current: job.current, total: job.total, message: job.message }),
      );
      setResults(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Recommendation generation failed.');
    } finally {
      setRunning(false);
    }
  }

  async function handleStatusChange(recId: string, status: Recommendation['status']) {
    setSavingId(recId);
    try {
      const res = await api.patch<{ success: boolean; feedback_stats: FeedbackStats }>(
        `/recommendations/${recId}/status`,
        { status },
      );
      setResults((prev) => {
        if (!prev?.recommendations) return prev;
        return {
          ...prev,
          feedback_stats: res.feedback_stats,
          recommendations: prev.recommendations.map((r) => (r.rec_id === recId ? { ...r, status } : r)),
        };
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save reviewer decision.');
    } finally {
      setSavingId(null);
    }
  }

  function handlePriorityToggle(priority: Priority, checked: boolean) {
    setSelectedPriorities((current) => {
      const next = current === null ? new Set<Priority>() : new Set(current);
      if (checked) next.add(priority);
      else next.delete(priority);
      return next.size === PRIORITY_LEVELS.length ? null : next;
    });
  }

  const stats = results?.feedback_stats;
  const recommendations = results?.recommendations ?? [];
  const priorityCounts: Record<Priority, number> = {
    Critical: results?.kpis?.Critical ?? 0,
    High: results?.kpis?.High ?? 0,
    Medium: results?.kpis?.Medium ?? 0,
    Low: results?.kpis?.Low ?? 0,
  };
  const visibleRecommendations = recommendations
    .filter((recommendation) => selectedPriorities === null || selectedPriorities.has(recommendation.priority as Priority))
    .slice()
    .sort((left, right) => {
      const leftValue = expectedImprovementMidpoint(left.expected_improvement);
      const rightValue = expectedImprovementMidpoint(right.expected_improvement);
      if (leftValue === null) return rightValue === null ? 0 : 1;
      if (rightValue === null) return -1;
      return improvementOrder === 'highest' ? rightValue - leftValue : leftValue - rightValue;
    });
  const priorityGroups = PRIORITY_LEVELS
    .filter((priority) => selectedPriorities === null || selectedPriorities.has(priority))
    .map((priority) => ({
      priority,
      recommendations: visibleRecommendations.filter((recommendation) => recommendation.priority === priority),
    }))
    .filter((group) => group.recommendations.length > 0);

  return (
    <div>
      <PageHeader
        eyebrow="Step 6"
        title="AI Recommendation Engine"
        description="LLM-generated business recommendations grounded in the root causes extracted above."
      />

      <button
        onClick={handleRun}
        disabled={running}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {running ? 'Generating…' : 'Generate Recommendations'}
      </button>

      {running && (
        <div className="mt-5 max-w-md">
          <ProgressBar current={progress.current} total={progress.total} message={progress.message} />
        </div>
      )}

      {error && <div className="mt-4 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative">{error}</div>}

      {!running && !results && !error && (
        <div className="mt-6">
          <EmptyState title="No recommendations yet" description="Generate them once root cause analysis is complete." />
        </div>
      )}

      {results?.has_results && (
        <div className="mt-8 space-y-6">
          {/* Reviewer feedback / acceptance-rate summary — closes the loop
              between "AI generated a suggestion" and "was it actually useful". */}
          {stats && stats.total > 0 && (
            <div className="rounded-lg border border-line bg-surface p-4">
              <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Reviewer Feedback</h2>
              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="Accepted" value={stats.by_status.Accepted ?? 0} tone="positive" />
                <MetricCard label="Rejected" value={stats.by_status.Rejected ?? 0} tone="negative" />
                <MetricCard label="Pending Review" value={stats.by_status.Pending ?? 0} />
                <MetricCard
                  label="Acceptance Rate"
                  value={stats.acceptance_rate !== null ? `${Math.round(stats.acceptance_rate * 100)}%` : '—'}
                />
              </div>
              {stats.by_department.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-soft/60">
                  {stats.by_department.map((d) => (
                    <span key={d.department} className="rounded-full bg-canvas px-2.5 py-1">
                      {d.department}: {d.accepted}/{d.total} accepted
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {results.priority_distribution && results.priority_distribution.length > 0 && (
            <div className="rounded-lg border border-line bg-surface p-4">
              <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Priority Distribution</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={results.priority_distribution}>
                  <XAxis dataKey="priority" tick={{ fontSize: 12 }} />
                  <YAxis hide />
                  <Tooltip />
                  <Bar dataKey="count" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft/80">
              <input
                type="checkbox"
                checked={selectedPriorities === null}
                onChange={(event) => setSelectedPriorities(event.target.checked ? null : new Set())}
                className="accent-accent"
              />
              Overall <span className="text-xs text-ink-soft/50">({recommendations.length})</span>
            </label>
            {PRIORITY_LEVELS.map((priority) => (
              <label key={priority} className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft/80">
                <input
                  type="checkbox"
                  checked={selectedPriorities?.has(priority) ?? false}
                  onChange={(event) => handlePriorityToggle(priority, event.target.checked)}
                  className="accent-accent"
                />
                {priority} <span className="text-xs text-ink-soft/50">({priorityCounts[priority]})</span>
              </label>
            ))}
          </div>

          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink-soft/70">
                {selectedPriorities === null
                  ? 'Overall Recommendations'
                  : selectedPriorities.size === 1
                    ? `${Array.from(selectedPriorities)[0]} Priority Recommendations`
                    : 'Filtered Recommendations'}
                <span className="ml-2 font-normal">({visibleRecommendations.length})</span>
              </h2>
              <label className="flex items-center gap-2 text-xs text-ink-soft/60">
                Sort expected improvement
                <select
                  value={improvementOrder}
                  onChange={(event) => setImprovementOrder(event.target.value as 'highest' | 'lowest')}
                  className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-ink outline-none focus:border-accent"
                >
                  <option value="highest">Highest first</option>
                  <option value="lowest">Lowest first</option>
                </select>
              </label>
            </div>
            <div className="space-y-5">
              {priorityGroups.map((group) => (
                <section key={group.priority}>
                  <h3 className="mb-2 text-xs font-semibold uppercase text-ink-soft/60">
                    {group.priority} Priority <span className="ml-1 font-normal">({group.recommendations.length})</span>
                  </h3>
                  <div className="space-y-3">
                    {group.recommendations.map((rec) => {
                const hasEvidence = rec.evidence && rec.evidence.length > 0;
                const evidenceOpen = openEvidence === rec.rec_id;
                return (
                  <div key={rec.rec_id} className="rounded-lg border border-line bg-surface p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-ink">{rec.aspect}</div>
                      <div className="flex items-center gap-2">
                        <Badge label={rec.priority} />
                        <span className="text-xs text-ink-soft/50">{rec.department}</span>
                      </div>
                    </div>
                    <p className="mt-2 text-sm text-ink-soft/80">{rec.recommendation}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-ink-soft/50">
                      <span>Impact: {rec.business_impact}</span>
                      <span>Expected: {rec.expected_improvement}</span>
                      {hasEvidence && (
                        <button
                          onClick={() => setOpenEvidence(evidenceOpen ? null : rec.rec_id)}
                          className="font-medium text-accent hover:underline"
                        >
                          {evidenceOpen ? 'Hide' : 'Why this recommendation?'}
                        </button>
                      )}
                    </div>

                    {/* Explainability panel: the actual customer reviews +
                        root-cause phrases this recommendation was grounded in. */}
                    {evidenceOpen && hasEvidence && (
                      <div className="mt-3 space-y-2 rounded-md bg-canvas p-3">
                        {rec.evidence!.map((ev, i) => (
                          <div key={i} className="text-xs">
                            <span className="rounded bg-accent-soft px-1.5 py-0.5 font-medium text-accent">
                              {ev.phrase}
                            </span>
                            {ev.confidence !== null && (
                              <span className="ml-2 text-ink-soft/40">{ev.confidence}% confidence negative</span>
                            )}
                            <p className="mt-1 italic text-ink-soft/70">"{ev.review}"</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Reviewer feedback loop */}
                    <div className="mt-3 flex items-center gap-2 border-t border-line pt-3">
                      <span className="text-xs text-ink-soft/50">Status:</span>
                      {STATUS_OPTIONS.map((status) => (
                        <button
                          key={status}
                          disabled={savingId === rec.rec_id}
                          onClick={() => handleStatusChange(rec.rec_id, status)}
                          className={`rounded-full px-2.5 py-1 text-xs font-medium transition-opacity disabled:opacity-50 ${
                            rec.status === status ? STATUS_TONE[status] : 'text-ink-soft/40 hover:bg-canvas'
                          }`}
                        >
                          {status}
                        </button>
                      ))}
                    </div>
                  </div>
                );
                    })}
                  </div>
                </section>
              ))}
              {visibleRecommendations.length === 0 && (
                <EmptyState
                  title={recommendations.length === 0 ? 'No recommendations were generated' : 'No priorities selected'}
                  description={recommendations.length === 0 ? 'Check your LLM provider settings and try again.' : 'Select a priority or Overall to show recommendations.'}
                />
              )}
            </div>
          </div>

          {results.executive_summary && (
            <div>
              <h2 className="mb-3 text-sm font-semibold text-ink-soft/70">Executive Summary</h2>
              <div className="rounded-lg border border-line bg-surface p-4 text-sm leading-relaxed text-ink-soft/80">
                <ul className="list-disc space-y-2 pl-5">
                  {getSummaryBullets(results.executive_summary).map((bullet, index) => (
                    <li key={index}>{bullet}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <button
            onClick={() => navigate('/report')}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Continue to Executive Report →
          </button>
        </div>
      )}
    </div>
  );
}
