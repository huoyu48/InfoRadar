import { useState } from 'react'
import { ChevronDown, ChevronRight, FileText } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

export default function DigestList({ digests }) {
  const [expandedId, setExpandedId] = useState(null)

  if (!digests || digests.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted text-sm">
        暂无历史摘要，触发一次扫描后这里会显示结果
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {digests.map((d) => {
        const isExpanded = expandedId === d.id
        return (
          <div key={d.id} className="bg-card rounded-xl border border-border overflow-hidden">
            <button
              onClick={() => setExpandedId(isExpanded ? null : d.id)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-bg transition-colors"
            >
              <FileText size={16} className="text-primary flex-shrink-0" />
              <span className="text-sm text-text-secondary flex-1">
                {new Date(d.created_at).toLocaleString('zh-CN')}
              </span>
              {isExpanded
                ? <ChevronDown size={16} className="text-text-muted" />
                : <ChevronRight size={16} className="text-text-muted" />
              }
            </button>
            {isExpanded && (
              <div className="px-4 pb-4 border-t border-border pt-3">
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown>{d.content}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
