import { Link } from 'react-router-dom'
import { Radar, ExternalLink } from 'lucide-react'

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-bg">
      {/* 顶栏 */}
      <header className="bg-card border-b border-border sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-text font-semibold">
            <Radar size={20} className="text-primary" />
            <span>InfoRadar</span>
          </Link>
          <a
            href="https://github.com/huoyu48/InfoRadar"
            target="_blank"
            rel="noreferrer"
            className="text-text-secondary hover:text-text flex items-center gap-1 text-sm"
          >
            <ExternalLink size={16} />
            <span>GitHub</span>
          </a>
        </div>
      </header>

      {/* 内容区 */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {children}
      </main>
    </div>
  )
}
