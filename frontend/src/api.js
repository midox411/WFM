// Central API client — maps to REAL endpoints from api/routers/
// forecast.py  → GET /api/v1/forecast/intraday?limit=N
// attrition.py → GET /api/v1/attrition/agents
// optimization → GET /api/v1/optimization/schedule?day=N&agent_id=N

const BASE = '/api/v1'

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// forecast/intraday → { count: number, data: [{interval_15min, call_volume?, ...}] }
export const getForecastIntraday = (limit = 336) =>
  fetchJSON(`/forecast/intraday?limit=${limit}`)

// attrition/agents → { active_agents: number, data: [{agent_id, status, contract_type, seniority_level, base_hourly_cost}] }
export const getAttritionAgents = () => fetchJSON('/attrition/agents')

// optimization/schedule → { total_shifts_slots: number, schedule: [{agent_id, day, slot, assigned}] }
export const getSchedule = (day = null, agentId = null) => {
  const params = new URLSearchParams()
  if (day !== null) params.append('day', day)
  if (agentId !== null) params.append('agent_id', agentId)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return fetchJSON(`/optimization/schedule${qs}`)
}

// Root health check → { status, message }
export const getHealth = () => fetch('/api/v1/../').then(r => r.json()).catch(() => null)

// simulator/what-if → { summary, intraday }
export const getWhatIfSimulation = (volChangePct = 0, headcountDelta = 0, absenteeismPct = 5) => {
  const params = new URLSearchParams({
    volume_change_pct: volChangePct,
    headcount_delta: headcountDelta,
    absenteeism_rate_pct: absenteeismPct,
  })
  return fetchJSON(`/simulator/what-if?${params.toString()}`)
}

// monitoring/drift → { status, global_summary, forecasting_drift, attrition_drift, last_check_timestamp }
export const getDriftAnalysis = () => fetchJSON('/monitoring/drift')
