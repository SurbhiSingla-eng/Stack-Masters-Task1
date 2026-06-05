import { useState } from 'react'
import { api } from '../../lib/api'
import { useAsyncAction } from '../../hooks/useApi'
import { Modal, Spinner } from '../ui'

export default function SubmitModal({ open, onClose, assignmentId, onSubmitted }) {
  const [form, setForm] = useState({ student_id: '', student_label: '', raw_code: '', submitted_at: '' })
  const { run, loading, error } = useAsyncAction()
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async () => {
    if (!form.student_id.trim() || !form.raw_code.trim()) return
    const payload = {
      student_id:    form.student_id.trim(),
      student_label: form.student_label.trim() || undefined,
      raw_code:      form.raw_code,
      ...(form.submitted_at ? { submitted_at: new Date(form.submitted_at).toISOString() } : {}),
    }
    await run(() => api.submissions.create(assignmentId, payload))
    onSubmitted && onSubmitted()
    onClose()
    setForm({ student_id: '', student_label: '', raw_code: '', submitted_at: '' })
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Submission">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label block mb-1.5">Student ID *</label>
            <input className="input w-full" placeholder="e.g. student_001" value={form.student_id} onChange={e => set('student_id', e.target.value)} />
          </div>
          <div>
            <label className="label block mb-1.5">Display Name</label>
            <input className="input w-full" placeholder="e.g. Alice" value={form.student_label} onChange={e => set('student_label', e.target.value)} />
          </div>
        </div>
        <div>
          <label className="label block mb-1.5">Submission Time</label>
          <input type="datetime-local" className="input w-full" value={form.submitted_at} onChange={e => set('submitted_at', e.target.value)} />
        </div>
        <div>
          <label className="label block mb-1.5">Code *</label>
          <textarea className="input w-full font-mono text-xs" rows={12} placeholder="Paste student code here…" value={form.raw_code} onChange={e => set('raw_code', e.target.value)} />
        </div>
        {error && <div className="text-signal text-sm px-3 py-2 bg-signal-soft rounded-lg">{error}</div>}
        <div className="flex justify-end gap-3 pt-1">
          <button onClick={onClose} className="btn-ghost">Cancel</button>
          <button onClick={handleSubmit} disabled={loading || !form.student_id || !form.raw_code} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            {loading && <Spinner size="sm" />} Submit
          </button>
        </div>
      </div>
    </Modal>
  )
}
