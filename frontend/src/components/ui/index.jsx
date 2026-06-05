import { riskColor, statusColor } from '../../lib/utils'

export function Spinner({ size = 'md' }) {
  const s = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' }[size]
  return <div className={`${s} border-2 border-ink-600 border-t-signal rounded-full animate-spin`} />
}

export function LoadingPane() {
  return (
    <div className="flex items-center justify-center py-24">
      <Spinner size="lg" />
    </div>
  )
}

export function ErrorPane({ message }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <div className="text-signal text-2xl">⚠</div>
      <p className="text-ink-400 text-sm">{message}</p>
    </div>
  )
}

export function Empty({ icon = '◌', title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-2 text-center">
      <div className="text-3xl text-ink-600">{icon}</div>
      <p className="text-ink-300 font-medium">{title}</p>
      {subtitle && <p className="text-ink-500 text-sm">{subtitle}</p>}
    </div>
  )
}

export function RiskBadge({ risk }) {
  return <span className={`badge border ${riskColor(risk)}`}>{risk}</span>
}

export function StatusBadge({ status }) {
  return <span className={`badge ${statusColor(status)}`}>{status}</span>
}

export function ScoreBar({ score, risk }) {
  const colors = { critical: 'bg-signal', high: 'bg-amber', medium: 'bg-sky', low: 'bg-jade' }
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-ink-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${colors[risk] ?? 'bg-ink-400'}`}
          style={{ width: `${Math.round(score * 100)}%` }}
        />
      </div>
      <span className="text-xs font-mono text-ink-300 w-8 text-right">
        {Math.round(score * 100)}%
      </span>
    </div>
  )
}

export function Modal({ open, onClose, title, children }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-ink-800 border border-ink-600 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-slide-up">
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-700">
          <h2 className="font-display font-semibold text-ink-100">{title}</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-100 text-xl leading-none">×</button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  )
}

export function Select({ value, onChange, options, className = '' }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className={`input cursor-pointer ${className}`}
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}
