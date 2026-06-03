export default function MetricCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-4">
      <div className="text-2xl font-bold text-white" style={{ fontFamily: 'Red Hat Display' }}>{value}</div>
      <div className="text-xs text-brand-muted uppercase tracking-wider mt-1">{label}</div>
      {sub && <div className="text-xs text-brand-muted mt-0.5">{sub}</div>}
    </div>
  );
}
