import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { getSchedule } from '../api'
import { useFetch } from '../hooks/useFetch'
import { slotToTime, DAY_NAMES, fmt } from '../utils'
import { ErrorState, EmptyState } from '../components/States'
import { CheckCircle, Clock } from 'lucide-react'

// Baseline cost from Jour 13 OPTIMAL run (real logged value)
const BASELINE_COST = 269762
const OPTIMIZED_COST = 115931
const SAVING_PCT = 57.0

const AGENT_COLORS = [
  '#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444',
  '#8b5cf6','#ec4899','#14b8a6','#f97316','#84cc16'
]

export default function Scheduling() {
  const [selectedDay, setSelectedDay] = useState(0)
  const { data, loading, error } = useFetch(
    () => getSchedule(selectedDay),
    [selectedDay]
  )

  // Gantt data: { agentId → Set<slot> } for the selected day
  const gantt = useMemo(() => {
    if (!data?.schedule?.length) return { agents: [], slotSet: [] }
    const agentMap = {}
    const slots = new Set()
    data.schedule.forEach(({ agent_id, slot }) => {
      if (!agentMap[agent_id]) agentMap[agent_id] = new Set()
      agentMap[agent_id].add(slot)
      slots.add(slot)
    })
    const agentIds = Object.keys(agentMap).map(Number).sort((a, b) => a - b)
    const slotArr = Array.from({ length: 48 }, (_, i) => i)  // always show 08h-20h
    return { agentIds, slotArr, agentMap }
  }, [data])

  // Aggregate: agents per slot (for coverage bar chart)
  const agentsPerSlot = useMemo(() => {
    if (!data?.schedule?.length) return []
    const map = {}
    data.schedule.forEach(({ slot }) => { map[slot] = (map[slot] || 0) + 1 })
    return Array.from({ length: 48 }, (_, slot) => ({ time: slotToTime(slot), agents: map[slot] ?? 0 }))
  }, [data])

  const hasSolution = data && data.total_shifts_slots > 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-neutral-800">Scheduling</h1>
        <p className="text-sm text-neutral-400 mt-0.5">
          Planning optimisé OR-Tools CP-SAT · endpoint :
          <code className="bg-surface-100 px-1 rounded text-xs ml-1">/api/v1/optimization/schedule</code>
        </p>
      </div>

      {/* Cost KPIs */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card">
          <p className="text-xs text-neutral-400 uppercase tracking-wide">Coût baseline</p>
          <p className="text-2xl font-semibold tabular-nums text-neutral-800 mt-1">{fmt(BASELINE_COST)}</p>
          <p className="text-xs text-neutral-400 mt-0.5">MAD / semaine</p>
        </div>
        <div className="card border-accent-100 bg-accent-50">
          <p className="text-xs text-accent-600 uppercase tracking-wide">Coût optimisé</p>
          <p className="text-2xl font-semibold tabular-nums text-accent-700 mt-1">{fmt(OPTIMIZED_COST)}</p>
          <p className="text-xs text-accent-500 mt-0.5">MAD / semaine</p>
        </div>
        <div className="card border-green-100 bg-green-50">
          <p className="text-xs text-green-600 uppercase tracking-wide">Économie</p>
          <p className="text-2xl font-semibold tabular-nums text-green-700 mt-1">−{SAVING_PCT}%</p>
          <p className="text-xs text-green-500 mt-0.5">{fmt(BASELINE_COST - OPTIMIZED_COST)} MAD épargnés</p>
        </div>
        <div className="card">
          <p className="text-xs text-neutral-400 uppercase tracking-wide">Solver status</p>
          <div className="flex items-center gap-1.5 mt-1">
            <CheckCircle size={16} className="text-green-500 shrink-0" />
            <p className="text-lg font-semibold text-neutral-800">OPTIMAL</p>
          </div>
          <p className="text-xs text-neutral-400 mt-0.5">Prouvé en 12.7s · gap = 0%</p>
        </div>
      </div>

      {/* Solver params */}
      <div className="card bg-surface-50">
        <p className="text-xs font-semibold text-neutral-600 mb-3">Paramètres du solveur OR-Tools CP-SAT</p>
        <div className="grid grid-cols-4 gap-3 text-xs">
          {[
            ['Erlang C SL', '80% / 20s'],
            ['AHT', '240s'],
            ['Créneaux', '15 min'],
            ['Agents', '82 actifs'],
            ['Shift FT', '8h continu'],
            ['Shift PT', '4h continu'],
            ['Repos min.', '2 jours/sem'],
            ['Coverage', '100%'],
          ].map(([k, v]) => (
            <div key={k} className="flex flex-col gap-0.5">
              <p className="text-neutral-400">{k}</p>
              <p className="font-medium text-neutral-700">{v}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Day selector */}
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs text-neutral-500 mr-1">Jour :</p>
        {DAY_NAMES.map((name, i) => (
          <button
            key={i}
            onClick={() => setSelectedDay(i)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150
              ${selectedDay === i ? 'bg-neutral-800 text-white' : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'}`}
          >
            {name}
          </button>
        ))}
      </div>

      {/* Coverage bar chart */}
      <div className="card">
        <p className="text-sm font-semibold text-neutral-800 mb-1">
          Couverture par créneau — {DAY_NAMES[selectedDay]}
        </p>
        <p className="text-xs text-neutral-400 mb-4">Agents actifs · shifts continus 8h (FT) ou 4h (PT)</p>
        {loading
          ? <div className="skeleton h-40 rounded-lg" />
          : (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={agentsPerSlot} barSize={6} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#f0f0f0" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#a3a3a3' }} tickLine={false} axisLine={false} interval={7} />
                <YAxis tick={{ fontSize: 10, fill: '#a3a3a3' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip cursor={{ fill: '#f5f5f5' }}
                  content={({ active, payload }) => active && payload?.length
                    ? <div className="bg-white border border-neutral-100 rounded-lg px-3 py-2 text-xs shadow-card-hover">
                        <p className="text-neutral-400">{payload[0].payload.time}</p>
                        <p className="font-semibold text-neutral-800">{payload[0].value} agents</p>
                      </div>
                    : null}
                />
                <Bar dataKey="agents" radius={[2, 2, 0, 0]} fill="#0ea5e9" fillOpacity={0.75} />
              </BarChart>
            </ResponsiveContainer>
          )
        }
      </div>

      {/* ── GANTT TIMETABLE ── */}
      <div className="card p-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
          <p className="text-sm font-semibold text-neutral-800">Emploi du temps — {DAY_NAMES[selectedDay]}</p>
          {data && (
            <span className="badge badge-blue">
              <Clock size={10} /> {fmt(data.total_shifts_slots)} créneaux assignés
            </span>
          )}
        </div>

        {loading && <div className="p-4 space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="skeleton h-8 rounded-lg" />)}</div>}
        {error && <div className="p-4"><ErrorState message={error} /></div>}
        {!loading && !error && !hasSolution && (
          <EmptyState
            message="Aucun planning disponible"
            hint="Lancez le DAG dag_optimization dans Airflow pour générer un planning optimal."
          />
        )}

        {!loading && !error && hasSolution && (
          <div className="overflow-x-auto">
            <table className="border-collapse" style={{ minWidth: '900px' }}>
              <thead>
                <tr>
                  {/* Agent ID header cell */}
                  <th className="sticky left-0 z-10 bg-surface-50 border-b border-r border-neutral-100"
                    style={{ width: '80px', minWidth: '80px' }}>
                    <span className="block px-3 py-2 text-[10px] font-medium text-neutral-400 uppercase">Agent</span>
                  </th>
                  {/* Time slot headers — show every 4 slots = 1h */}
                  {gantt.slotArr?.map(slot => (
                    <th key={slot}
                      className="border-b border-neutral-100 text-center"
                      style={{ width: '18px', minWidth: '18px', padding: 0 }}
                    >
                      {slot % 4 === 0 && (
                        <span className="block text-[9px] text-neutral-400 py-1 font-normal">
                          {slotToTime(slot)}
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {gantt.agentIds?.map((agentId, rowIdx) => {
                  const agentSlots = gantt.agentMap[agentId]
                  const color = AGENT_COLORS[rowIdx % AGENT_COLORS.length]
                  return (
                    <tr key={agentId} className="group hover:bg-surface-50 transition-colors">
                      {/* Agent ID label */}
                      <td className="sticky left-0 z-10 bg-white group-hover:bg-surface-50 border-b border-r border-neutral-50"
                        style={{ width: '80px', minWidth: '80px' }}>
                        <span className="block px-3 py-1 text-[11px] font-medium text-neutral-600 tabular-nums">
                          #{agentId}
                        </span>
                      </td>
                      {/* Slot cells */}
                      {gantt.slotArr?.map(slot => {
                        const active = agentSlots.has(slot)
                        // Detect block start/end for rounded corners
                        const prev = agentSlots.has(slot - 1)
                        const next = agentSlots.has(slot + 1)
                        return (
                          <td key={slot}
                            className="border-b border-neutral-50 p-0"
                            style={{ width: '18px', height: '28px' }}
                          >
                            {active && (
                              <div
                                title={`Agent #${agentId} · ${slotToTime(slot)}`}
                                style={{
                                  height: '16px',
                                  margin: '6px 1px',
                                  backgroundColor: color,
                                  opacity: 0.75,
                                  borderRadius:
                                    !prev && !next ? '4px'
                                    : !prev ? '4px 0 0 4px'
                                    : !next ? '0 4px 4px 0'
                                    : '0',
                                }}
                              />
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
