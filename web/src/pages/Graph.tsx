import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { GraphPayload, Topic } from '../lib/types'
import TopicGraph from '../components/TopicGraph'
import HealthBar from '../components/HealthBar'

export default function GraphPage() {
  const [graph, setGraph] = useState<GraphPayload | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])

  useEffect(() => {
    api.graph().then(setGraph)
    api.topics().then(setTopics)
  }, [])

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Topic graph</h2>
          <p>Prerequisites flow left → right. Node color tracks current recall.</p>
        </div>
      </div>
      {graph && <TopicGraph data={graph} />}
      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Topics</h3>
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Prereqs</th><th>Depends on this</th><th>Recall</th><th>Problems</th></tr>
          </thead>
          <tbody>
            {topics.map((t) => (
              <tr key={t.id}>
                <td>
                  <div>{t.name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{t.description}</div>
                </td>
                <td className="muted">{t.prerequisites.join(', ') || '—'}</td>
                <td className="muted">{t.dependents.join(', ') || '—'}</td>
                <td><HealthBar value={t.retrievability} /></td>
                <td>{t.problem_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
