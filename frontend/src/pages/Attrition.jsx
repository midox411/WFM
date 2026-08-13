import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import { getAttritionAgents } from '../api'
import { useFetch } from '../hooks/useFetch'
import { computeRisk, fmt } from '../utils'
import { ErrorState, EmptyState } from '../components/States'
import { Search } from 'lucide-react'

const TIER_COLOR = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' }

export default function Attrition() {
  const { data, loading, error } = useFetch(() => getAttritionAgents())
  const [search, setSearch] = useState('')
  const [sortTier, setSortTier] = useState('all')

  const enriched = useMemo(() => {
    if (!data?.data) return []
    return data.data
      .map(a => ({ ...a, risk: computeRisk(a) }))
      .sort((a, b) => b.risk.pct - a.risk.pct)
  }, [data])

  const filtered = useMemo(() => {
    let list = enriched
    if (sortTier !== 'all') list = list.filter(a => a.risk.tier === sortTier)
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(a =>
        String(a.agent_id).includes(q) ||
        a.seniority_level?.toLowerCase().includes(q) ||
        a.contract_type?.toLowerCase().includes(q)
      )
    }
    return list
  }, [enriched, sortTier, search])

  // Distribution chart data
  const distData = useMemo(() => {
    if (!enriched.length) return []
    const counts = { high: 0, medium: 0, low: 0 }
    enriched.forEach(a => counts[a.risk.tier]++)
    return [
      { name: 'Élevé',  value: counts.high,   fill: '#ef4444' },
      { name: 'Moyen',  value: counts.medium, fill: '#f59e0b' },
      { name: 'Faible', value: counts.low,    fill: '#22c55e' },
    ]
  }, [enriched])

  const [page, setPage] = useState(1)
  const PAGE_SIZE = 10
  const pages = Math.ceil(filtered.length / PAGE_SIZE)
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-800">Attrition</h1>
          <p className="text-sm text-neutral-400 mt-0.5">
            {data ? `${data.active_agents} agents actifs` : 'Risque de départ des agents'}
            {' · '}endpoint : <code className="bg-surface-100 px-1 rounded text-xs">/api/v1/attrition/agents</code>
          </p>
        </div>
      </div>

      {/* Top section: dist chart + stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card col-span-1">
          <p className="text-sm font-semibold text-neutral-800 mb-4">Distribution du risque</p>
          {loading && <div className="skeleton h-40 rounded-lg" />}
          {!loading && !error && distData.length > 0 && (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={distData} barSize={36} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#f0f0f0" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#a3a3a3' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#a3a3a3' }} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: '#f5f5f5' }}
                  content={({ active, payload }) =>
                    active && payload?.length
                      ? <div className="bg-white border border-neutral-100 rounded-lg px-3 py-2 text-xs shadow-card-hover">
                          <p className="font-semibold text-neutral-800">{payload[0].payload.name}</p>
                          <p className="text-neutral-400">{payload[0].value} agents</p>
                        </div>
                      : null
                  }
                />
                {distData.map(d => (
                  <Bar key={d.name} dataKey="value" radius={[4, 4, 0, 0]}>
                    {distData.map((entry, i) => <Cell key={i} fill={entry.fill} fillOpacity={0.85} />)}
                  </Bar>
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="col-span-2 grid grid-cols-3 gap-4">
          {['high', 'medium', 'low'].map(tier => {
            const labels = { high: 'Élevé', medium: 'Moyen', low: 'Faible' }
            const count = enriched.filter(a => a.risk.tier === tier).length
            const badgeCls = { high: 'badge-red', medium: 'badge-amber', low: 'badge-green' }
            return (
              <div key={tier} className="card flex flex-col gap-2">
                <span className={`badge ${badgeCls[tier]} self-start`}>{labels[tier]}</span>
                {loading
                  ? <div className="skeleton h-8 w-16" />
                  : <p className="text-3xl font-semibold tabular-nums text-neutral-800">{count}</p>
                }
                <p className="text-xs text-neutral-400">agents</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center gap-3 p-4 border-b border-neutral-100">
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Rechercher un agent…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              className="w-full pl-8 pr-3 py-2 text-sm border border-neutral-200 rounded-lg bg-surface-50
                         focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500"
            />
          </div>
          <div className="flex gap-1">
            {['all', 'high', 'medium', 'low'].map(t => (
              <button
                key={t}
                onClick={() => { setSortTier(t); setPage(1) }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150
                  ${sortTier === t ? 'bg-neutral-800 text-white' : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'}`}
              >
                {t === 'all' ? 'Tous' : t === 'high' ? 'Élevé' : t === 'medium' ? 'Moyen' : 'Faible'}
              </button>
            ))}
          </div>
          <p className="text-xs text-neutral-400 ml-auto">{filtered.length} agents</p>
        </div>

        {/* Table content */}
        {loading && (
          <div className="p-4 space-y-2">
            {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-10 rounded-lg" />)}
          </div>
        )}
        {error && <div className="p-4"><ErrorState message={error} /></div>}
        {!loading && !error && filtered.length === 0 && (
          <EmptyState message="Aucun agent trouvé" hint="Modifiez votre recherche ou filtre." />
        )}
        {!loading && !error && paged.length > 0 && (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100">
                  {['Agent ID', 'Ancienneté', 'Contrat', 'Coût horaire', 'Risque', 'Score'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-neutral-400 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paged.map((agent, idx) => (
                  <tr key={agent.agent_id}
                    className={`border-b border-neutral-50 hover:bg-surface-50 transition-colors ${idx % 2 === 0 ? '' : 'bg-surface-50/50'}`}
                  >
                    <td className="px-4 py-3 font-medium text-neutral-700">#{agent.agent_id}</td>
                    <td className="px-4 py-3 capitalize text-neutral-600">{agent.seniority_level}</td>
                    <td className="px-4 py-3 text-neutral-600">{agent.contract_type?.replace('_', '-')}</td>
                    <td className="px-4 py-3 tabular-nums text-neutral-600">{fmt(agent.base_hourly_cost, 2)} MAD</td>
                    <td className="px-4 py-3">
                      <span className={`badge ${agent.risk.tier === 'high' ? 'badge-red' : agent.risk.tier === 'medium' ? 'badge-amber' : 'badge-green'}`}>
                        {agent.risk.tier === 'high' && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />}
                        {agent.risk.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${agent.risk.pct}%`,
                              backgroundColor: TIER_COLOR[agent.risk.tier],
                              opacity: 0.75
                            }}
                          />
                        </div>
                        <span className="text-xs tabular-nums text-neutral-500 w-8 text-right">
                          {agent.risk.pct.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-neutral-100">
                <p className="text-xs text-neutral-400">Page {page} sur {pages}</p>
                <div className="flex gap-1">
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                    className="btn-secondary py-1.5 px-3 text-xs disabled:opacity-40">
                    ← Préc.
                  </button>
                  <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                    className="btn-secondary py-1.5 px-3 text-xs disabled:opacity-40">
                    Suiv. →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
