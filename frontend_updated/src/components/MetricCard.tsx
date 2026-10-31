export function MetricCard({ label, value, tone }: { label: string; value: string | number; tone?: 'positive' | 'negative' | 'accent' }) {
  const toneClass = tone === 'positive' ? 'text-positive' : tone === 'negative' ? 'text-negative' : 'text-ink';
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3.5">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-soft/60">{label}</div>
      <div className={`mt-1 font-display text-2xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}
