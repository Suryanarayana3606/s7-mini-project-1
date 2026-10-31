import type { ReactNode } from 'react';

export function ProgressBar({ current, total, message }: { current: number; total: number; message?: string }) {
  const pct = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  return (
    <div className="space-y-2">
      {message && <div className="text-sm text-ink-soft/80">{message}</div>}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full bg-accent transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mono text-xs text-ink-soft/50">{pct}%</div>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface/60 px-6 py-10 text-center">
      <div className="text-sm font-medium text-ink">{title}</div>
      {description && <div className="mt-1 text-sm text-ink-soft/60">{description}</div>}
    </div>
  );
}
