import { useState, useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { getWhatIfSimulation } from '../api'
import { useFetch } from '../hooks/useFetch'
import { fmt } from '../utils'
import { ErrorState, SkeletonCard } from '../components/States'
import { Sliders, RefreshCw, AlertTriangle, TrendingUp, Users, ShieldAlert, DollarSign } from 'lucide-react'

// Presets for quick scenario selection
const PRESETS = [
  { name: 'Nominal (Baseline)', vol: 0, headcount: 0, absence: 5 },
  { name: 'Surcroît d\'activité (+25% volume)', vol: 25, headcount: 0, absence: 5 },
  { name: 'Crise absentéisme (15% absence)', vol: 0, headcount: 0, absence: 15 },
  { name: 'Renfort d\'équipe (+10 agents)', vol: 0, headcount: 10, absence: 5 },
]

export default function WhatIf() {
  const [volChange, setVolChange] = useState(0)
  const [headcountDelta, setHeadcountDelta] = useState(0)
  const [absenteeism, setAbsenteeism] = useState(5)

  const { data, loading, error } = useFetch(
    () => getWhatIfSimulation(volChange, headcountDelta, absenteeism),
    [volChange, headcountDelta, absenteeism]
  )

  const summary = data?.summary
  const intraday = data?.intraday ?? []

  const applyPreset = (preset) => {
    setVolChange(preset.vol)
    setHeadcountDelta(preset.headcount)
    setAbsenteeism(preset.absence)
  }

  const resetAll = () => {
    setVolChange(0)
    setHeadcountDelta(0)
    setAbsenteeism(5)
  }

  // SLA Color status
  const slaColorClass = useMemo(() => {
    if (!summary) return 'text-neutral-800'
    if (summary.avg_service_level_pct >= 80) return 'text-green-600'
    if (summary.avg_service_level_pct >= 65) return 'text-amber-600'
    return 'text-red-600'
  }, [summary])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-800 flex items-center gap-2">
            <Sliders size={22} className="text-accent-600" />
            Simulateur What-if
          </h1>
          <p className="text-sm text-neutral-400 mt-0.5">
            Évaluez l'impact temps réel d'un changement de volume, d'effectif ou d'absentéisme sur le SLA et les coûts.
          </p>
        </div>
        <button
          onClick={resetAll}
          className="btn-secondary text-xs flex items-center gap-1.5"
        >
          <RefreshCw size={13} /> Réinitialiser
        </button>
      </div>

      {/* Preset Scenarios */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-neutral-400 mr-1 font-medium">Scénarios préconfigurés :</span>
        {PRESETS.map((p) => {
          const isActive = volChange === p.vol && headcountDelta === p.headcount && absenteeism === p.absence
          return (
            <button
              key={p.name}
              onClick={() => applyPreset(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-neutral-800 text-white shadow-sm'
                  : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
              }`}
            >
              {p.name}
            </button>
          )
        })}
      </div>

      {/* Interactive Controls (Sliders) */}
      <div className="card grid grid-cols-1 md:grid-cols-3 gap-6 bg-white border-neutral-100 shadow-sm">
        {/* Slider 1: Volume */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <label className="font-semibold text-neutral-700 flex items-center gap-1.5">
              <TrendingUp size={14} className="text-accent-600" /> Volume d'appels
            </label>
            <span className={`font-bold tabular-nums ${volChange > 0 ? 'text-amber-600' : volChange < 0 ? 'text-green-600' : 'text-neutral-700'}`}>
              {volChange > 0 ? `+${volChange}%` : `${volChange}%`}
            </span>
          </div>
          <input
            type="range"
            min="-50"
            max="50"
            step="5"
            value={volChange}
            onChange={(e) => setVolChange(Number(e.target.value))}
            className="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-accent-600"
          />
          <div className="flex justify-between text-[10px] text-neutral-400">
            <span>-50%</span>
            <span>Nominal (0%)</span>
            <span>+50%</span>
          </div>
        </div>

        {/* Slider 2: Headcount */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <label className="font-semibold text-neutral-700 flex items-center gap-1.5">
              <Users size={14} className="text-accent-600" /> Variation d'effectif
            </label>
            <span className={`font-bold tabular-nums ${headcountDelta > 0 ? 'text-green-600' : headcountDelta < 0 ? 'text-red-600' : 'text-neutral-700'}`}>
              {headcountDelta > 0 ? `+${headcountDelta} agents` : `${headcountDelta} agents`}
            </span>
          </div>
          <input
            type="range"
            min="-20"
            max="20"
            step="1"
            value={headcountDelta}
            onChange={(e) => setHeadcountDelta(Number(e.target.value))}
            className="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-accent-600"
          />
          <div className="flex justify-between text-[10px] text-neutral-400">
            <span>-20 agents</span>
            <span>82 agents</span>
            <span>+20 agents</span>
          </div>
        </div>

        {/* Slider 3: Absenteeism */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <label className="font-semibold text-neutral-700 flex items-center gap-1.5">
              <ShieldAlert size={14} className="text-accent-600" /> Taux d'absentéisme
            </label>
            <span className={`font-bold tabular-nums ${absenteeism > 10 ? 'text-red-600' : absenteeism > 5 ? 'text-amber-600' : 'text-green-600'}`}>
              {absenteeism}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="30"
            step="1"
            value={absenteeism}
            onChange={(e) => setAbsenteeism(Number(e.target.value))}
            className="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-accent-600"
          />
          <div className="flex justify-between text-[10px] text-neutral-400">
            <span>0% (Parfait)</span>
            <span>5% (Std)</span>
            <span>30% (Crise)</span>
          </div>
        </div>
      </div>

      {/* Simulated Results KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: SLA */}
        {loading ? <SkeletonCard /> : (
          <div className="kpi-card border-l-4 border-l-accent-500">
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">SLA Moyen (80/20)</p>
            <p className={`text-2xl font-semibold tabular-nums mt-1 ${slaColorClass}`}>
              {summary?.avg_service_level_pct}%
            </p>
            <p className="text-xs text-neutral-400 mt-0.5">
              Objectif cible : <span className="font-medium text-neutral-600">80.0%</span>
            </p>
          </div>
        )}

        {/* KPI 2: Coverage */}
        {loading ? <SkeletonCard /> : (
          <div className="kpi-card border-l-4 border-l-blue-500">
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Couverture Erlang C</p>
            <p className="text-2xl font-semibold tabular-nums text-neutral-800 mt-1">
              {summary?.coverage_rate_pct}%
            </p>
            <p className="text-xs text-neutral-400 mt-0.5">
              Créneaux respectant la cible
            </p>
          </div>
        )}

        {/* KPI 3: Staffing Peak */}
        {loading ? <SkeletonCard /> : (
          <div className="kpi-card border-l-4 border-l-indigo-500">
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Peak Agents Requis</p>
            <p className="text-2xl font-semibold tabular-nums text-neutral-800 mt-1">
              {summary?.peak_agents_req_sim} <span className="text-sm font-normal text-neutral-400">agents</span>
            </p>
            <p className="text-xs text-neutral-400 mt-0.5">
              vs {summary?.peak_agents_req_base} agents baseline
            </p>
          </div>
        )}

        {/* KPI 4: Financial Impact */}
        {loading ? <SkeletonCard /> : (
          <div className={`kpi-card border-l-4 ${summary?.cost_delta > 0 ? 'border-l-red-500 bg-red-50/20' : 'border-l-green-500 bg-green-50/20'}`}>
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Impact Financier (Semaine)</p>
            <p className={`text-2xl font-semibold tabular-nums mt-1 ${summary?.cost_delta > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {summary?.cost_delta > 0 ? `+${fmt(summary?.cost_delta)}` : fmt(summary?.cost_delta)} MAD
            </p>
            <p className="text-xs text-neutral-400 mt-0.5">
              {summary?.cost_delta > 0 ? `Surcoût de +${summary?.cost_delta_pct}%` : `Économie de ${summary?.cost_delta_pct}%`}
            </p>
          </div>
        )}
      </div>

      {/* Alert Banner if SLA below target */}
      {summary && summary.avg_service_level_pct < 80 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3 text-amber-800 text-xs">
          <AlertTriangle size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-900">Avertissement Niveau de Service (SLA)</p>
            <p className="mt-0.5">
              Le SLA estimé ({summary.avg_service_level_pct}%) est inférieur à l'objectif de 80%. Envisagez d'augmenter l'effectif ou de réduire l'absentéisme pour rétablir la qualité de service.
            </p>
          </div>
        </div>
      )}

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1: Volume Comparison */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-neutral-800">Volume d'Appels : Baseline vs Simulé</p>
              <p className="text-xs text-neutral-400">Impact de la variation de volume (+/- %)</p>
            </div>
          </div>

          {error && <ErrorState message={error} />}
          {!error && (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={intraday} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradSim" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradBase" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#f0f0f0" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#a3a3a3' }} tickLine={false} axisLine={false} interval={7} />
                <YAxis tick={{ fontSize: 10, fill: '#a3a3a3' }} tickLine={false} axisLine={false} />
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="bg-white border border-neutral-100 rounded-lg px-3 py-2 text-xs shadow-card-hover space-y-1">
                        <p className="text-neutral-400 font-medium">{payload[0].payload.time}</p>
                        <p className="text-accent-600">Baseline : <b>{payload[0].value}</b> appels</p>
                        <p className="text-amber-600">Simulé : <b>{payload[1]?.value}</b> appels</p>
                      </div>
                    ) : null
                  }
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                <Area type="monotone" name="Baseline" dataKey="volume_base" stroke="#0ea5e9" strokeWidth={1.5} fill="url(#gradBase)" />
                <Area type="monotone" name="Simulé" dataKey="volume_sim" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 4" fill="url(#gradSim)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Chart 2: Staffing Requirements vs Availability */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-neutral-800">Staffing : Requis vs Disponible</p>
              <p className="text-xs text-neutral-400">Nombre d'agents requis Erlang C vs agents présents</p>
            </div>
          </div>

          {!error && (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={intraday} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#f0f0f0" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#a3a3a3' }} tickLine={false} axisLine={false} interval={7} />
                <YAxis tick={{ fontSize: 10, fill: '#a3a3a3' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="bg-white border border-neutral-100 rounded-lg px-3 py-2 text-xs shadow-card-hover space-y-1">
                        <p className="text-neutral-400 font-medium">{payload[0].payload.time}</p>
                        <p className="text-neutral-600">Requis Baseline : <b>{payload[0].value}</b> agents</p>
                        <p className="text-indigo-600">Requis Simulé : <b>{payload[1]?.value}</b> agents</p>
                        <p className="text-green-600">Disponible : <b>{payload[2]?.value}</b> agents</p>
                      </div>
                    ) : null
                  }
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                <Line type="monotone" name="Requis Baseline" dataKey="agents_req_base" stroke="#a3a3a3" strokeWidth={1} dot={false} />
                <Line type="monotone" name="Requis Simulé" dataKey="agents_req_sim" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" name="Disponible" dataKey="agents_available" stroke="#10b981" strokeWidth={2} strokeDasharray="3 3" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Summary Table */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-100 flex justify-between items-center">
          <p className="text-sm font-semibold text-neutral-800">Bilan du Scénario Simulé</p>
          <span className="badge bg-neutral-100 text-neutral-700">Calcul Temps Réel</span>
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-neutral-100 bg-surface-50 text-neutral-500 font-medium">
              <th className="px-4 py-2.5 text-left">Indicateur</th>
              <th className="px-4 py-2.5 text-left">Scénario Baseline</th>
              <th className="px-4 py-2.5 text-left">Scénario Simulé</th>
              <th className="px-4 py-2.5 text-left">Écart (Delta)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-50">
            <tr>
              <td className="px-4 py-2.5 font-medium text-neutral-700">Volume d'appels moyen</td>
              <td className="px-4 py-2.5 text-neutral-600">Nominal (100%)</td>
              <td className="px-4 py-2.5 text-neutral-600">{volChange >= 0 ? `+${volChange}%` : `${volChange}%`}</td>
              <td className="px-4 py-2.5 font-semibold text-neutral-800">{volChange >= 0 ? `+${volChange}%` : `${volChange}%`}</td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-medium text-neutral-700">Effectif total (Workforce)</td>
              <td className="px-4 py-2.5 text-neutral-600">82 agents</td>
              <td className="px-4 py-2.5 text-neutral-600">{summary?.effective_workforce} agents</td>
              <td className="px-4 py-2.5 font-semibold text-neutral-800">{headcountDelta >= 0 ? `+${headcountDelta}` : headcountDelta} agents</td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-medium text-neutral-700">Taux d'absentéisme</td>
              <td className="px-4 py-2.5 text-neutral-600">5.0% (Standard)</td>
              <td className="px-4 py-2.5 text-neutral-600">{absenteeism}%</td>
              <td className="px-4 py-2.5 font-semibold text-neutral-800">{absenteeism - 5 >= 0 ? `+${absenteeism - 5}%` : `${absenteeism - 5}%`}</td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-medium text-neutral-700">Peak d'agents requis (Erlang C)</td>
              <td className="px-4 py-2.5 text-neutral-600">{summary?.peak_agents_req_base} agents</td>
              <td className="px-4 py-2.5 text-neutral-600">{summary?.peak_agents_req_sim} agents</td>
              <td className="px-4 py-2.5 font-semibold text-neutral-800">
                {summary?.peak_agents_req_sim - summary?.peak_agents_req_base >= 0
                  ? `+${summary?.peak_agents_req_sim - summary?.peak_agents_req_base}`
                  : summary?.peak_agents_req_sim - summary?.peak_agents_req_base}
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-medium text-neutral-700">Niveau de Service Moyen (SLA 80/20)</td>
              <td className="px-4 py-2.5 text-neutral-600">80.0% (Cible)</td>
              <td className={`px-4 py-2.5 font-semibold ${slaColorClass}`}>{summary?.avg_service_level_pct}%</td>
              <td className="px-4 py-2.5 font-semibold text-neutral-800">
                {(summary?.avg_service_level_pct - 80.0) >= 0 ? `+${(summary?.avg_service_level_pct - 80.0).toFixed(1)}%` : `${(summary?.avg_service_level_pct - 80.0).toFixed(1)}%`}
              </td>
            </tr>
            <tr>
              <td className="px-4 py-2.5 font-medium text-neutral-700">Coût Hebdomadaire Estimé</td>
              <td className="px-4 py-2.5 text-neutral-600">{fmt(summary?.baseline_weekly_cost)} MAD</td>
              <td className="px-4 py-2.5 text-neutral-600">{fmt(summary?.simulated_weekly_cost)} MAD</td>
              <td className={`px-4 py-2.5 font-semibold ${summary?.cost_delta > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {summary?.cost_delta > 0 ? `+${fmt(summary?.cost_delta)} MAD (+${summary?.cost_delta_pct}%)` : `${fmt(summary?.cost_delta)} MAD (${summary?.cost_delta_pct}%)`}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
