import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Overview        from './pages/Overview'
import Forecasting     from './pages/Forecasting'
import Attrition       from './pages/Attrition'
import Scheduling      from './pages/Scheduling'
import WhatIf          from './pages/WhatIf'
import DriftMonitoring from './pages/DriftMonitoring'

export default function App() {
  return (
    <div className="flex min-h-screen bg-surface-50">
      <Sidebar />

      {/* Main content — offset by sidebar width */}
      <main className="ml-56 flex-1 p-8 min-h-screen">
        <div className="max-w-6xl mx-auto">
          <Routes>
            <Route path="/"           element={<Overview />} />
            <Route path="/forecast"   element={<Forecasting />} />
            <Route path="/attrition"  element={<Attrition />} />
            <Route path="/scheduling" element={<Scheduling />} />
            <Route path="/what-if"    element={<WhatIf />} />
            <Route path="/monitoring" element={<DriftMonitoring />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
