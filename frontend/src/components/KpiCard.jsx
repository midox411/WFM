export default function KpiCard({ label, value, sub, accent = false, loading = false }) {
  if (loading) {
    return (
      <div className="kpi-card">
        <div className="skeleton h-3 w-24" />
        <div className="skeleton h-8 w-28 mt-2" />
        <div className="skeleton h-3 w-16 mt-1" />
      </div>
    )
  }
  return (
    <div className={`kpi-card group ${accent ? 'bg-accent-600 border-accent-600' : ''}`}>
      <p className={`text-xs font-medium tracking-wide uppercase ${accent ? 'text-accent-100' : 'text-neutral-400'}`}>
        {label}
      </p>
      <p className={`text-2xl font-semibold tabular-nums mt-1 ${accent ? 'text-white' : 'text-neutral-800'}`}>
        {value ?? '—'}
      </p>
      {sub && (
        <p className={`text-xs mt-0.5 ${accent ? 'text-accent-100' : 'text-neutral-400'}`}>{sub}</p>
      )}
    </div>
  )
}
