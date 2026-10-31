export function PageHeader({ eyebrow, title, description }: { eyebrow?: string; title: string; description?: string }) {
  return (
    <div className="mb-6">
      {eyebrow && <div className="mono text-xs text-accent">{eyebrow}</div>}
      <h1 className="mt-1 text-2xl font-semibold text-ink">{title}</h1>
      {description && <p className="mt-1.5 max-w-2xl text-sm text-ink-soft/70">{description}</p>}
    </div>
  );
}
