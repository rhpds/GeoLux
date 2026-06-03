export default function SectionHeader({ children }: { children: React.ReactNode }) {
  return <h2 className="text-xs text-brand-muted uppercase tracking-wider font-bold mb-3">{children}</h2>;
}
