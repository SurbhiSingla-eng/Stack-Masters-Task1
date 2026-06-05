import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Play, AlertTriangle, Grid, Upload } from 'lucide-react'
import { useApi, useAsyncAction } from '../hooks/useApi'
import { api } from '../lib/api'
import { pct, fmtDate, riskColor } from '../lib/utils'
import { LoadingPane, ErrorPane, Spinner, RiskBadge } from '../components/ui'
import SubmitModal from '../components/dashboard/SubmitModal'

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="card p-5">
      <div className="label mb-2">{label}</div>
      <div className={`text-3xl font-display font-bold ${accent ?? 'text-ink-100'}`}>{value}</div>
      {sub && <div className="text-xs text-ink-500 mt-1">{sub}</div>}
    </div>
  )
}

function RiskPill({ label, count, risk }) {
  if (!count) return null
  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded-lg border ${riskColor(risk)}`}>
      <span className="text-xs font-medium capitalize">{label}</span>
      <span className="text-sm font-bold">{count}</span>
    </div>
  )
}

export default function DashboardPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [showSubmit, setShowSubmit] = useState(false)
  const { run, loading: running, error: runError } = useAsyncAction()
  const { data: stats, loading, error, reload } = useApi(() => api.stats(id), [id])

  const handleRun = async () => {
    await run(() => api.runs.trigger(id))
    reload()
  }

  if (loading) return <LoadingPane />
  if (error) return (
    <div className="p-8">
      <ErrorPane message={error} />
      <p className="text-center text-ink-500 text-sm mt-2">
        Make sure the backend is running and this assignment ID exists.
      </p>
    </div>
  )

  const rd = stats.risk_distribution
  const sd = stats.status_distribution

  return (
    <div className="p-8 animate-fade-in">

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="label mb-1">Assignment</div>
          <h1 className="font-display text-2xl font-bold text-ink-100">Similarity Dashboard</h1>
          <p className="text-ink-500 text-xs mt-1 font-mono">{id}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSubmit(true)}
            className="btn-ghost flex items-center gap-2 border border-ink-600"
          >
            <Upload className="w-4 h-4" /> Add Submission
          </button>
          <button
            onClick={handleRun}
            disabled={running}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {running ? <Spinner size="sm" /> : <Play className="w-4 h-4" />}
            Run Analysis
          </button>
        </div>
      </div>

      {runError && (
        <div className="mb-6 px-4 py-3 bg-signal-soft border border-signal/30 rounded-lg text-signal text-sm">
          {runError}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Submissions"  value={stats.total_submissions} sub={`${stats.total_pairs} pairs to check`} />
        <StatCard label="Flagged Pairs" value={stats.flagged_pairs}    sub={`${pct(stats.flagged_pct)} of all pairs`} accent={stats.flagged_pairs > 0 ? 'text-signal' : 'text-jade'} />
        <StatCard label="Avg Similarity" value={stats.avg_composite != null ? pct(stats.avg_composite) : '—'} sub="across flagged pairs" />
        <StatCard label="Last Run" value={stats.last_run_at ? fmtDate(stats.last_run_at) : 'Never'} sub={stats.last_run_at ? 'analysis complete' : 'click Run Analysis'} />
      </div>

      {/* Middle row */}
      <div className="grid grid-cols-3 gap-4 mb-8">

        {/* Risk breakdown */}
        <div className="card p-5">
          <div className="label mb-3">Risk Breakdown</div>
          <div className="space-y-2">
            <RiskPill label="Critical" count={rd.critical} risk="critical" />
            <RiskPill label="High"     count={rd.high}     risk="high" />
            <RiskPill label="Medium"   count={rd.medium}   risk="medium" />
            <RiskPill label="Low"      count={rd.low}      risk="low" />
          </div>
          {!rd.critical && !rd.high && !rd.medium && !rd.low && (
            <p className="text-xs text-ink-500 text-center py-4">Run analysis first</p>
          )}
        </div>

        {/* Review status */}
        <div className="card p-5">
          <div className="label mb-3">Review Status</div>
          <div className="space-y-2.5">
            {[
              ['Pending',   sd.pending,   'text-ink-300'],
              ['Reviewing', sd.reviewing, 'text-sky-400'],
              ['Confirmed', sd.confirmed, 'text-signal'],
              ['Dismissed', sd.dismissed, 'text-ink-500'],
              ['Escalated', sd.escalated, 'text-amber-400'],
            ].map(([label, count, color]) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs text-ink-400">{label}</span>
                <span className={`text-sm font-medium ${color}`}>{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick nav */}
        <div className="flex flex-col gap-3">
          <button
            onClick={() => navigate(`/assignments/${id}/pairs`)}
            className="card p-5 flex-1 flex items-center gap-3 hover:border-ink-400 transition-all text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-signal/10 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-signal" />
            </div>
            <div>
              <div className="font-medium text-ink-100 text-sm">Flagged Pairs</div>
              <div className="text-xs text-ink-500">Filter &amp; review</div>
            </div>
          </button>
          <button
            onClick={() => navigate(`/assignments/${id}/matrix`)}
            className="card p-5 flex-1 flex items-center gap-3 hover:border-ink-400 transition-all text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-sky/10 flex items-center justify-center">
              <Grid className="w-5 h-5 text-sky" />
            </div>
            <div>
              <div className="font-medium text-ink-100 text-sm">Similarity Matrix</div>
              <div className="text-xs text-ink-500">Heatmap view</div>
            </div>
          </button>
        </div>
      </div>

      {/* Highest pair */}
      {stats.highest_pair && (
        <div className="card p-5">
          <div className="label mb-3">Highest-Scoring Pair</div>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 text-ink-100 font-medium">
                <span>{stats.highest_pair.submission_a?.student_label ?? stats.highest_pair.submission_a?.student_id}</span>
                <span className="text-ink-500">×</span>
                <span>{stats.highest_pair.submission_b?.student_label ?? stats.highest_pair.submission_b?.student_id}</span>
              </div>
              <div className="flex items-center gap-3 mt-2">
                <RiskBadge risk={stats.highest_pair.risk_level} />
                <span className="text-2xl font-display font-bold text-signal">
                  {pct(stats.highest_pair.composite_score)}
                </span>
              </div>
            </div>
            <button onClick={() => navigate(`/assignments/${id}/pairs`)} className="btn-ghost border border-ink-600">
              View All →
            </button>
          </div>
        </div>
      )}

      <SubmitModal
        open={showSubmit}
        onClose={() => setShowSubmit(false)}
        assignmentId={id}
        onSubmitted={reload}
      />
    </div>
  )
}
