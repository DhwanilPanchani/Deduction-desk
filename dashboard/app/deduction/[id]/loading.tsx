export default function DetailLoading() {
  return <main className="detail-shell" aria-label="Loading deduction detail" aria-busy="true">
    <div className="skeleton h-4 w-36 rounded" />
    <div className="mt-6 flex justify-between border-b border-[var(--line)] pb-7"><div className="w-1/2"><div className="skeleton h-3 w-28 rounded" /><div className="skeleton mt-3 h-9 w-56 rounded-lg" /><div className="skeleton mt-3 h-4 w-72 rounded" /></div><div className="w-36"><div className="skeleton ml-auto h-3 w-24 rounded" /><div className="skeleton mt-3 h-8 w-36 rounded" /></div></div>
    <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]"><div className="space-y-6"><SkeletonCard rows={3} /><SkeletonCard rows={6} /><SkeletonCard rows={3} /></div><div className="space-y-5"><SkeletonCard rows={4} /><SkeletonCard rows={3} /></div></div>
  </main>;
}

function SkeletonCard({ rows }: { rows: number }) { return <div className="card overflow-hidden"><div className="border-b border-[var(--line-soft)] bg-[var(--surface-subtle)] px-6 py-5"><div className="skeleton h-3 w-36 rounded" /></div><div className="p-6"><div className="skeleton h-5 w-44 rounded" /><div className="mt-5 grid gap-3 sm:grid-cols-2">{Array.from({ length: rows }, (_, index) => <div key={index} className="skeleton h-16 rounded-lg" />)}</div></div></div>; }
