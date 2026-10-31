const TONE_MAP: Record<string, string> = {
  critical: 'bg-negative-soft text-negative',
  negative: 'bg-negative-soft text-negative',
  high: 'bg-neutral-soft text-neutral-tone',
  medium: 'bg-accent-soft text-accent',
  neutral: 'bg-accent-soft text-accent',
  low: 'bg-positive-soft text-positive',
  positive: 'bg-positive-soft text-positive',
};

export function Badge({ label }: { label: string }) {
  const tone = TONE_MAP[label?.toLowerCase()] ?? 'bg-line text-ink-soft';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      {label}
    </span>
  );
}
