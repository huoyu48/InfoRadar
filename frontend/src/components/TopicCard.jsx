import { Play, Eye, Trash2, Clock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const INTERVAL_LABEL = { 6: '6 小时', 12: '12 小时', 24: '每天', 168: '每周' }

export default function TopicCard({ topic, onScan, onDelete }) {
  const navigate = useNavigate()

  return (
    <div className="bg-card rounded-xl border border-border p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-semibold text-text">{topic.name}</h3>
        <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full">
          {INTERVAL_LABEL[topic.scan_interval_hours] || `${topic.scan_interval_hours}h`}
        </span>
      </div>

      <p className="text-sm text-text-muted mb-4 flex items-center gap-1">
        <Clock size={14} />
        创建于 {new Date(topic.created_at).toLocaleDateString('zh-CN')}
      </p>

      <div className="flex gap-2">
        <button
          onClick={() => onScan(topic.id)}
          className="flex-1 flex items-center justify-center gap-1.5 bg-primary text-white rounded-lg py-2 text-sm hover:bg-primary-hover transition-colors"
        >
          <Play size={14} /> 扫描
        </button>
        <button
          onClick={() => navigate(`/topic/${topic.id}`)}
          className="flex items-center justify-center gap-1.5 border border-border rounded-lg px-4 py-2 text-sm text-text-secondary hover:bg-bg transition-colors"
        >
          <Eye size={14} />
        </button>
        <button
          onClick={() => onDelete(topic.id)}
          className="flex items-center justify-center gap-1.5 border border-border rounded-lg px-4 py-2 text-sm text-danger hover:bg-danger/5 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}
