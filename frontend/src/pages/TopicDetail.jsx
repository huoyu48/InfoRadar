import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Play, Clock, Hash } from 'lucide-react'
import { getTopics, getDigests } from '../api.js'
import ScanPanel from '../components/ScanPanel.jsx'
import DigestList from '../components/DigestList.jsx'

export default function TopicDetail() {
  const { id } = useParams()
  const [topic, setTopic] = useState(null)
  const [digests, setDigests] = useState([])
  const [scanning, setScanning] = useState(false)
  const [scanKey, setScanKey] = useState(0)

  const INTERVAL_LABEL = { 6: '6 小时', 12: '12 小时', 24: '每天', 168: '每周' }

  const loadDigests = async () => {
    const data = await getDigests(id)
    setDigests(data)
  }

  useEffect(() => {
    const loadTopic = async () => {
      const topics = await getTopics()
      const found = topics.find((t) => String(t.id) === id)
      setTopic(found)
    }
    loadTopic()
    loadDigests()
  }, [id])

  const handleScan = () => {
    setScanning(true)
    setScanKey((k) => k + 1)  // 触发 ScanPanel 重新挂载
  }

  return (
    <div>
      {/* 返回按钮 */}
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text mb-6"
      >
        <ArrowLeft size={16} /> 返回列表
      </Link>

      {topic && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左列：话题信息 + 扫描 */}
          <div className="space-y-4">
            {/* 话题信息卡 */}
            <div className="bg-card rounded-xl border border-border p-5">
              <h2 className="text-xl font-bold mb-3">{topic.name}</h2>
              <div className="flex gap-4 text-sm text-text-secondary">
                <span className="flex items-center gap-1">
                  <Clock size={14} />
                  {INTERVAL_LABEL[topic.scan_interval_hours] || `${topic.scan_interval_hours}h`}
                </span>
                <span className="flex items-center gap-1">
                  <Hash size={14} />
                  ID: {topic.id}
                </span>
              </div>
            </div>

            {/* 扫描按钮 */}
            {!scanning && (
              <button
                onClick={handleScan}
                className="w-full flex items-center justify-center gap-2 bg-primary text-white rounded-xl py-3 hover:bg-primary-hover transition-colors"
              >
                <Play size={16} /> 开始扫描
              </button>
            )}

            {/* 扫描进度 */}
            {scanning && <ScanPanel key={scanKey} topicId={Number(id)} />}
          </div>

          {/* 右列：历史摘要 */}
          <div>
            <h3 className="font-semibold mb-4 text-text-secondary">历史摘要</h3>
            <DigestList digests={digests} />
          </div>
        </div>
      )}
    </div>
  )
}
