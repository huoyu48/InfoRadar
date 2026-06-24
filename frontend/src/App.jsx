import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import TopicDetail from './pages/TopicDetail.jsx'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/topic/:id" element={<TopicDetail />} />
      </Routes>
    </Layout>
  )
}

export default App
