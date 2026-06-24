import { useState } from 'react'
import { X } from 'lucide-react'

const INTERVALS = [
  { value: 6, label: '6 小时' },
  { value: 12, label: '12 小时' },
  { value: 24, label: '每天（推荐）' },
  { value: 168, label: '每周' },
]

export default function AddTopicModal({ open, onClose, onSubmit }) {
  const [name, setName] = useState('')
  const [interval, setInterval] = useState(24)

  if (!open) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim()) return
    onSubmit(name.trim(), interval)
    setName('')
    setInterval(24)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩层 */}
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />

      {/* 弹窗内容 */}
      <form
        onSubmit={handleSubmit}
        className="relative bg-card rounded-xl shadow-xl p-6 w-full max-w-md mx-4"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-text-muted hover:text-text"
        >
          <X size={18} />
        </button>

        <h2 className="text-lg font-semibold mb-4">添加追踪话题</h2>

        <label className="block text-sm text-text-secondary mb-1">话题名称</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="如：上海 AI Agent 实习"
          className="w-full border border-border rounded-lg px-3 py-2 mb-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          autoFocus
        />

        <label className="block text-sm text-text-secondary mb-1">扫描频率</label>
        <select
          value={interval}
          onChange={(e) => setInterval(Number(e.target.value))}
          className="w-full border border-border rounded-lg px-3 py-2 mb-6 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          {INTERVALS.map((i) => (
            <option key={i.value} value={i.value}>{i.label}</option>
          ))}
        </select>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 border border-border rounded-lg py-2 text-sm text-text-secondary hover:bg-bg"
          >
            取消
          </button>
          <button
            type="submit"
            className="flex-1 bg-primary text-white rounded-lg py-2 text-sm hover:bg-primary-hover"
          >
            添加
          </button>
        </div>
      </form>
    </div>
  )
}
