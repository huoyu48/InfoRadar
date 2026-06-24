import { useState, useEffect } from 'react'
import { Plus, Radar } from 'lucide-react'
import { getTopics, createTopic, deleteTopic, getStats } from '../api.js'
import TopicCard from '../components/TopicCard.jsx'
import AddTopicModal from '../components/AddTopicModal.jsx'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const [topics, setTopics] = useState([])
  const [stats, setStats] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const navigate = useNavigate()

  const loadData = async () => {
    const [t, s] = await Promise.all([getTopics(), getStats()])
    setTopics(t)
    setStats(s)
  }

  useEffect(() => { loadData() }, [])

  const handleAdd = async (name, interval) => {
    await createTopic(name, interval)
    loadData()
  }

  const handleDelete = async (id) => {
    if (!confirm('确定删除这个话题？相关数据也会一并删除。')) return
    await deleteTopic(id)
    loadData()
  }

  const handleScan = (id) => {
    navigate(`/topic/${id}`)
  }

  return (
    <div>
      {/* 头部 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text">话题追踪</h1>
          <p className="text-sm text-text-muted mt-1">管理你的情报追踪话题</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 bg-primary text-white rounded-lg px-4 py-2 text-sm hover:bg-primary-hover transition-colors"
        >
          <Plus size={16} /> 添加话题
        </button>
      </div>

      {/* 统计栏 */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-card rounded-xl border border-border p-4 text-center">
            <div className="text-2xl font-bold text-primary">{stats.total_topics}</div>
            <div className="text-xs text-text-muted mt-1">追踪话题</div>
          </div>
          <div className="bg-card rounded-xl border border-border p-4 text-center">
            <div className="text-2xl font-bold text-success">{stats.total_findings}</div>
            <div className="text-xs text-text-muted mt-1">信息发现</div>
          </div>
          <div className="bg-card rounded-xl border border-border p-4 text-center">
            <div className="text-2xl font-bold text-warning">{stats.total_digests}</div>
            <div className="text-xs text-text-muted mt-1">情报摘要</div>
          </div>
        </div>
      )}

      {/* 话题网格 */}
      {topics.length === 0 ? (
        <div className="text-center py-20 text-text-muted">
          <Radar size={48} className="mx-auto mb-4 opacity-30" />
          <p>还没有追踪话题</p>
          <p className="text-sm mt-1">点击"添加话题"开始追踪你感兴趣的领域</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {topics.map((topic) => (
            <TopicCard
              key={topic.id}
              topic={topic}
              onScan={handleScan}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <AddTopicModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleAdd}
      />
    </div>
  )
}
