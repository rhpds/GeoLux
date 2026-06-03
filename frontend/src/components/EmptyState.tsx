export default function EmptyState({ message = 'No data available.' }: { message?: string }) {
  return <p className="text-brand-muted text-sm py-4">{message}</p>;
}
