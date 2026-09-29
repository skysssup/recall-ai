export interface Topic {
  id: string
  name: string
  description?: string | null
  stability: number
  difficulty: number
  retrievability: number
  practice_count: number
  last_reviewed_at?: string | null
  next_review_at?: string | null
  problem_count: number
  prerequisites: string[]
  dependents: string[]
}

export interface Problem {
  id: string
  title: string
  platform: string
  slug: string
  url?: string | null
  difficulty: string
  topic_id?: string | null
  topic_name?: string | null
  tags: string[]
  notes: string
  stability: number
  difficulty_score: number
  retrievability: number
  due_at?: string | null
  last_reviewed_at?: string | null
  review_count: number
  lapses: number
  created_at: string
  priority: number
}

export interface Solve {
  id: string
  problem_id?: string | null
  platform: string
  slug: string
  title: string
  difficulty: string
  verdict: string
  time_to_understand_s?: number | null
  time_to_write_s?: number | null
  num_submissions: number
  hints_used: number
  tags: string[]
  source: string
  created_at: string
  recall_strength?: number | null
  applied_rating?: number | null
}

export interface Dashboard {
  due_count: number
  learned_count: number
  problem_count: number
  topic_count: number
  health_score: number
  streak_days: number
  reviews_today: number
  weak_topics: { name: string; retrievability: number; difficulty: number }[]
  upcoming: Problem[]
  recent_solves: Solve[]
}

export interface GraphPayload {
  nodes: {
    id: string
    name: string
    description?: string | null
    stability: number
    difficulty: number
    retrievability: number
    practice_count: number
  }[]
  edges: { from: string; to: string; from_id: string; to_id: string }[]
  layers: string[][]
}

export interface SearchHit {
  kind: string
  id: string
  title: string
  subtitle: string
  score: number
}

export const RATING_LABELS: Record<number, { label: string; hint: string; key: string }> = {
  1: { label: 'Again', hint: 'Forgot', key: '1' },
  2: { label: 'Hard', hint: 'Struggled', key: '2' },
  3: { label: 'Good', hint: 'Correct', key: '3' },
  4: { label: 'Easy', hint: 'Trivial', key: '4' },
}
