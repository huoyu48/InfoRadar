import { useState, useEffect, useRef } from 'react'
import { Loader2, CheckCircle2, Circle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { scanStream } from '../api.js'

const STAGES = [
  { key: 'planner', label: 'Planner — 规划搜索策略' },
  { key: 'researcher', label: 'Researcher — 搜索和收集信息' },
  { key: 'analyst', label: 'Analyst — 分析变化趋势' },
  { key: 'writer', label: 'Writer — 生成情报摘要' },
]

export default function ScanPanel({ topicId }) {
  const [stageStatus, setStageStatus] = useState({})
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    if (!topicId) return

    // 重置状态
    setStageStatus({})
    setResult(null)
    setError(null)

    esRef.current = scanStream(topicId, {
      onProgress: (data) => {
        setStageStatus((prev) => ({ ...prev, [data.stage]: 'running' }))
      },
      onComplete: (data) => {
        // 所有阶段标记完成
        setStageStatus({
          planner: 'done', researcher: 'done',
          analyst: 'done', writer: 'done',
        })
        setResult(data)
      },
      onError: (data) => {
        setError(data.error || '扫描失败')
      },
    })

    return () => esRef.current?.close()
  }, [topicId])

  return (
    <div className="bg-card rounded-xl border border-border p-5">
      <h3 className="font-semibold mb-4">扫描进度</h3>

      {/* 阶段列表 */}
      <div className="space-y-3 mb-6">
        {STAGES.map((stage) => {
          const status = stageStatus[stage.key]
          return (
            <div key={stage.key} className="flex items-center gap-3">
              {status === 'done' && <CheckCircle2 size={18} className="text-success" />}
              {status === 'running' && <Loader2 size={18} className="text-primary animate-spin" />}
              {!status && <Circle size={18} className="text-text-muted" />}
              <span className={`text-sm ${status === 'running' ? 'text-primary' : 'text-text-secondary'}`}>
                {stage.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* 错误 */}
      {error && (
        <div className="bg-danger/5 border border-danger/20 rounded-lg p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* 结果摘要 */}
      {result && (
        <div className="border-t border-border pt-4">
          <p className="text-sm text-text-secondary mb-2">
            新增 {result.new_entries} 条信息
          </p>
          <div className="bg-bg rounded-lg p-4 max-h-80 overflow-y-auto">
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>{result.digest}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
