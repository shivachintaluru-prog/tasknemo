const BASE = ''

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  getDashboard: () => apiFetch<any>('/api/dashboard'),
  getTasks: (state?: string) => apiFetch<any>(`/api/tasks${state ? `?state=${state}` : ''}`),
  getTask: (id: string) => apiFetch<any>(`/api/tasks/${id}`),
  createTask: (data: any) => apiFetch<any>('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
  updateTask: (id: string, data: any) => apiFetch<any>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  closeTask: (id: string) => apiFetch<any>(`/api/tasks/${id}/close`, { method: 'POST' }),
  reopenTask: (id: string) => apiFetch<any>(`/api/tasks/${id}/reopen`, { method: 'POST' }),
  pinTask: (id: string) => apiFetch<any>(`/api/tasks/${id}/pin`, { method: 'POST' }),
  unpinTask: (id: string) => apiFetch<any>(`/api/tasks/${id}/unpin`, { method: 'POST' }),
  transitionTask: (id: string, state: string, reason?: string) =>
    apiFetch<any>(`/api/tasks/${id}/transition`, { method: 'POST', body: JSON.stringify({ state, reason }) }),
  bulkAction: (ids: string[], action: string) =>
    apiFetch<any>('/api/tasks/bulk', { method: 'POST', body: JSON.stringify({ ids, action }) }),
  getAnalyticsOverview: () => apiFetch<any>('/api/analytics/overview'),
  getResponseTimes: () => apiFetch<any>('/api/analytics/response-times'),
  getSyncLog: (limit = 20) => apiFetch<any>(`/api/analytics/sync-log?limit=${limit}`),
  getTrends: () => apiFetch<any>('/api/analytics/trends'),
  getQuality: () => apiFetch<any>('/api/analytics/quality'),
  getAlerts: () => apiFetch<any>('/api/analytics/alerts'),
  getSyncStatus: () => apiFetch<any>('/api/sync/status'),
  triggerRefresh: () => apiFetch<any>('/api/sync/refresh', { method: 'POST' }),
  getConfig: () => apiFetch<any>('/api/config'),
  updateConfig: (data: any) => apiFetch<any>('/api/config', { method: 'PATCH', body: JSON.stringify(data) }),
}
