export default function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return <p className="text-brand-muted text-sm py-4">{message}</p>;
}
