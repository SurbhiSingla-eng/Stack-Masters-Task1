import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ChevronDown, ChevronUp, Clock } from 'lucide-react'
import { useApi, useAsyncAction } from '../hooks/useApi'
import { api } from '../lib/api'
import { pct, fmtDate, heuristicLabel } from '../lib/utils'
import { LoadingPane, ErrorPane, Empty, RiskBadge, StatusBadge, ScoreBar, Select, Spinner } from '../components/ui'
import ExplainerModal from '../components/explainer/ExplainerModal'

const RISK_OPTS = [
  { value: '',         label: 'All risk levels' },
  { value: 'critical', label: 'Critical' },
  { value: 'high',     label: 'High' },
  { value: 'medium',   label: 'Medium' },
  { value: 'low',      label: 'Low' },
]

const STATUS_OPTS = [
  { value: '',          label: 'All statuses' },
  { value: 'pending',   label: 'Pending' },
  { value: 'reviewing', label: 'Reviewing' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'escalated', label: 'Escalated' },
]

const REVIEW_OPTS = [
  { value: 'reviewing', label: 'Mark reviewing' },
  { value: 'confirmed', label: 'Confirm copying' },
  { value: 'dismissed', label: 'Dismiss' },
  { value: 'escalated', label: 'Escalate' },
]

function ReviewDropdown({ pair, onReview }) {
  const [open, setOpen] = useState(false)
  const { run, loading } = useAsyncAction()

  const handle = async (status) => {
    setOpen(false)
    await run(() => onReview(pair.id, status))
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs text-ink-400 hover:text-ink-100 border border-ink-600 rounded px-2 py-1 transition-colors flex items-center gap-1"
      >
        {loading ? <Spinner size="sm" /> : 'Review'}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-ink-700 border border-ink-600 rounded-lg shadow-xl overflow-hidden w-40">
            {REVIEW_OPTS.map(o => (
              <button
                key={o.value}
                onClick={() => handle(o.value)}
                className="w-full text-left px-3 py-2 text-xs text-ink-200 hover:bg-ink-600 transition-colors"
              >
                {o.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function PairRow({ pair, onReview, onExplain, expanded, onToggle }) {
  const a = pair.submission_a?.student_label ?? pair.submission_a?.student_id ?? '?'
  const b = pair.submission_b?.student_label ?? pair.submission_b?.student_id ?? '?'
  const breakdown = pair.score_breakdown ?? {}

  return (
    <>
      <tr
        className="border-b border-ink-700 hover:bg-ink-700/40 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="font-medium text-ink-100 text-sm">{a}</span>
            <span className="text-ink-500 text-xs">×</span>
            <span className="font-medium text-ink-100 text-sm">{b}</span>
            {pair.timing_flag && (
              <Clock className="w-3.5 h-3.5 text-amber shrink-0" title="Near-simultaneous submission" />
            )}
          </div>
        </td>
        <td className="px-4 py-3 w-48">
          <ScoreBar score={pair.composite_score} risk={pair.risk_level} />
        </td>
        <td className="px-4 py-3"><RiskBadge risk={pair.risk_level} /></td>
        <td className="px-4 py-3"><StatusBadge status={pair.status} /></td>
        <td className="px-4 py-3 text-xs text-ink-500">{fmtDate(pair.flagged_at)}</td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => onExplain(pair)}
              className="text-xs text-sky-400 hover:text-sky-300 transition-colors font-medium"
            >
              Why?
            </button>
            <ReviewDropdown pair={pair} onReview={onReview} />
          </div>
        </td>
        <td className="px-4 py-3 text-ink-500">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </td>
      </tr>

      {expanded && (
        <tr className="bg-ink-800/60 border-b border-ink-700">
          <td colSpan={7} className="px-6 py-4">
            <div className="grid grid-cols-5 gap-4">
              {Object.entries(breakdown).map(([key, val]) => (
                <div key={key}>
                  <div className="text-xs text-ink-500 mb-1">{heuristicLabel(key)}</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 bg-ink-700 rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-sky" style={{ width: `${Math.round(val * 100)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-ink-300">{Math.round(val * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
            {pair.instructor_note && (
              <div className="mt-3 text-xs text-ink-400 italic border-t border-ink-700 pt-3">
                Note: {pair.instructor_note}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

export default function FlaggedPairsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ risk_level: '', status: '', page: 1 })
  const [expandedId, setExpandedId] = useState(null)
  const [explainPair, setExplainPair] = useState(null)

  const { data, loading, error, reload } = useApi(
    () => api.flaggedPairs.list(id, { ...filters, page_size: 25 }),
    [id, filters.risk_level, filters.status, filters.page]
  )

  const { run: doReview } = useAsyncAction()

  const handleReview = async (pairId, status) => {
    await doReview(() => api.flaggedPairs.review(id, pairId, { status }))
    reload()
  }

  const setFilter = (key, val) => setFilters(f => ({ ...f, [key]: val, page: 1 }))

  return (
    <div className="p-8 animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(`/assignments/${id}`)} className="btn-ghost">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="font-display text-xl font-bold text-ink-100">Flagged Pairs</h1>
          <p className="text-ink-500 text-sm">
            {data ? `${data.total} pair${data.total !== 1 ? 's' : ''} found` : 'Loading…'}
          </p>
        </div>
      </div>

      <div className="flex gap-3 mb-6">
        <Select value={filters.risk_level} onChange={v => setFilter('risk_level', v)} options={RISK_OPTS} />
        <Select value={filters.status}     onChange={v => setFilter('status', v)}     options={STATUS_OPTS} />
      </div>

      {loading ? <LoadingPane /> : error ? <ErrorPane message={error} /> : (
        <>
          {data.items.length === 0 ? (
            <Empty icon="✓" title="No pairs match these filters" subtitle="Try clearing the filters or run the analysis first." />
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-ink-700 bg-ink-800/80">
                    <th className="px-4 py-3 text-left label">Pair</th>
                    <th className="px-4 py-3 text-left label">Score</th>
                    <th className="px-4 py-3 text-left label">Risk</th>
                    <th className="px-4 py-3 text-left label">Status</th>
                    <th className="px-4 py-3 text-left label">Flagged</th>
                    <th className="px-4 py-3 text-left label">Actions</th>
                    <th className="px-4 py-3 w-8" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map(pair => (
                    <PairRow
                      key={pair.id}
                      pair={pair}
                      expanded={expandedId === pair.id}
                      onToggle={() => setExpandedId(expandedId === pair.id ? null : pair.id)}
                      onReview={handleReview}
                      onExplain={setExplainPair}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.total > 25 && (
            <div className="flex items-center justify-center gap-3 mt-6">
              <button disabled={filters.page <= 1} onClick={() => setFilter('page', filters.page - 1)} className="btn-ghost disabled:opacity-40">← Previous</button>
              <span className="text-sm text-ink-400">Page {filters.page}</span>
              <button disabled={filters.page * 25 >= data.total} onClick={() => setFilter('page', filters.page + 1)} className="btn-ghost disabled:opacity-40">Next →</button>
            </div>
          )}
        </>
      )}

      <ExplainerModal
        open={!!explainPair}
        pair={explainPair}
        assignmentId={id}
        onClose={() => setExplainPair(null)}
        onReview={handleReview}
      />
    </div>
  )
}
