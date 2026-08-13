import { useState, useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'
import { getForecastIntraday } from '../api'
import { useFetch } from '../hooks/useFetch'
import { formatSlotLabel, fmt } from '../utils'
import { ErrorState, EmptyState } from '../components/States'

const HORIZONS = [
  { label: '1 jour (96 slots)', value: 96 },
  { label: '7 jours', value: 672 },
  { label: '30 jours', value: 2880 },
]

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-neutral-100 rounded-lg shadow-card-hover px-3 py-2 text-xs">
      <p className="text-neutral-400 mb-1">{label}</p>
      <p className="font-semibold text-neutral-800">{fmt(payload[0].value)} appels</p>
    </div>
  )
}

export default function Forecasting() {
  const [horizon, setHorizon] = useState(HORIZONS[0])
  const { data, loading, error } = useFetch(() => getForecastIntraday(horizon.value), [horizon.value])

  const chartData = useMemo(() => {
    if (!data?.data?.length) return []
    return data.data.map(r => ({
      time: formatSlotLabel(r.interval_15min),
      volume: r.call_volume ?? r.volume ?? r.total_calls ?? 0,
    }))
  }, [data])

  const stats = useMemo(() => {
    if (!chartData.length) return null
    const values = chartData.map(r => r.volume)
    return {
      max: Math.max(...values),
      min: Math.min(...values),
      avg: values.reduce((s, v) => s + v, 0) / values.length,
    }
  }, [chartData])

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-800">Forecasting</h1>
          <p className="text-sm text-neutral-400 mt-0.5">Prévisions SARIMA — volumes agrégés par Spark (15 min)</p>
        </div>

        {/* Model badge */}
        <div className="flex items-center gap-2">
          <span className="badge badge-blue">Modèle : SARIMA</span>
          <span className="badge bg-green-50 text-green-700">MAE = 2 096 appels/j</span>
        </div>
      </div>

      {/* Horizon selector */}
      <div className="flex gap-2">
        {HORIZONS.map(h => (
          <button
            key={h.value}
            onClick={() => setHorizon(h)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all duration-150
              ${horizon.value === h.value
                ? 'bg-accent-600 text-white shadow-sm'
                : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'}`}
          >
            {h.label}
          </button>
        ))}
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Volume max', value: fmt(stats.max), sub: 'appels / 15 min' },
            { label: 'Volume moyen', value: fmt(stats.avg, 0), sub: 'appels / 15 min' },
            { label: 'Volume min', value: fmt(stats.min), sub: 'appels / 15 min' },
          ].map(s => (
            <div key={s.label} className="card">
              <p className="text-xs text-neutral-400 uppercase tracking-wide">{s.label}</p>
              <p className="text-2xl font-semibold text-neutral-800 mt-1">{s.value}</p>
              <p className="text-xs text-neutral-400 mt-0.5">{s.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Main chart */}
      <div className="card">
        <p className="text-sm font-semibold text-neutral-800 mb-1">Courbe des volumes 15 min</p>
        <p className="text-xs text-neutral-400 mb-5">
          Source : <code className="bg-surface-100 px-1 rounded">volume_15min.parquet</code> · endpoint : <code className="bg-surface-100 px-1 rounded">/api/v1/forecast/intraday</code>
        </p>

        {loading && <div className="skeleton h-72 w-full rounded-lg" />}
        {error && <ErrorState message={error} />}
        {!loading && !error && chartData.length === 0 && (
          <EmptyState
            message="Aucune donnée de forecast disponible"
            hint="Assurez-vous que le DAG Spark a bien généré volume_15min.parquet"
          />
        )}
        {error && (
          <ErrorState message={`${error} — Le fichier Parquet ne contient pas assez de données pour cet horizon. Relancez le DAG Spark ou choisissez un horizon plus court.`} />
        )}
        {!loading && !error && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={288}>
            <AreaChart data={chartData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="grad2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#0ea5e9" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#f0f0f0" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#a3a3a3' }} tickLine={false} axisLine={false}
                interval={Math.floor(chartData.length / 10)} />
              <YAxis tick={{ fontSize: 10, fill: '#a3a3a3' }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              {stats && (
                <ReferenceLine y={stats.avg} stroke="#0ea5e9" strokeDasharray="3 3" strokeOpacity={0.4} />
              )}
              <Area type="monotone" dataKey="volume" stroke="#0ea5e9" strokeWidth={1.5}
                fill="url(#grad2)" dot={false} activeDot={{ r: 3, fill: '#0ea5e9' }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Pipeline info */}
      <div className="card bg-surface-50 border-neutral-100">
        <p className="text-xs font-semibold text-neutral-600 mb-2">Pipeline de forecast</p>
        <div className="flex flex-wrap gap-2 text-[10px]">
          {['Données Spark', '→', 'volume_15min.parquet', '→', 'SARIMA (winner)', '→', 'Intraday scaling', '→', 'Erlang C'].map((s, i) => (
            <span key={i} className={s === '→' ? 'text-neutral-300' : 'badge bg-white border border-neutral-200 text-neutral-600'}>
              {s}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
