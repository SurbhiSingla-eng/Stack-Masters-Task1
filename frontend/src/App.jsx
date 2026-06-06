import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { BookOpen, AlertTriangle, Plus } from 'lucide-react'
import AssignmentsPage    from './pages/AssignmentsPage'
import DashboardPage      from './pages/DashboardPage'
import FlaggedPairsPage   from './pages/FlaggedPairsPage'
import MatrixPage         from './pages/MatrixPage'
import NewAssignmentModal from './components/dashboard/NewAssignmentModal'

function Sidebar() {
  const [showNew, setShowNew] = useState(false)
  const navigate = useNavigate()

  return (
    <>
      <aside className="w-56 shrink-0 bg-ink-900 border-r border-ink-700 flex flex-col h-screen sticky top-0">

        {/* Logo */}
        <div className="px-5 pt-6 pb-5 border-b border-ink-800">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-signal flex items-center justify-center">
              <AlertTriangle className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-display font-bold text-sm text-ink-100 leading-tight">Signal Panel</div>
              <div className="text-xs text-ink-500">Code Similarity</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-ink-700 text-ink-100 font-medium'
                  : 'text-ink-400 hover:text-ink-200 hover:bg-ink-800'
              }`
            }
          >
            <BookOpen className="w-4 h-4" /> Assignments
          </NavLink>
        </nav>

        {/* New assignment */}
        <div className="px-3 py-4 border-t border-ink-800">
          <button
            onClick={() => setShowNew(true)}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-ink-400 hover:text-ink-100 hover:bg-ink-800 transition-colors"
          >
            <Plus className="w-4 h-4" /> New Assignment
          </button>
        </div>
      </aside>

      <NewAssignmentModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreate={(assignment) => {
          setShowNew(false)
          navigate(`/assignments/${assignment.id}`)
        }}
      />
    </>
  )
}

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto">
        <Routes>
          <Route path="/"                       element={<AssignmentsPage />} />
          <Route path="/assignments/:id"         element={<DashboardPage />} />
          <Route path="/assignments/:id/pairs"   element={<FlaggedPairsPage />} />
          <Route path="/assignments/:id/matrix"  element={<MatrixPage />} />
        </Routes>
      </main>
    </div>
  )
}
