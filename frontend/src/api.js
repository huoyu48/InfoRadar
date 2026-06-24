const BASE = '/api'

async function request(url, options = {}) {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || `HTTP ${res.status}`)
  }
  return res.json()
}

// 话题 CRUD
export const getTopics = () => request('/topics')

export const createTopic = (name, scan_interval_hours = 24) =>
  request('/topics', {
    method: 'POST',
    body: JSON.stringify({ name, scan_interval_hours }),
  })

export const deleteTopic = (id) =>
  request(`/topics/${id}`, { method: 'DELETE' })

// 扫描
export const triggerScan = (topicId) =>
  request(`/scans/${topicId}`, { method: 'POST' })

// SSE 扫描流（返回 EventSource 实例）
export function scanStream(topicId, { onProgress, onComplete, onError }) {
  const es = new EventSource(`${BASE}/scans/${topicId}/stream`)

  es.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data)
    onProgress?.(data)
  })

  es.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data)
    onComplete?.(data)
    es.close()
  })

  es.addEventListener('error', (e) => {
    // 浏览器 EventSource 自动发的 error 事件（连接断开）
    if (e.data) {
      onError?.(JSON.parse(e.data))
    }
    es.close()
  })

  return es
}

// 历史摘要
export const getDigests = (topicId, limit = 10) =>
  request(`/digests/${topicId}?limit=${limit}`)

// 统计信息
export const getStats = () => request('/stats')
