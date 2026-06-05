import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { heuristicLabel, pct, riskColor } from '../../lib/utils'
import { Modal, LoadingPane, ErrorPane, RiskBadge, Spinner } from '../ui'
import { Clock, AlertTriangle, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react'

const SEVERITY_COLOR = {
  'very high': 'text-signal',
  'high':      'text-amber-400',
  'moderate':  'text-sky-400',
  'low':       'text-jade-400',
  'negligible':'text-ink-500',
}

const SEVERITY_BAR = {
  'very high': 'bg-signal',
  'high':      'bg-amber',
  'moderate':  'bg-sky',
  'low':       'bg-jade',
  'negligible':'bg-ink-600',
}

function HeuristicRow({ v }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-ink-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-ink-700/50 transition-colors"
      >
        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="text-sm text-ink-100 font-medium">{heuristicLabel(v.heuristic)}</span>
            {v.contributed && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-signal/10 text-signal border border-signal/20">signal</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            <div className="w-32 h-1.5 bg-ink-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${SEVERITY_BAR[v.severity] ?? 'bg-ink-600'}`}
                style={{ width: `${Math.round(v.score * 100)}%` }}
              />
            </div>
            <span className={`text-xs font-mono ${SEVERITY_COLOR[v.severity] ?? 'text-ink-400'}`}>
              {Math.round(v.score * 100)}% · {v.severity}
            </span>
          </div>
        </div>
        <span className="text-xs text-ink-500">w={v.weight.toFixed(2)}</span>
        {open ? <ChevronUp className="w-4 h-4 text-ink-500" /> : <ChevronDown className="w-4 h-4 text-ink-500" />}
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 border-t border-ink-700 bg-ink-800/60">
          <p className="text-xs text-ink-400 leading-relaxed">{v.finding}</p>
        </div>
      )}
    </div>
  )
}

function EvidenceBlock({ ev }) {
  const isNgrams = ev.kind === 'shared_ngrams'
  return (
    <div className="border border-ink-700 rounded-lg p-4">
      <div className="label mb-2">{isNgrams ? 'Shared Token Patterns' : 'Common Token Sequence'}</div>
      <p className="text-xs text-ink-500 mb-3">{ev.note}</p>
      <div className="flex flex-wrap gap-1.5">
        {isNgrams
          ? ev.tokens.map((phrase, i) => (
              <span key={i} className="font-mono text-xs bg-ink-700 border border-ink-600 px-2 py-1 rounded text-sky-300">
                {phrase}
              </span>
            ))
          : (
              <div className="font-mono text-xs text-ink-300 leading-loose">
                {ev.tokens.slice(0, 60).join(' ')}
                {ev.tokens.length > 60 && <span className="text-ink-600"> …</span>}
              </div>
            )
        }
      </div>
    </div>
  )
}

export default function ExplainerModal({ open, pair, assignmentId, onClose, onReview }) {
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    if (!open || !pair) return
    setData(null)
    setLoading(true)
    setError(null)
    api.flaggedPairs.explain(assignmentId, pair.id)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [open, pair && pair.id])

  if (!pair) return null

  const a = pair.submission_a ? (pair.submission_a.student_label || pair.submission_a.student_id) : '?'
  const b = pair.submission_b ? (pair.submission_b.student_label || pair.submission_b.student_id) : '?'

  const handleReview = async (status) => {
    setReviewing(true)
    try {
      await onReview(pair.id, status)
      onClose()
    } finally {
      setReviewing(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Why flagged: ${a} × ${b}`}>
      {loading && <LoadingPane />}
      {error   && <ErrorPane message={error} />}
      {data && (
        <div className="space-y-6 animate-fade-in">

          {/* Summary banner */}
          <div className={`rounded-xl p-4 border ${riskColor(data.risk_level)}`}>
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <RiskBadge risk={data.risk_level} />
                  <span className="font-display font-bold text-lg">{pct(data.composite_score)}</span>
                  {data.timing_flag && (
                    <span className="flex items-center gap-1 text-xs text-amber-400">
                      <Clock className="w-3 h-3" /> Near-simultaneous
                    </span>
                  )}
                </div>
                <p className="text-sm leading-relaxed opacity-90">{data.summary}</p>
              </div>
            </div>
          </div>

          {/* Key findings */}
          <div>
            <div className="label mb-3">Key Findings</div>
            <ul className="space-y-2">
              {data.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-ink-300">
                  <span className="text-signal mt-0.5 shrink-0">•</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>

          {/* Heuristic breakdown */}
          <div>
            <div className="label mb-3">Heuristic Breakdown</div>
            <div className="space-y-2">
              {data.heuristic_verdicts.map(v => (
                <HeuristicRow key={v.heuristic} v={v} />
              ))}
            </div>
          </div>

          {/* Evidence */}
          {data.evidence && data.evidence.length > 0 && (
            <div>
              <div className="label mb-3">Evidence</div>
              <div className="space-y-3">
                {data.evidence.map((ev, i) => (
                  <EvidenceBlock key={i} ev={ev} />
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          <div className="bg-ink-700/60 rounded-xl p-4 border border-ink-600">
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-jade mt-0.5 shrink-0" />
              <div>
                <div className="label mb-1">Recommendation</div>
                <p className="text-sm text-ink-300 leading-relaxed">{data.recommendation}</p>
              </div>
            </div>
          </div>

          {/* Review actions */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-ink-700">
            <span className="text-xs text-ink-500 self-center mr-1">Mark as:</span>
            {[
              { status: 'reviewing', label: 'Reviewing',     cls: 'border-sky/40 text-sky-400 hover:bg-sky/10' },
              { status: 'confirmed', label: 'Confirmed copy', cls: 'border-signal/40 text-signal hover:bg-signal/10' },
              { status: 'dismissed', label: 'Dismiss',        cls: 'border-ink-600 text-ink-400 hover:bg-ink-700' },
              { status: 'escalated', label: 'Escalate',       cls: 'border-amber/40 text-amber-400 hover:bg-amber/10' },
            ].map(function(item) {
              return (
                <button
                  key={item.status}
                  disabled={reviewing}
                  onClick={() => handleReview(item.status)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-40 ${item.cls}`}
                >
                  {reviewing ? <Spinner size="sm" /> : item.label}
                </button>
              )
            })}
          </div>

        </div>
      )}
    </Modal>
  )
}
