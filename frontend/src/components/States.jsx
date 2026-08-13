export function Skeleton({ className = '', lines = 1 }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-4 w-full" />
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }) {
  return (
    <div className={`card ${className}`}>
      <div className="skeleton h-3 w-24 mb-3" />
      <div className="skeleton h-8 w-32 mb-1" />
      <div className="skeleton h-3 w-16" />
    </div>
  )
}

export function ErrorState({ message }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center text-red-500 text-lg">!</div>
      <p className="text-sm font-medium text-neutral-700">Impossible de charger les données</p>
      <p className="text-xs text-neutral-400 max-w-xs">{message}</p>
    </div>
  )
}

export function EmptyState({ message = 'Aucun résultat disponible.', hint }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <div className="w-10 h-10 rounded-full bg-surface-100 flex items-center justify-center text-2xl">—</div>
      <p className="text-sm font-medium text-neutral-600">{message}</p>
      {hint && <p className="text-xs text-neutral-400 max-w-xs">{hint}</p>}
    </div>
  )
}
