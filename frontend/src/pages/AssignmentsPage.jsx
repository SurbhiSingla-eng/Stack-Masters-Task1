import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, ChevronRight, Calendar } from 'lucide-react'
import { fmtDate } from '../lib/utils'
import { Empty } from '../components/ui'
import NewAssignmentModal from '../components/dashboard/NewAssignmentModal'

function getStored() {
  try { return JSON.parse(localStorage.getItem('sp_assignments') || '[]') } catch { return [] }
}
function addStored(a) {
  const all = getStored().filter(x => x.id !== a.id)
  localStorage.setItem('sp_assignments', JSON.stringify([a, ...all]))
}

export default function AssignmentsPage() {
  const [assignments, setAssignments] = useState(getStored)
  const [showNew, setShowNew] = useState(false)
  const navigate = useNavigate()

  const langColor = lang => ({
    python: 'text-sky-400', java: 'text-amber-400',
    javascript: 'text-jade-400', c: 'text-signal', cpp: 'text-signal',
  }[lang] ?? 'text-ink-400')

  return (
    <div className="p-8 max-w-4xl mx-auto animate-fade-in">

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-100">Assignments</h1>
          <p className="text-ink-400 text-sm mt-1">Select an assignment to view its similarity panel.</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowNew(true)}>
          + New Assignment
        </button>
      </div>

      {assignments.length === 0 ? (
        <Empty
          icon="📋"
          title="No assignments yet"
          subtitle="Create your first assignment to start analysing submissions."
        />
      ) : (
        <div className="space-y-3">
          {assignments.map(a => (
            <button
              key={a.id}
              onClick={() => navigate(`/assignments/${a.id}`)}
              className="w-full card p-5 flex items-center gap-4 hover:border-ink-400 transition-all text-left group"
            >
              <div className="w-10 h-10 rounded-lg bg-ink-700 flex items-center justify-center shrink-0">
                <BookOpen className="w-5 h-5 text-ink-300" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-ink-100 truncate">{a.title}</div>
                <div className="flex items-center gap-3 mt-1">
                  <span className={`text-xs font-mono ${langColor(a.language)}`}>{a.language}</span>
                  <span className="text-xs text-ink-500">{a.course_id}</span>
                  {a.due_at && (
                    <span className="text-xs text-ink-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />{fmtDate(a.due_at)}
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-ink-500 group-hover:text-ink-300 transition-colors" />
            </button>
          ))}
        </div>
      )}

      <NewAssignmentModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreate={(a) => {
          addStored(a)
          setAssignments(getStored())
          setShowNew(false)
          navigate(`/assignments/${a.id}`)
        }}
      />
    </div>
  )
}
