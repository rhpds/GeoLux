const VARIANTS: Record<string, string> = {
  pass: 'bg-green-800 text-green-200',
  fail: 'bg-red-800 text-red-200',
  inconclusive: 'bg-gray-700 text-gray-300',
  unclassifiable: 'bg-amber-800 text-amber-200',
  stable_pass: 'bg-green-800 text-green-200',
  stable_fail: 'bg-red-800 text-red-200',
  unstable_pass: 'bg-amber-800 text-amber-200',
  unstable_fail: 'bg-red-900 text-red-300',
  validated: 'bg-green-800 text-green-200',
  falsified: 'bg-red-800 text-red-200',
  nano: 'bg-blue-800 text-blue-200',
  micro: 'bg-purple-800 text-purple-200',
  macro: 'bg-orange-800 text-orange-200',
  critical: 'bg-red-800 text-red-200',
  major: 'bg-amber-800 text-amber-200',
  minor: 'bg-gray-700 text-gray-300',
  live: 'bg-green-600 text-white',
  synthetic: 'bg-amber-600 text-white',
  replay: 'bg-blue-600 text-white',
};

export default function Badge({ variant, children }: { variant: string; children?: React.ReactNode }) {
  const cls = VARIANTS[variant] ?? 'bg-gray-700 text-gray-300';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${cls}`}>
      {children ?? variant}
    </span>
  );
}
