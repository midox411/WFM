import { useState } from 'react'
import { getDriftAnalysis } from '../api'
import { useFetch } from '../hooks/useFetch'
import { ErrorState, SkeletonCard } from '../components/States'
import { Activity, ShieldCheck, AlertTriangle, RefreshCw, Database, Cpu, CheckCircle2, XCircle } from 'lucide-react'

export default function DriftMonitoring() {
  const [refreshKey, setRefreshKey] = useState(0)
  const { data, loading, error } = useFetch(() => getDriftAnalysis(), [refreshKey])

  const globalSummary = data?.global_summary
  const fcDrift = data?.forecasting_drift
  const attDrift = data?.attrition_drift

  const [activeTab, setActiveTab] = useState('all')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-800 flex items-center gap-2">
            <Activity size={22} className="text-accent-600" />
            Drift Monitoring (Evidently AI)
          </h1>
          <p className="text-sm text-neutral-400 mt-0.5">
            Détection automatique des dérives de distribution entre données de référence et données récentes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {data?.last_check_timestamp && (
            <span className="text-xs text-neutral-400 font-mono">
              Dernier contrôle : {data.last_check_timestamp}
            </span>
          )}
          <button
            onClick={() => setRefreshKey(k => k + 1)}
            className="btn-secondary text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Analyser
          </button>
        </div>
      </div>

      {/* Global Status KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Global Status */}
        {loading ? <SkeletonCard /> : (
          <div className={`kpi-card border-l-4 ${globalSummary?.drift_detected ? 'border-l-red-500 bg-red-50/20' : 'border-l-green-500 bg-green-50/20'}`}>
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Statut Global Drift</p>
            <div className="flex items-center gap-2 mt-1">
              {globalSummary?.drift_detected ? (
                <>
                  <AlertTriangle size={20} className="text-red-500 shrink-0" />
                  <span className="text-xl font-semibold text-red-600">Drift Détecté</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={20} className="text-green-500 shrink-0" />
                  <span className="text-xl font-semibold text-green-600">Aucun Drift</span>
                </>
              )}
            </div>
            <p className="text-xs text-neutral-400 mt-1">
              {globalSummary?.drift_detected ? 'Dérive statistique détectée' : 'Distributions stables'}
            </p>
          </div>
        )}

        {/* KPI 2: Features Monitored */}
        {loading ? <SkeletonCard /> : (
          <div className="kpi-card border-l-4 border-l-accent-500">
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Features Surveillées</p>
            <p className="text-2xl font-semibold tabular-nums text-neutral-800 mt-1">
              {globalSummary?.total_features_monitored} <span className="text-sm font-normal text-neutral-400">features</span>
            </p>
            <p className="text-xs text-neutral-400 mt-0.5">
              Forecasting ({fcDrift?.total_features}) & Attrition ({attDrift?.total_features})
            </p>
          </div>
        )}

        {/* KPI 3: Drifted Features Count */}
        {loading ? <SkeletonCard /> : (
          <div className="kpi-card border-l-4 border-l-amber-500">
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Features en Drift</p>
            <p className="text-2xl font-semibold tabular-nums text-neutral-800 mt-1">
              {globalSummary?.drifted_features_count} <span className="text-sm font-normal text-neutral-400">/ {globalSummary?.total_features_monitored}</span>
            </p>
            <p className="text-xs text-neutral-400 mt-0.5">
              Part de dérive : <span className="font-semibold text-neutral-700">{globalSummary?.drift_share_pct}%</span>
            </p>
          </div>
        )}

        {/* KPI 4: Monitoring Engine */}
        {loading ? <SkeletonCard /> : (
          <div className="kpi-card border-l-4 border-l-indigo-500">
            <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">Moteur d'Analyse</p>
            <div className="flex items-center gap-1.5 mt-1">
              <Cpu size={16} className="text-indigo-600 shrink-0" />
              <p className="text-sm font-semibold text-neutral-800">Evidently AI Engine</p>
            </div>
            <p className="text-xs text-neutral-400 mt-0.5">
              Kolmogorov-Smirnov & TVD
            </p>
          </div>
        )}
      </div>

      {/* Module Tabs */}
      <div className="flex gap-2">
        {[
          { id: 'all', label: 'Tous les modules' },
          { id: 'forecasting', label: `Forecasting (${fcDrift?.drifted_count ?? 0} drift)` },
          { id: 'attrition', label: `Attrition (${attDrift?.drifted_count ?? 0} drift)` },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
              activeTab === tab.id
                ? 'bg-neutral-800 text-white shadow-sm'
                : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} />}

      {/* Module 1: Forecasting Data Drift */}
      {(activeTab === 'all' || activeTab === 'forecasting') && fcDrift && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-neutral-800">{fcDrift.module}</h2>
                <span className={`badge ${fcDrift.drift_detected ? 'badge-red' : 'badge-green'}`}>
                  {fcDrift.drift_detected ? 'Drift Détecté' : 'Stable'}
                </span>
              </div>
              <p className="text-xs text-neutral-400 mt-0.5 flex items-center gap-1">
                <Database size={12} /> Source : <code className="bg-surface-100 px-1 rounded">{fcDrift.dataset_source}</code>
              </p>
            </div>
            <p className="text-xs text-neutral-500 font-medium">
              {fcDrift.drifted_count} / {fcDrift.total_features} features dérivées
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-100 bg-surface-50 text-neutral-400 font-medium text-left">
                  <th className="px-3 py-2">Feature</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Test Statistique</th>
                  <th className="px-3 py-2">Moyenne Réf.</th>
                  <th className="px-3 py-2">Moyenne Réc.</th>
                  <th className="px-3 py-2">Score / P-Value</th>
                  <th className="px-3 py-2 text-right">Statut Drift</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {fcDrift.features.map(f => (
                  <tr key={f.feature} className="hover:bg-surface-50">
                    <td className="px-3 py-2.5 font-medium text-neutral-700">{f.feature}</td>
                    <td className="px-3 py-2.5 text-neutral-400 capitalize">{f.type}</td>
                    <td className="px-3 py-2.5 text-neutral-500">{f.metric_name}</td>
                    <td className="px-3 py-2.5 tabular-nums text-neutral-600">{f.ref_mean}</td>
                    <td className="px-3 py-2.5 tabular-nums text-neutral-600">{f.curr_mean}</td>
                    <td className="px-3 py-2.5 tabular-nums text-neutral-500">
                      p={f.p_value} (score={f.drift_score})
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {f.drift_detected ? (
                        <span className="badge badge-red inline-flex items-center gap-1">
                          <XCircle size={12} /> Drift
                        </span>
                      ) : (
                        <span className="badge badge-green inline-flex items-center gap-1">
                          <CheckCircle2 size={12} /> Stable
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Module 2: Attrition Data Drift */}
      {(activeTab === 'all' || activeTab === 'attrition') && attDrift && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-neutral-800">{attDrift.module}</h2>
                <span className={`badge ${attDrift.drift_detected ? 'badge-red' : 'badge-green'}`}>
                  {attDrift.drift_detected ? 'Drift Détecté' : 'Stable'}
                </span>
              </div>
              <p className="text-xs text-neutral-400 mt-0.5 flex items-center gap-1">
                <Database size={12} /> Source : <code className="bg-surface-100 px-1 rounded">{attDrift.dataset_source}</code>
              </p>
            </div>
            <p className="text-xs text-neutral-500 font-medium">
              {attDrift.drifted_count} / {attDrift.total_features} features dérivées
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-100 bg-surface-50 text-neutral-400 font-medium text-left">
                  <th className="px-3 py-2">Feature</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Test Statistique</th>
                  <th className="px-3 py-2">Valeur / Top Réf.</th>
                  <th className="px-3 py-2">Valeur / Top Réc.</th>
                  <th className="px-3 py-2">Score / P-Value</th>
                  <th className="px-3 py-2 text-right">Statut Drift</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {attDrift.features.map(f => (
                  <tr key={f.feature} className="hover:bg-surface-50">
                    <td className="px-3 py-2.5 font-medium text-neutral-700">{f.feature}</td>
                    <td className="px-3 py-2.5 text-neutral-400 capitalize">{f.type}</td>
                    <td className="px-3 py-2.5 text-neutral-500">{f.metric_name}</td>
                    <td className="px-3 py-2.5 tabular-nums text-neutral-600">
                      {f.ref_mean ?? f.ref_top_category}
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-neutral-600">
                      {f.curr_mean ?? f.curr_top_category}
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-neutral-500">
                      p={f.p_value} (score={f.drift_score})
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {f.drift_detected ? (
                        <span className="badge badge-red inline-flex items-center gap-1">
                          <XCircle size={12} /> Drift
                        </span>
                      ) : (
                        <span className="badge badge-green inline-flex items-center gap-1">
                          <CheckCircle2 size={12} /> Stable
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Technical Summary Card for Jury */}
      <div className="card bg-surface-50 border-neutral-100">
        <p className="text-xs font-semibold text-neutral-700 mb-2">
          Note Méthodologique — Détection de Drift (Evidently AI Standard)
        </p>
        <p className="text-xs text-neutral-500 leading-relaxed">
          Le module compare les distributions de référence (données historiques/d'entraînement) aux données récentes (fenêtres d'inférence).
          Pour les variables numériques (volume, AHT, coûts), le test de <b>Kolmogorov-Smirnov (KS-test)</b> à 2 échantillons mesure si les fonctions de répartition cumulée sont significativement différentes (seuil p-value &lt; 0.05).
          Pour les variables catégorielles (seniority, contract), la <b>Total Variation Distance (TVD)</b> quantifie les décalages de fréquences relatives.
        </p>
      </div>
    </div>
  )
}
