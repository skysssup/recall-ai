import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Review from './pages/Review'
import Problems from './pages/Problems'
import Graph from './pages/Graph'
import Analytics from './pages/Analytics'
import LogSolve from './pages/LogSolve'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="review" element={<Review />} />
          <Route path="problems" element={<Problems />} />
          <Route path="graph" element={<Graph />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="log" element={<LogSolve />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
