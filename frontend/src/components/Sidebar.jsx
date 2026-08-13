import { NavLink } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, UserX, CalendarCheck, Sliders, Activity } from 'lucide-react'

const NAV = [
  { to: '/',           icon: LayoutDashboard, label: 'Overview' },
  { to: '/forecast',   icon: TrendingUp,      label: 'Forecasting' },
  { to: '/attrition',  icon: UserX,           label: 'Attrition' },
  { to: '/scheduling', icon: CalendarCheck,   label: 'Scheduling' },
  { to: '/what-if',    icon: Sliders,         label: 'What-if Simulator' },
  { to: '/monitoring', icon: Activity,        label: 'Drift Monitoring' },
]

export default function Sidebar() {
  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-white border-r border-neutral-100 flex flex-col z-30">
      {/* Logo / Brand */}
      <div className="px-5 py-6 border-b border-neutral-100">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-accent-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">W</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-neutral-800 leading-tight">WFM Platform</p>
            <p className="text-[10px] text-neutral-400 leading-tight">Intelligence Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={16} strokeWidth={1.75} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-neutral-100">
        <p className="text-[10px] text-neutral-300 leading-relaxed">
          FastAPI + OR-Tools + SARIMA<br />Master Big Data & Cloud
        </p>
      </div>
    </aside>
  )
}
