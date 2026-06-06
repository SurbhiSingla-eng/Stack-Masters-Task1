export function riskColor(risk) {
  return {
    critical: 'bg-signal-soft text-signal border-signal/30',
    high:     'bg-amber-soft  text-amber-700 border-amber/30',
    medium:   'bg-sky-soft    text-sky-700   border-sky/30',
    low:      'bg-jade-soft   text-jade-700  border-jade/30',
  }[risk] ?? 'bg-ink-700 text-ink-300 border-ink-600'
}

export function riskDot(risk) {
  return { critical: 'bg-signal', high: 'bg-amber', medium: 'bg-sky', low: 'bg-jade' }[risk] ?? 'bg-ink-400'
}

export function riskBar(risk) {
  return { critical: 'bg-signal', high: 'bg-amber', medium: 'bg-sky', low: 'bg-jade' }[risk] ?? 'bg-ink-400'
}

export function statusColor(status) {
  return {
    pending:   'bg-ink-700     text-ink-300',
    reviewing: 'bg-sky-soft    text-sky-700',
    confirmed: 'bg-signal-soft text-signal',
    dismissed: 'bg-ink-800     text-ink-500',
    escalated: 'bg-amber-soft  text-amber-700',
  }[status] ?? 'bg-ink-700 text-ink-300'
}

export function pct(n) {
  return `${Math.round((n ?? 0) * 100)}%`
}

export function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function heuristicLabel(name) {
  return {
    token_jaccard_3gram: '3-gram Jaccard',
    token_jaccard_5gram: '5-gram Jaccard',
    normalised_lcs:      'Normalised LCS',
    containment_5gram:   'Containment',
    cosine_tf:           'Cosine TF',
  }[name] ?? name
}

export function clsx(...args) {
  return args.filter(Boolean).join(' ')
}
