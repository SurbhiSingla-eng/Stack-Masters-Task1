import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import { LoadingPane, ErrorPane, Empty } from '../components/ui'

function cellBg(score, risk) {
  if (score == null) return '#1A202C'
  if (risk === 'critical') return `rgba(232,69,69,${0.15 + score * 0.7})`
  if (risk === 'high')     return `rgba(245,158,11,${0.12 + score * 0.6})`
  if (risk === 'medium')   return `rgba(59,130,246,${0.10 + score * 0.5})`
  return `rgba(16,185,129,${0.08 + score * 0.35})`
}

function cellText(risk) {
  return { critical: '#E84545', high: '#F59E0B', medium: '#60A5FA', low: '#34D399' }[risk] ?? '#9AA3AE'
}

function Tooltip({ cell, x, y }) {
  if (!cell) return null
  return (
    <div
      className="fixed z-50 pointer-events-none bg-ink-700 border border-ink-600 rounded-lg px-3 py-2 text-xs shadow-xl"
      style={{ left: x + 12, top: y - 10 }}
    >
      <div className="font-medium text-ink-100 mb-1">
        {cell.student_a_label} × {cell.student_b_label}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-ink-400">Score:</span>
        <span className="font-mono font-medium" style={{ color: cellText(cell.risk_level) }}>
          {Math.round(cell.composite_score * 100)}%
        </span>
        <span className="capitalize text-ink-400">{cell.risk_level}</span>
      </div>
    </div>
  )
}

export default function MatrixPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [tooltip, setTooltip] = useState(null)
  const { data, loading, error } = useApi(() => api.matrix(id), [id])

  if (loading) return <LoadingPane />
  if (error)   return <div className="p-8"><ErrorPane message={error} /></div>

  const students = data.students ?? []
  const cells    = data.cells    ?? []

  if (students.length === 0) {
    return (
      <div className="p-8">
        <button onClick={() => navigate(`/assignments/${id}`)} className="btn-ghost mb-6">
          <ArrowLeft className="w-4 h-4 inline mr-1" /> Back
        </button>
        <Empty icon="⬜" title="No matrix data yet" subtitle="Run the analysis first." />
      </div>
    )
  }

  const lookup = {}
  cells.forEach(c => {
    lookup[`${c.student_a_label}||${c.student_b_label}`] = c
    lookup[`${c.student_b_label}||${c.student_a_label}`] = c
  })

  const cellSize = Math.max(52, Math.min(80, Math.floor(560 / students.length)))

  return (
    <div className="p-8 animate-fade-in">
      <div className="flex items-center gap-3 mb-8">
        <button onClick={() => navigate(`/assignments/${id}`)} className="btn-ghost">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="font-display text-xl font-bold text-ink-100">Similarity Matrix</h1>
          <p className="text-ink-500 text-sm">{students.length} students · hover a cell for detail</p>
        </div>
      </div>

      <div className="card p-6 inline-block max-w-full overflow-auto">
        <table className="border-separate border-spacing-1">
          <thead>
            <tr>
              <th style={{ width: 96 }} />
              {students.map(s => (
                <th key={s} style={{ width: cellSize }} className="pb-2">
                  <div
                    className="text-xs text-ink-400 font-medium truncate text-center"
                    style={{ maxWidth: cellSize, writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: 72 }}
                  >
                    {s}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {students.map((rowS, ri) => (
              <tr key={rowS}>
                <td className="pr-3 text-right">
                  <span className="text-xs text-ink-400 font-medium truncate" style={{ maxWidth: 90, display: 'inline-block' }}>
                    {rowS}
                  </span>
                </td>
                {students.map((colS, ci) => {
                  if (ri === ci) {
                    return (
                      <td key={colS} style={{ width: cellSize, height: cellSize }}>
                        <div
                          className="rounded flex items-center justify-center text-ink-600 text-xs"
                          style={{ width: cellSize, height: cellSize, background: '#131720' }}
                        >
                          —
                        </div>
                      </td>
                    )
                  }
                  const cell  = lookup[`${rowS}||${colS}`]
                  const score = cell ? cell.composite_score : null
                  const risk  = cell ? cell.risk_level : null
                  return (
                    <td key={colS} style={{ width: cellSize, height: cellSize }}>
                      <div
                        className="rounded flex items-center justify-center text-xs font-mono font-medium cursor-pointer transition-transform hover:scale-105"
                        style={{ width: cellSize, height: cellSize, background: cellBg(score, risk), color: score != null ? cellText(risk) : '#2D3748' }}
                        onMouseEnter={e => cell && setTooltip({ cell, x: e.clientX, y: e.clientY })}
                        onMouseMove={e  => cell && setTooltip(t => t ? { ...t, x: e.clientX, y: e.clientY } : t)}
                        onMouseLeave={() => setTooltip(null)}
                        onClick={() => cell && navigate(`/assignments/${id}/pairs`)}
                      >
                        {score != null ? `${Math.round(score * 100)}%` : '·'}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>

        <div className="flex items-center gap-6 mt-6 pt-4 border-t border-ink-700">
          <span className="label">Risk scale:</span>
          {[['Low','#34D399'],['Medium','#60A5FA'],['High','#F59E0B'],['Critical','#E84545']].map(([label, color]) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ background: color + '99' }} />
              <span className="text-xs text-ink-400">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {tooltip && <Tooltip {...tooltip} />}
    </div>
  )
}
