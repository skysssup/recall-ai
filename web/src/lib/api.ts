import type { Dashboard, GraphPayload, Problem, SearchHit, Solve, Topic } from './types'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<{ status: string }>('/api/health'),
  dashboard: () => req<Dashboard>('/api/dashboard'),
  topics: () => req<Topic[]>('/api/topics'),
  graph: () => req<GraphPayload>('/api/topics/graph'),
  problems: (params?: Record<string, string | boolean | number>) => {
    const q = new URLSearchParams()
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
      }
    }
    const qs = q.toString()
    return req<Problem[]>(`/api/problems${qs ? `?${qs}` : ''}`)
  },
  createProblem: (body: Record<string, unknown>) =>
    req<Problem>('/api/problems', { method: 'POST', body: JSON.stringify(body) }),
  updateProblem: (id: string, body: Record<string, unknown>) =>
    req<Problem>(`/api/problems/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteProblem: (id: string) => req<{ ok: boolean }>(`/api/problems/${id}`, { method: 'DELETE' }),
  review: (id: string, rating: number, duration_sec = 0, note = '') =>
    req(`/api/problems/${id}/reviews`, {
      method: 'POST',
      body: JSON.stringify({ rating, duration_sec, note }),
    }),
  queue: (limit = 20) => req<Problem[]>(`/api/reviews/queue?limit=${limit}`),
  history: () => req<unknown[]>('/api/reviews/history'),
  reviewStats: () => req<{ last_30_days: Record<string, number>; by_rating: Record<string, number>; total: number }>('/api/reviews/stats'),
  search: (q: string) => req<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}`),
  analytics: () => req<{
    health_score: number
    streak_days: number
    topics: { name: string; retrievability: number; stability: number; difficulty: number; practice_count: number }[]
    difficulty_breakdown: Record<string, number>
  }>('/api/analytics/overview'),
  settings: () => req<{ daily_goal: number; api_token: string; onboarded: boolean }>('/api/settings'),
  saveSettings: (body: { daily_goal?: number }) =>
    req('/api/settings', { method: 'POST', body: JSON.stringify(body) }),
  exportBundle: () => req<Record<string, unknown>>('/api/export'),
  importBundle: (data: Record<string, unknown>) =>
    req('/api/import', { method: 'POST', body: JSON.stringify({ data, merge: true }) }),
  manualSolve: (body: Record<string, unknown>) =>
    req<Solve>('/api/capture/manual', { method: 'POST', body: JSON.stringify(body) }),
}
