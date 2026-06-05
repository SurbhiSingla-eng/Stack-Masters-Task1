import { useState } from 'react'
import { api } from '../../lib/api'
import { useAsyncAction } from '../../hooks/useApi'
import { Modal, Spinner } from '../ui'

const LANGS = ['python', 'java', 'javascript', 'c', 'cpp', 'unknown']

export default function NewAssignmentModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState({ course_id: '', title: '', language: 'python', due_at: '' })
  const { run, loading, error } = useAsyncAction()
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async () => {
    if (!form.course_id.trim() || !form.title.trim()) return
    const payload = {
      course_id: form.course_id.trim(),
      title:     form.title.trim(),
      language:  form.language,
      ...(form.due_at ? { due_at: new Date(form.due_at).toISOString() } : {}),
    }
    const assignment = await run(() => api.assignments.create(payload))
    onCreate(assignment)
    setForm({ course_id: '', title: '', language: 'python', due_at: '' })
  }

  return (
    <Modal open={open} onClose={onClose} title="New Assignment">
      <div className="space-y-4">
        <div>
          <label className="label block mb-1.5">Course ID *</label>
          <input className="input w-full" placeholder="e.g. CS101-2024" value={form.course_id} onChange={e => set('course_id', e.target.value)} />
        </div>
        <div>
          <label className="label block mb-1.5">Assignment Title *</label>
          <input className="input w-full" placeholder="e.g. Sorting Algorithms" value={form.title} onChange={e => set('title', e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label block mb-1.5">Language</label>
            <select className="input w-full" value={form.language} onChange={e => set('language', e.target.value)}>
              {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="label block mb-1.5">Due Date</label>
            <input type="datetime-local" className="input w-full" value={form.due_at} onChange={e => set('due_at', e.target.value)} />
          </div>
        </div>
        {error && <div className="text-signal text-sm px-3 py-2 bg-signal-soft rounded-lg">{error}</div>}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onClose} className="btn-ghost">Cancel</button>
          <button onClick={handleSubmit} disabled={loading || !form.course_id || !form.title} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            {loading && <Spinner size="sm" />} Create Assignment
          </button>
        </div>
      </div>
    </Modal>
  )
}
