// Shared utility functions

// Parse interval_15min string like "2024-01-01 08:00:00" → display label "08:00"
export function formatSlotLabel(intervalStr) {
  if (!intervalStr) return ''
  const d = new Date(intervalStr)
  if (isNaN(d.getTime())) {
    // Try fallback for strings like "2024-01-01T08:00:00"
    return intervalStr.slice(11, 16) || intervalStr
  }
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export function formatDate(intervalStr) {
  if (!intervalStr) return ''
  const d = new Date(intervalStr)
  if (isNaN(d.getTime())) return intervalStr.slice(0, 10)
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}

// Derive a risk tier from seniority_level + hourly cost heuristics
// (the API has no risk_score field — we compute a proxy)
export function computeRisk(agent) {
  const seniorityScore = { junior: 3, mid: 2, senior: 1 }
  const score = seniorityScore[agent.seniority_level] ?? 2
  // Part-time agents have higher turnover risk
  const contractMult = agent.contract_type === 'part_time' ? 1.4 : 1.0
  const raw = score * contractMult
  if (raw >= 3.5) return { label: 'Élevé', tier: 'high', pct: Math.min(95, 55 + raw * 10) }
  if (raw >= 2.0) return { label: 'Moyen', tier: 'medium', pct: Math.min(70, 30 + raw * 10) }
  return { label: 'Faible', tier: 'low', pct: Math.max(10, raw * 10) }
}

export function fmt(n, decimals = 0) {
  return Number(n).toLocaleString('fr-FR', { maximumFractionDigits: decimals })
}

// Slot index 0–47 → "08:00" – "19:45" (8h open, 48 × 15min)
export function slotToTime(slot) {
  const totalMin = 8 * 60 + slot * 15
  const h = Math.floor(totalMin / 60).toString().padStart(2, '0')
  const m = (totalMin % 60).toString().padStart(2, '0')
  return `${h}:${m}`
}

// Day index 0–6 → "Lun", "Mar", etc.
export const DAY_NAMES = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
