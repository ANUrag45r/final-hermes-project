import { Card } from "@/components/ui/card";

export function SummaryCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <Card className="animate-rise p-5">
      <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/45">
        {label}
      </div>
      <div className="mt-2 font-display text-4xl font-medium text-ink">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-ink/50">{hint}</div>}
    </Card>
  );
}
