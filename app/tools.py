"""InfoRadar 工具函数集 — 搜索、抓取、知识库读写、规则引擎"""
import re
import hashlib
import sqlite3
from datetime import datetime

import httpx
import chromadb
from tavily import TavilyClient

from app.config import get_settings
from app.models import Finding


# ── 单例客户端 ──

_tavily: TavilyClient | None = None
_chroma: chromadb.ClientAPI | None = None  # type: ignore
_db: sqlite3.Connection | None = None


def get_tavily() -> TavilyClient:
    global _tavily
    if _tavily is None:
        _tavily = TavilyClient(api_key=get_settings().tavily_api_key)
    return _tavily


def get_chroma() -> chromadb.ClientAPI:  # type: ignore
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(path=get_settings().chroma_dir)
    return _chroma


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        settings = get_settings()
        import os
        os.makedirs(os.path.dirname(settings.sqlite_path), exist_ok=True)
        _db = sqlite3.connect(settings.sqlite_path)
        _db.row_factory = sqlite3.Row
    return _db


# ── 数据库初始化 ──

def init_db():
    """创建 SQLite 三张表（如果不存在）"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            scan_interval_hours INTEGER DEFAULT 24,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT DEFAULT '',
            company TEXT DEFAULT '',
            published_at TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            relevance_score INTEGER DEFAULT 0,
            tier TEXT DEFAULT 'hot',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            new_entries_count INTEGER DEFAULT 0,
            sources TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()


# ── 搜索 ──

def web_search(query: str, max_results: int = 5) -> list[dict]:
    """搜索互联网，返回结果列表"""
    client = get_tavily()
    response = client.search(query, max_results=max_results)
    results = []
    for item in response.get("results", []):
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "content": item.get("content", ""),  # Tavily 自带摘要
            "score": item.get("score", 0),
        })
    return results


# ── 网页抓取 ──

def fetch_page(url: str) -> str:
    """抓取网页正文，返回纯文本"""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 InfoRadar/1.0"})
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        # 移除 script 和 style
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000]  # 截断，避免存太多
    except Exception:
        return ""


# ── 去重与哈希 ──

def url_exists(url: str, topic_id: int) -> bool:
    """检查该 URL 是否已存在于某个话题下"""
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM findings WHERE url = ? AND topic_id = ?",
        (url, topic_id),
    ).fetchone()
    return row is not None


def content_hash(text: str) -> str:
    """计算文本的 MD5 哈希，用于去重"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ── 混合存储写入 ──

def save_finding(finding: Finding, full_content: str = ""):
    """同时写 SQLite（结构化字段）+ ChromaDB（语义内容）"""
    # 1. SQLite：存 url、title、company、score 等结构化字段
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO findings (topic_id, url, title, company, content_hash,
           relevance_score, tier, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (finding.topic_id, finding.url, finding.title, finding.company,
         finding.content_hash, finding.relevance_score, finding.tier,
         finding.created_at),
    )
    conn.commit()
    # 回填自增 ID，供 ChromaDB 使用
    finding.id = cur.lastrowid

    # 2. ChromaDB：存网页正文（语义检索用）
    if full_content:
        chroma = get_chroma()
        collection = chroma.get_or_create_collection(name=f"topic_{finding.topic_id}")
        collection.add(
            ids=[str(finding.id)],
            documents=[full_content],
            metadatas=[{"url": finding.url, "tier": finding.tier}],
        )


# ── 规则引擎（零 token 消耗）──

def detect_changes(topic_id: int, new_findings: list[Finding]) -> dict:
    """纯代码做变化检测：URL 去重、公司频率统计、版本号正则提取"""
    conn = get_db()
    existing_urls = {row["url"] for row in
                     conn.execute("SELECT url FROM findings WHERE topic_id = ?",
                                  (topic_id,)).fetchall()}
    new_items = [f for f in new_findings if f.url not in existing_urls]

    company_counts = {}
    for f in new_findings:
        if f.company:
            company_counts[f.company] = company_counts.get(f.company, 0) + 1

    version_changes = []
    for f in new_findings:
        match = re.search(r"v?(\d+\.\d+[\.\d]*)", f.title)
        if match:
            version_changes.append({"title": f.title, "version": match.group(1)})

    return {
        "new_items": [{"title": f.title, "url": f.url} for f in new_items],
        "new_items_count": len(new_items),
        "frequency_changes": company_counts,
        "version_changes": version_changes,
    }
