const BASE = '/api/v1'

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  if (res.status === 204) return null
  return res.json()
}

const get = (path) => request('GET', path)
const post = (path, body) => request('POST', path, body)
const patch = (path, body) => request('PATCH', path, body)

export const api = {
  assignments: {
    create: (data) => post('/assignments', data),
    get: (id) => get(`/assignments/${id}`),
    list: () => get('/assignments'),
  },

  submissions: {
    create: (assignmentId, data) =>
      post(`/assignments/${assignmentId}/submissions`, data),
    list: (assignmentId) =>
      get(`/assignments/${assignmentId}/submissions`),
  },

  runs: {
    trigger: (assignmentId, threshold = 0.45) =>
      post(`/assignments/${assignmentId}/runs`, { threshold }),
    get: (assignmentId, runId) =>
      get(`/assignments/${assignmentId}/runs/${runId}`),
  },

  flaggedPairs: {
    list: (assignmentId, params = {}) => {
      const q = new URLSearchParams()
      if (params.risk_level) q.set('risk_level', params.risk_level)
      if (params.status) q.set('status', params.status)
      if (params.min_score != null) q.set('min_score', params.min_score)
      if (params.page) q.set('page', params.page)
      if (params.page_size) q.set('page_size', params.page_size)
      return get(`/assignments/${assignmentId}/flagged-pairs?${q}`)
    },

    review: (assignmentId, pairId, data) =>
      patch(`/assignments/${assignmentId}/flagged-pairs/${pairId}`, data),

    explain: (assignmentId, pairId) =>
      get(`/assignments/${assignmentId}/flagged-pairs/${pairId}/explain`),
  },

  matrix: (assignmentId) =>
    get(`/assignments/${assignmentId}/matrix`),

  stats: (assignmentId) =>
    get(`/assignments/${assignmentId}/stats`),
}
