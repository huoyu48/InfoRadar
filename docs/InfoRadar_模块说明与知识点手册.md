## InfoRadar 模块说明与源码手册

配合《InfoRadar 项目设计方案》使用，按开发顺序编排。每写一个模块前先看这个文档，搞清楚"这段代码在做什么"和"涉及哪些知识点"。

> 标记说明：✅ = 完整源码（可直接照敲） | 📝 = 核心逻辑预览（第 5 周前端组件）

---

### 项目整体架构（先看这个再动手）

```
数据流向：

Celery Beat 定时触发（每个话题各自的频率）
    │
    ▼
┌──────────────────────────────────────────────────┐
│  app/tasks.py            ← 定时调度 + 任务定义     │
│  app/config.py           ← 配置管理（✅ 已写好）   │
└────────────┬─────────────────────────────────────┘
             │ 触发话题扫描
             ▼
┌──────────────────────────────────────────────────┐
│  app/graph.py            ← LangGraph 状态图编排   │
│  app/models.py           ← 数据模型定义           │
│                                                    │
│  ┌─ 扫描流水线 ─────────────────────────────────┐ │
│  │  planner.py   → 生成搜索查询                  │ │
│  │  researcher.py → 搜索 + LLM 打分 + 过滤存储   │ │
│  │  analyst.py    → 规则检测 + LLM 总结          │ │
│  │  writer.py     → 生成情报摘要                  │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌─ 归档流程（独立调度）────────────────────────┐ │
│  │  archiver.py   → 旧条目压缩摘要 + 冷热分层    │ │
│  └──────────────────────────────────────────────┘ │
└────────────┬─────────────────────────────────────┘
             │ 读写数据
             ▼
┌──────────────────────────────────────────────────┐
│  app/tools.py            ← 工具函数集中管理        │
│                                                    │
│  混合存储：                                        │
│  ├─ SQLite   → 结构化数据（岗位/公司/时间/URL）    │
│  └─ ChromaDB → 语义数据（网页正文/摘要向量）       │
└────────────┬─────────────────────────────────────┘
             │ API 对外暴露
             ▼
┌──────────────────────────────────────────────────┐
│  app/main.py             ← FastAPI 入口（✅ 已写） │
│  app/static/index.html   ← Web UI（✅ 已写）      │
└──────────────────────────────────────────────────┘
```

---

## 第 1 周：基础骨架 + 搜索能力

> 目标：跑通"输入话题 → Planner 生成搜索策略 → Researcher 搜索互联网 → 过滤后存入知识库"。先让系统能搜到东西。

---

### 1.1 ✅ `.env` — 环境变量

**源码**：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
```

**这段代码做了什么**：四个配置项。DeepSeek 的三个控制 LLM 调用（Key、地址、模型名），Tavily 的一个控制搜索 API。`.gitignore` 排除了这个文件，防止 API Key 泄露。

⚠️ 把 `sk-xxxxxxxxxxxxxxxx` 和 `tvly-xxxxxxxxxxxxxxxx` 换成你自己的 Key。

**知识点**：

| 知识点                  | 说明                         | 面试怎么讲                                 |
| ----------------------- | ---------------------------- | ------------------------------------------ |
| **12-Factor App** | 配置存储于环境中             | "敏感信息通过 .env 注入，不硬编码在代码里" |
| **Tavily**        | 专为 AI Agent 设计的搜索 API | "比直接爬搜索引擎更稳定，返回结构化结果"   |

---

### 1.2 ✅ `requirements.txt` — 依赖列表

**源码**：

```
langgraph>=0.4.0
langchain>=0.3.0
langchain-openai>=0.3.0
langchain-core>=0.3.0
pydantic-settings>=2.0.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
celery>=5.4.0
redis>=5.0.0
chromadb>=0.5.0
tiktoken>=0.8.0
tavily-python>=0.5.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
sse-starlette>=2.0.0
```

**这段代码做了什么**：17 个运行时依赖。`langgraph` 做 Agent 编排，`langchain-openai` 对接 DeepSeek（兼容 OpenAI 接口），`tavily-python` 做搜索，`chromadb` 做向量存储，`celery` + `redis` 做定时任务，`sse-starlette` 做实时推送。

⚠️ `pydantic-settings` 需要单独装，不在 `pydantic` 里面。`uvicorn[standard]` 的方括号安装额外组件（websocket 等）。

---

### 1.3 ✅ `app/__init__.py` — 包标记

空文件。让 Python 把 `app/` 目录识别为包，其他文件才能 `from app.xxx import yyy`。

---

### 1.4 ✅ `app/config.py` — 配置管理

**源码**：

```python
"""InfoRadar 配置管理 — 自动从 .env 读取"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    tavily_api_key: str = ""
    chroma_dir: str = "data/chroma"
    sqlite_path: str = "data/inforadar.db"
    archive_after_days: int = 30
    min_relevance_score: int = 3
    model_config = {"env_file": ".env"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

**这段代码做了什么**：`Settings` 继承 `BaseSettings`，从 `.env` 自动加载值并做类型校验。`get_settings()` 用全局变量做单例，整个应用只创建一次。`archive_after_days=30` 控制多少天前的数据需要归档，`min_relevance_score=3` 控制搜索结果的最低入库存数。

**知识点**：

| 知识点                      | 说明                     | 面试怎么讲                                                   |
| --------------------------- | ------------------------ | ------------------------------------------------------------ |
| **pydantic-settings** | 自动类型校验 + .env 加载 | "配置项有类型检查，类型错启动就报错"                         |
| **单例模式**          | 全局只创建一个实例       | "用 `_settings` 全局变量 + None 判断，效果等同 @lru_cache" |
| **配置外置**          | 运行时可调不改代码       | "归档天数、最低分数线都在 .env 里，改配置不用重新部署"       |

---

### 1.5 ✅ `app/models.py` — 数据模型

**源码**：

```python
"""InfoRadar 数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict


# ── SQLite 结构化数据模型 ──

@dataclass
class Topic:
    """用户配置的话题"""
    id: int = 0
    name: str = ""                          # 话题名称，如"上海Agent实习"
    scan_interval_hours: int = 24           # 扫描间隔（小时）
    created_at: str = ""
    is_active: bool = True


@dataclass
class Finding:
    """一条信息发现"""
    id: int = 0
    topic_id: int = 0
    url: str = ""
    title: str = ""
    company: str = ""                       # 提取的公司名（可为空）
    published_at: str = ""
    content_hash: str = ""                  # md5 hash，用于去重
    relevance_score: int = 0                # 相关度 1-5
    tier: str = "hot"                       # hot / cold / archive
    created_at: str = ""


# ── LangGraph 状态 ──

class RadarState(TypedDict):
    """主扫描流水线的共享状态"""
    topic: Topic
    search_queries: list[str]               # Planner 产出
    findings: list[Finding]                 # Researcher 产出
    rule_changes: dict                      # 规则引擎产出
    analysis: str                           # Analyst LLM 总结
    digest: str                             # Writer 产出的摘要
    new_entries_count: int
    sources: list[str]


class ArchiveState(TypedDict):
    """Archiver 归档流程的共享状态"""
    topic: Topic
    stale_entries: list[Finding]
    grouped_entries: dict[str, list[Finding]]
    summaries: list[str]
    metrics: dict
```

**知识点**：

| 知识点                 | 说明                         | 面试怎么讲                                                    |
| ---------------------- | ---------------------------- | ------------------------------------------------------------- |
| **@dataclass**   | 自动生成 `__init__` 等方法 | "比手写 class 简洁，适合纯数据容器"                           |
| **TypedDict**    | 给 dict 加类型提示           | "LangGraph 用它校验状态结构，key 写错直接报错"                |
| **tier 三态**    | hot / cold / archive         | "热区保留原文可检索，冷区保留原文低频检索，归档区存 LLM 摘要" |
| **content_hash** | 内容指纹防重复入库           | "同一篇文章从不同 URL 被搜到，hash 一样就跳过"                |

---

### 1.6 ✅ `app/tools.py` — 工具函数集

**源码**：

```python
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
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000]
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
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO findings (topic_id, url, title, company, content_hash,
           relevance_score, tier, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (finding.topic_id, finding.url, finding.title, finding.company,
         finding.content_hash, finding.relevance_score, finding.tier,
         finding.created_at),
    )
    conn.commit()
    finding.id = cur.lastrowid  # 回填自增 ID，供 ChromaDB 使用

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
```

⚠️ `get_or_create_collection` 不是 `create_collection`——后者在 collection 已存在时会报错。

⚠️ `init_db()` 用 `CREATE TABLE IF NOT EXISTS`，多次调用安全，不会清空数据。

**知识点**：

| 知识点                  | 说明                               | 面试怎么讲                                                         |
| ----------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| **混合存储**      | SQLite + ChromaDB 各取所长         | "结构化字段存 SQLite 做精确查询和统计，正文存 ChromaDB 做语义检索" |
| **规则引擎**      | 纯代码做确定性高的检测             | "URL 去重、频率统计、版本号提取用代码做，零 token 消耗，又快又准"  |
| **单例客户端**    | Tavily / ChromaDB 客户端只创建一次 | "用全局变量 + None 判断，避免每次搜索都重新建立连接"               |
| **SQLite 三张表** | topics + findings + digests        | "话题配置、信息发现、情报摘要分开存储，关系通过 topic_id 关联"     |

---

### 1.7 ✅ `app/planner.py` — Planner Agent

**源码**：

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import get_settings

settings = get_settings()

planner_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.3,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

PLANNER_PROMPT = """你是一个情报分析经理。给定一个追踪话题，你需要生成 3-5 个精准的搜索查询。
规则：混合使用通用搜索、定向站点搜索、技术关键词搜索。
请只输出查询列表，每行一个，不要编号。"""


def plan_searches(topic_name: str) -> list[str]:
    messages = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=f"话题：{topic_name}"),
    ]
    response = planner_llm.invoke(messages)
    queries = []
    for line in response.content.strip().split("\n"):
        q = line.strip()
        if q and q[0].isdigit():        # 去掉 "1. " 前缀
            q = q.split(".", 1)[-1].strip()
        if q:
            queries.append(q)
    return queries[:5]
```

⚠️ `openai_api_key` 和 `openai_api_base` 是 langchain-openai 的参数名，虽然看着像 OpenAI 专属，但 DeepSeek 兼容 OpenAI 接口。加 `# type: ignore` 消除 Pylance 误报。

**知识点**：

| 知识点                    | 说明                        | 面试怎么讲                                             |
| ------------------------- | --------------------------- | ------------------------------------------------------ |
| **SystemMessage**   | 给 LLM 的角色设定           | "Planner 被设定为情报经理，只输出搜索查询，不闲聊"     |
| **输出解析**        | 处理 LLM 返回的非结构化文本 | "LLM 有时会加编号前缀，用 split 和 strip 清洗"         |
| **temperature=0.3** | 适度创造性                  | "搜索策略需要一定多样性，不像安全扫描那样要完全确定性" |

---

### 1.8 ✅ `app/researcher.py` — Researcher Agent

**源码**：

```python
"""InfoRadar Researcher Agent — 搜索 → 打分 → 过滤 → 存储"""
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings
from app.models import Finding
from app.tools import web_search, fetch_page, url_exists, content_hash, save_finding

settings = get_settings()

scorer_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.0,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

SCORE_PROMPT = """请对以下搜索结果的相关度打分（1-5 分），5 分最高。
话题：{topic}

结果列表：
{items}

请只输出数字，每行一个，按顺序排列。"""


def score_results(topic_name: str, results: list[dict]) -> list[int]:
    """用 LLM 对搜索结果批量打分（1-5分）"""
    items_text = "\n".join(
        f"{i+1}. {r['title']} - {r['content'][:100]}"
        for i, r in enumerate(results)
    )
    messages = [
        SystemMessage(content="你是一个信息质量评估专家，只输出数字。"),
        HumanMessage(content=SCORE_PROMPT.format(topic=topic_name, items=items_text)),
    ]
    response = scorer_llm.invoke(messages)
    # 解析输出：逐行扫描找数字
    scores = []
    for line in response.content.strip().split("\n"):
        for char in line.strip():
            if char.isdigit():
                scores.append(int(char))
                break
    while len(scores) < len(results):
        scores.append(3)  # 解析不够就补 3 分
    return scores[:len(results)]


def research(topic_name: str, topic_id: int, queries: list[str]) -> list[Finding]:
    """搜索 → 打分 → 过滤 → 存储"""
    # 1. 搜索
    all_results = []
    for query in queries:
        all_results.extend(web_search(query, max_results=5))

    # 2. 批次内 URL 去重
    seen = set()
    all_results = [r for r in all_results if r["url"] not in seen and not seen.add(r["url"])]

    # 3. LLM 打分
    scores = score_results(topic_name, all_results)

    # 4. 过滤 + 存储
    findings = []
    for result, score in zip(all_results, scores):
        if score < settings.min_relevance_score:
            continue
        if url_exists(result["url"], topic_id):
            continue
        full_content = fetch_page(result["url"]) if score >= 4 else result.get("content", "")
        finding = Finding(
            topic_id=topic_id, url=result["url"], title=result.get("title", ""),
            content_hash=content_hash(full_content), relevance_score=score,
            tier="hot", created_at=datetime.now().isoformat(),
        )
        save_finding(finding, full_content)
        findings.append(finding)
    return findings
```

⚠️ `not seen.add(r["url"])` 这个写法很巧妙——`set.add()` 返回 `None`，`not None` 是 `True`，所以第一次遇到新 URL 时条件为 True（保留），重复时为 False（过滤）。

**知识点**：

| 知识点             | 说明                     | 面试怎么讲                                                   |
| ------------------ | ------------------------ | ------------------------------------------------------------ |
| **批量打分** | 多条结果一次 LLM 调用    | "不逐条打分，打包发给 LLM 一次评完，省 token"                |
| **质量关卡** | 入库前先过滤             | "低分丢弃 + URL 去重 + 高分才抓全文，三层过滤保证知识库质量" |
| **分级抓取** | 4-5 分抓全文，3 分存摘要 | "不是所有结果都值得抓全文，按分数分级控制成本"               |

---

## 第 2 周：完整流水线

> 目标：Analyst 做变化分析 + Writer 生成摘要 + Archiver 归档旧数据。串联完整 4 Agent 流水线。

---

### 2.1 ✅ `app/analyst.py` — Analyst Agent（核心差异化）

**源码**：

```python
"""InfoRadar Analyst Agent — 两阶段分析：规则检测 + LLM 总结"""
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings
from app.models import Finding
from app.tools import detect_changes

settings = get_settings()

analyst_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.3,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

ANALYST_PROMPT = """你是一个情报分析师。基于检测结果，撰写简短的趋势分析。
话题：{topic}
要求：关注变化趋势、频率异动、新出现的实体。不要重复罗列原始数据。"""


def analyze(topic_name: str, topic_id: int, new_findings: list[Finding]) -> dict:
    """两阶段分析：规则检测 + LLM 总结"""
    # 阶段一：规则检测（零 token）
    rule_changes = detect_changes(topic_id, new_findings)

    has_changes = (
        rule_changes["new_items_count"] > 0
        or len(rule_changes["frequency_changes"]) > 0
        or len(rule_changes["version_changes"]) > 0
    )

    if not has_changes:
        return {"rule_changes": rule_changes, "analysis": "本次扫描未发现明显变化。"}

    # 阶段二：LLM 总结（只处理规则检测发现的变化）
    changes_summary = json.dumps(rule_changes, ensure_ascii=False, indent=2)

    messages = [
        SystemMessage(content=ANALYST_PROMPT.format(topic=topic_name)),
        HumanMessage(content=f"检测结果：\n{changes_summary}"),
    ]
    response = analyst_llm.invoke(messages)

    return {"rule_changes": rule_changes, "analysis": response.content}
```

⚠️ `json.dumps` 必须加 `ensure_ascii=False`，否则中文变成 `\uXXXX`。

**知识点**：

| 知识点                 | 说明                   | 面试怎么讲                                                             |
| ---------------------- | ---------------------- | ---------------------------------------------------------------------- |
| **两阶段分析**   | 代码做检测，LLM 做解释 | "确定性高的用代码（URL 去重、频率统计），需要理解的用 LLM（趋势归纳）" |
| **条件跳过**     | 没变化不调 LLM         | "检测到没有新增、没有频率变化，直接返回，省一次 LLM 调用"              |
| **LLM 不做发现** | 只看结构化结果         | "LLM 看到的是'新增 3 条、字节频率上升'，不是几百条原始数据"            |

---

### 2.2 ✅ `app/writer.py` — Writer Agent

**源码**：

```python
"""InfoRadar Writer Agent — 生成情报摘要"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings

settings = get_settings()

writer_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.3,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

WRITER_PROMPT = """你是一个情报简报撰稿人。基于分析结果，撰写情报摘要。
格式：## 本期要点（3-5 条） → ## 新增信息 → ## 趋势观察 → ## 来源
风格：简洁、有信息密度、不废话。"""


def write_digest(topic_name: str, analysis: str, sources: list[str]) -> str:
    sources_text = "\n".join(f"- {url}" for url in sources)
    messages = [
        SystemMessage(content=WRITER_PROMPT),
        HumanMessage(content=f"话题：{topic_name}\n分析结果：\n{analysis}\n来源：\n{sources_text}"),
    ]
    response = writer_llm.invoke(messages)
    return response.content
```

**知识点**：

| 知识点                    | 说明                            | 面试怎么讲                                         |
| ------------------------- | ------------------------------- | -------------------------------------------------- |
| **结构化 Prompt**   | 在 SystemMessage 里定义输出格式 | "用 Prompt 限定 Markdown 格式，输出直接可用"       |
| **temperature=0.3** | 摘要需要适度组织语言            | "不像安全扫描要完全确定，摘要需要一定的表达灵活性" |

---

### 2.3 ✅ `app/archiver.py` — Archiver Agent

**源码**：

```python
"""InfoRadar Archiver Agent — 旧条目压缩摘要 + 冷热分层"""
import json
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings
from app.models import Finding
from app.tools import get_db, get_chroma

settings = get_settings()

archiver_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.2,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

ARCHIVER_PROMPT = """你是一个数据归档专员。将以下信息条目压缩为一段简短的摘要。
要求：保留关键趋势和重要实体，去除重复和细节。"""


# ── 辅助函数 ──

def get_stale_entries(topic_id: int) -> list[Finding]:
    """查询超过归档天数的热区条目"""
    conn = get_db()
    cutoff = (datetime.now() - timedelta(days=settings.archive_after_days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM findings WHERE topic_id = ? AND tier = 'hot' AND created_at < ?",
        (topic_id, cutoff),
    ).fetchall()
    return [
        Finding(
            id=row["id"], topic_id=row["topic_id"], url=row["url"],
            title=row["title"], company=row["company"],
            content_hash=row["content_hash"], relevance_score=row["relevance_score"],
            tier=row["tier"], created_at=row["created_at"],
        )
        for row in rows
    ]


def group_by_week(entries: list[Finding]) -> dict[str, list[Finding]]:
    """按 ISO 周分组条目"""
    groups: dict[str, list[Finding]] = {}
    for entry in entries:
        dt = datetime.fromisoformat(entry.created_at)
        week_key = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
        groups.setdefault(week_key, []).append(entry)
    return groups


def summarize_group(entries: list[Finding]) -> str:
    """用 LLM 将一组条目压缩为摘要"""
    items_text = "\n".join(
        f"- {e.title} | {e.url} | {e.company or '未知公司'}"
        for e in entries
    )
    messages = [
        SystemMessage(content=ARCHIVER_PROMPT),
        HumanMessage(content=f"共 {len(entries)} 条条目：\n{items_text}"),
    ]
    response = archiver_llm.invoke(messages)
    return response.content


# ── 主函数 ──

def archive_topic(topic_id: int, topic_name: str) -> dict:
    """对一个话题执行归档"""
    stale = get_stale_entries(topic_id)
    if not stale:
        return {"archived_count": 0}

    stale_ids = [e.id for e in stale]
    groups = group_by_week(stale)
    summaries = []
    chroma = get_chroma()

    for week_key, entries in groups.items():
        summary = summarize_group(entries)
        summaries.append(summary)
        # 摘要存入 ChromaDB archive 区
        try:
            chroma.get_or_create_collection(name=f"topic_{topic_id}").add(
                ids=[f"archive_{week_key}"],
                documents=[summary],
                metadatas=[{"tier": "archive", "week": week_key}],
            )
        except Exception:
            pass  # ChromaDB ID 冲突时跳过

    # 原文标记为 cold（不删除！）
    conn = get_db()
    placeholders = ",".join("?" for _ in stale_ids)
    conn.execute(
        f"UPDATE findings SET tier = 'cold' WHERE id IN ({placeholders})",
        stale_ids,
    )
    conn.commit()

    # ChromaDB 也同步更新 tier 标记
    collection = chroma.get_or_create_collection(name=f"topic_{topic_id}")
    for entry_id in stale_ids:
        try:
            collection.update(ids=[str(entry_id)], metadatas=[{"tier": "cold"}])
        except Exception:
            pass  # 有些 Finding 没有写入 ChromaDB，ID 不存在会报错

    return {"archived_count": len(stale), "summaries_count": len(summaries)}
```

⚠️ `collection.update` 如果 ID 不存在会报错（有些 Finding 没有写入 ChromaDB），所以包在 try/except 里。

**知识点**：

| 知识点             | 说明                        | 面试怎么讲                                       |
| ------------------ | --------------------------- | ------------------------------------------------ |
| **冷热分层** | hot → cold → archive 三态 | "热区日常检索，冷区保留原文低频查，归档区存摘要" |
| **不删原文** | 只改 metadata 标记          | "归档不等于删除，冷数据保留保证可追溯性"         |
| **按周聚合** | 同一周的一起压缩            | "50 条招聘压成一段趋势总结，压缩比 5:1"          |

---

### 2.4 ✅ `app/graph.py` — LangGraph 状态图

**源码**：

```python
"""InfoRadar LangGraph 状态图 — 4 Agent 线性流水线"""
import json
from datetime import datetime

from langgraph.graph import StateGraph, START, END

from app.models import RadarState, Topic
from app.planner import plan_searches
from app.researcher import research
from app.analyst import analyze
from app.writer import write_digest
from app.tools import get_db


def planner_node(state: RadarState) -> dict:
    queries = plan_searches(state["topic"].name)
    return {"search_queries": queries}


def researcher_node(state: RadarState) -> dict:
    findings = research(state["topic"].name, state["topic"].id, state["search_queries"])
    return {"findings": findings, "sources": [f.url for f in findings],
            "new_entries_count": len(findings)}


def analyst_node(state: RadarState) -> dict:
    result = analyze(state["topic"].name, state["topic"].id, state["findings"])
    return {"rule_changes": result["rule_changes"], "analysis": result["analysis"]}


def writer_node(state: RadarState) -> dict:
    digest = write_digest(state["topic"].name, state["analysis"], state["sources"])
    # 保存摘要到 SQLite digests 表
    conn = get_db()
    conn.execute(
        """INSERT INTO digests (topic_id, content, new_entries_count, sources, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (state["topic"].id, digest, state["new_entries_count"],
         json.dumps(state["sources"], ensure_ascii=False),
         datetime.now().isoformat()),
    )
    conn.commit()
    return {"digest": digest}


def build_scan_graph():
    graph = StateGraph(RadarState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("writer", writer_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", END)
    return graph


scan_graph = build_scan_graph().compile()


def run_scan(topic: Topic) -> RadarState:
    initial_state = {"topic": topic, "search_queries": [], "findings": [],
                     "rule_changes": {}, "analysis": "", "digest": "",
                     "new_entries_count": 0, "sources": []}
    return scan_graph.invoke(initial_state)
```

**知识点**：

| 知识点                   | 说明                 | 面试怎么讲                                                   |
| ------------------------ | -------------------- | ------------------------------------------------------------ |
| **StateGraph**     | LangGraph 状态图编排 | "节点是执行单元，边是数据流向，state 在节点间共享"           |
| **节点返回 dict**  | 自动合并到状态       | "每个节点只返回需要更新的字段，LangGraph 自动 merge"         |
| **compile() 复用** | 编译一次全局使用     | "图编译后不可变，所有话题扫描复用同一个编译结果"             |
| **线性流水线**     | 没有循环和条件边     | "监控场景不需要打回重写，和 CodeGuard 的 ReAct 循环形成对比" |

---

## 第 3 周：定时调度 + Web UI

> 目标：Celery Beat 定时触发扫描，FastAPI 提供 API，Web UI 管理话题和查看摘要。

---

### 3.1 ✅ `app/tasks.py` — Celery 任务 + Beat 调度

**源码**：

```python
"""InfoRadar Celery 任务 + Beat 调度"""
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings
from app.models import Topic
from app.tools import get_db, init_db
from app.graph import run_scan
from app.archiver import archive_topic

celery_app = Celery("inforadar", broker="redis://localhost:6379/1",
                     backend="redis://localhost:6379/2")
celery_app.conf.update(
    task_serializer="json", accept_content=["json"],
    timezone="Asia/Shanghai", task_acks_late=True,
    worker_prefetch_multiplier=1,
    include=["app.tasks"],  # ⚠️ 必须包含自身！
)

celery_app.conf.beat_schedule = {
    "check-topics-every-hour": {
        "task": "app.tasks.check_and_scan",
        "schedule": crontab(minute=0),
    },
    "weekly-archive": {
        "task": "app.tasks.run_archive",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
}

init_db()  # Worker 启动时确保表存在


@celery_app.task(name="app.tasks.scan_topic")
def scan_topic(topic_id: int):
    """扫描单个话题"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM topics WHERE id = ?", (topic_id,)
    ).fetchone()
    if not row or not row["is_active"]:
        return {"skipped": True, "reason": "topic not found or inactive"}
    topic = Topic(
        id=row["id"], name=row["name"],
        scan_interval_hours=row["scan_interval_hours"],
        created_at=row["created_at"], is_active=bool(row["is_active"]),
    )
    result = run_scan(topic)
    # 更新最后扫描时间
    conn.execute(
        "UPDATE topics SET created_at = ? WHERE id = ?",
        (datetime.now().isoformat(), topic_id),
    )
    conn.commit()
    return {
        "topic_id": topic_id,
        "new_entries": result.get("new_entries_count", 0),
        "digest": result.get("digest", "")[:200],
    }


@celery_app.task(name="app.tasks.check_and_scan")
def check_and_scan():
    """每小时检查到期话题，触发扫描"""
    conn = get_db()
    topics = conn.execute(
        "SELECT * FROM topics WHERE is_active = 1"
    ).fetchall()
    now = datetime.now()
    triggered = []
    for row in topics:
        last_scan = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.min
        hours_since = (now - last_scan).total_seconds() / 3600
        if hours_since >= row["scan_interval_hours"]:
            scan_topic.delay(row["id"])
            triggered.append(row["id"])
    return {"triggered": triggered, "checked": len(topics)}


@celery_app.task(name="app.tasks.run_archive")
def run_archive():
    """每周日凌晨归档旧数据"""
    conn = get_db()
    topics = conn.execute(
        "SELECT id, name FROM topics WHERE is_active = 1"
    ).fetchall()
    results = []
    for row in topics:
        result = archive_topic(row["id"], row["name"])
        results.append({"topic_id": row["id"], **result})
    return {"archived": results}
```

⚠️ `include=["app.tasks"]` 是 CodeGuard 踩过的坑——没有这行 Celery Worker 发现不了任务，报 `NotRegistered`。

⚠️ Redis 用 `/1` 和 `/2` 两个数据库（broker 和 backend 分开），避免消息和结果混在一起。

**知识点**：

| 知识点                   | 说明                | 面试怎么讲                                                    |
| ------------------------ | ------------------- | ------------------------------------------------------------- |
| **Celery Beat**    | 定时任务调度器      | "Beat 是定时器，到点了把任务丢进 Redis 队列，Worker 消费执行" |
| **crontab**        | Cron 表达式配置频率 | "每小时检查到期话题，每周日凌晨 3 点归档"                     |
| **task_acks_late** | 完成后才确认        | "Worker 崩溃时任务自动重入队，不丢任务"                       |
| **.delay()**       | 异步发送任务        | "check_and_scan 里调 scan_topic.delay()，不阻塞当前任务"      |

---

### 3.2 ✅ `app/main.py` — FastAPI 入口（已写好）

已包含：话题 CRUD API（`POST/GET/DELETE /api/topics`）、手动扫描 + SSE 流式推送（`POST /api/scans/{id}` + `GET /api/scans/{id}/stream`）、历史摘要查询（`GET /api/digests/{id}`）、首页路由。

---

### 3.3 ✅ `app/static/index.html` — Web UI（已写好）

单文件前端。功能：添加/删除话题（可选扫描频率）、手动触发扫描（SSE 实时进度）、查看历史摘要。暗色主题。

---

### 3.4 ✅ `test_run.py` — 命令行测试（已写好）

不启动 Web 也能跑完整流水线。用法：`python test_run.py`。

---

## 第 4 周：启动与打磨

> 目标：跑通所有流程，优化 Prompt，准备面试。

---

### 4.1 启动命令

```bash
# 终端 1：Redis
~/bin/redis-server --daemonize yes

# 终端 2：Celery Worker
celery -A app.tasks worker --loglevel=info

# 终端 3：Celery Beat
celery -A app.tasks beat --loglevel=info

# 终端 4：FastAPI
uvicorn app.main:app --reload --port 8000
```

⚠️ 最小测试不需要 Celery：只开终端 4，在 Web UI 点"扫描"按钮即可。

---

### 4.2 常见踩坑速查

| 报错                                       | 原因                   | 解决                                           |
| ------------------------------------------ | ---------------------- | ---------------------------------------------- |
| `NotRegistered: scan_topic`              | Celery 没发现任务      | `include=["app.tasks"]` 加了吗？             |
| `ModuleNotFoundError: pydantic_settings` | 没装独立包             | `pip install pydantic-settings`              |
| `Collection already exists`              | 用了 create_collection | 换成 `get_or_create_collection`              |
| `no such table: findings`                | 没初始化数据库         | 确保启动时调了 `init_db()`                   |
| `400 Bad Request` from DeepSeek          | BASE_URL 多了 /v1      | 用 `https://api.deepseek.com` 不要加 `/v1` |
| Pylance 类型报错                           | openai_api_key 误报    | 加 `# type: ignore`                          |

---

## 第 5 周：React + Vite 前端

> 目标：用 React + Vite + Tailwind CSS 搭建独立前端项目，简洁浅色风格（Notion / Linear 风格），替代原有的单文件 HTML。

---

### 前端项目结构

```
frontend/
├── src/
│   ├── main.jsx              # 入口（✅ 已写好）
│   ├── App.jsx               # 路由 + 布局（✅ 已写好）
│   ├── api.js                # API 封装（✅ 已写好）
│   ├── components/
│   │   ├── Layout.jsx        # 侧边栏 + 顶栏布局
│   │   ├── TopicCard.jsx     # 单个话题卡片
│   │   ├── AddTopicModal.jsx # 添加话题弹窗
│   │   ├── ScanPanel.jsx     # 扫描进度面板（SSE）
│   │   └── DigestList.jsx    # 历史摘要列表
│   ├── pages/
│   │   ├── Dashboard.jsx     # 主页（话题管理）
│   │   └── TopicDetail.jsx   # 话题详情页（扫描 + 历史）
│   └── styles/
│       └── index.css         # Tailwind 基础样式（✅ 已写好）
├── index.html                # ✅ 已写好
├── package.json
├── vite.config.js            # ✅ 已写好（含 /api 代理）
├── tailwind.config.js
└── postcss.config.js
```

---

### 5.1 ✅ 项目初始化（已自动完成）

项目脚手架已通过 `npm create vite@latest frontend -- --template react` 创建，并安装了以下依赖：

```bash
cd frontend
npm install
npm install react-router-dom lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

---

### 5.2 ✅ `vite.config.js` — Vite 配置 + API 代理

**源码**：

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**这段代码做了什么**：三个插件（React 热更新 + Tailwind CSS），一个代理配置。开发时前端跑在 `localhost:5173`，所有 `/api` 开头的请求自动转发到 FastAPI 的 `localhost:8000`，开发环境零跨域问题。

**知识点**：

| 知识点                      | 说明                     | 面试怎么讲                                              |
| --------------------------- | ------------------------ | ------------------------------------------------------- |
| **Vite proxy**        | 开发时代理 API 请求      | "前后端分离开发，proxy 解决跨域，生产环境由 Nginx 处理" |
| **@tailwindcss/vite** | Tailwind v4 的 Vite 插件 | "不需要 postcss.config，直接作为 Vite 插件加载"         |

---

### 5.3 ✅ `src/styles/index.css` — Tailwind 主题配置

**源码**：

```css
@import "tailwindcss";

@theme {
  --color-primary: #3B82F6;
  --color-primary-hover: #2563EB;
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-danger: #EF4444;
  --color-bg: #FAFAFA;
  --color-card: #FFFFFF;
  --color-border: #E5E7EB;
  --color-text: #1F2937;
  --color-text-secondary: #6B7280;
  --color-text-muted: #9CA3AF;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
```

**这段代码做了什么**：Tailwind v4 用 `@theme` 定义自定义颜色变量，在组件里直接用 `bg-primary`、`text-text-secondary` 等 class。浅色背景 `#FAFAFA` + 白色卡片 + 蓝色主色调，Notion / Linear 风格。

---

### 5.4 ✅ `src/main.jsx` — 入口文件

**源码**：

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './styles/index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
```

**这段代码做了什么**：React 应用入口。`StrictMode` 开启严格模式（开发时帮你发现潜在问题），`BrowserRouter` 提供路由上下文，两个页面（`/` 和 `/topic/:id`）共享同一个 Layout。

---

### 5.5 ✅ `src/App.jsx` — 路由配置

**源码**：

```jsx
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
```

**这段代码做了什么**：两个路由。`/` 是 Dashboard（话题列表），`/topic/:id` 是话题详情页（扫描 + 历史摘要）。`Layout` 组件包裹所有页面，提供统一的顶栏。

---

### 5.6 ✅ `src/api.js` — API 封装层

**源码**：

```javascript
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

// SSE 扫描流
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
```

**这段代码做了什么**：统一封装所有 API 调用。`request()` 是底层函数，自动加 Content-Type、自动检查 HTTP 状态码、自动解析 JSON。`scanStream()` 封装 SSE 连接，通过回调函数接收三种事件（progress / complete / error）。组件里直接调 `getTopics()`、`scanStream()` 就行，不用关心 fetch 细节。

**知识点**：

| 知识点                | 说明                   | 面试怎么讲                                            |
| --------------------- | ---------------------- | ----------------------------------------------------- |
| **封装 fetch**  | 统一处理请求和错误     | "所有 API 调一层 request()，错误处理集中在一处"       |
| **EventSource** | 浏览器原生 SSE 客户端  | "不需要第三方库，addEventListener 监听自定义事件类型" |
| **可选链 ?.()** | 回调可能为空时安全调用 | "onProgress?.(data) 比 if (onProgress) 更简洁"        |

---

### 5.7 📝 `src/components/Layout.jsx` — 页面布局

**这个模块要做什么**：顶部导航栏，左侧 Logo + 标题，右侧 GitHub 链接。所有页面共享这个布局。

**核心逻辑预览**：

```jsx
import { Link } from 'react-router-dom'
import { Radar, Github } from 'lucide-react'

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
            <Github size={16} />
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
```

**知识点**：

| 知识点                  | 说明                 | 面试怎么讲                                            |
| ----------------------- | -------------------- | ----------------------------------------------------- |
| **sticky top-0**  | 滚动时顶栏固定在顶部 | "用 CSS sticky 而不是 fixed，不影响文档流"            |
| **children prop** | React 插槽模式       | "Layout 不关心内容是什么，只负责提供统一的顶栏和容器" |
| **lucide-react**  | 轻量 SVG 图标库      | "按需导入单个图标，不影响打包体积"                    |

---

### 5.8 📝 `src/components/TopicCard.jsx` — 话题卡片

**这个模块要做什么**：单个话题的展示卡片。显示话题名、扫描频率、创建时间，底部三个操作按钮（扫描、查看详情、删除）。

**核心逻辑预览**：

```jsx
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
        创建于 {topic.created_at}
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
```

⚠️ `bg-primary/10` 是 Tailwind 的透明度语法，等于 `background-color: rgba(59,130,246,0.1)`。

**知识点**：

| 知识点                    | 说明                    | 面试怎么讲                                              |
| ------------------------- | ----------------------- | ------------------------------------------------------- |
| **useNavigate**     | React Router 编程式导航 | "点查看详情按钮用 navigate() 跳转，比 Link 更灵活"      |
| **Props 回调**      | 操作委托给父组件        | "卡片不直接调 API，通过 onScan/onDelete 回调通知父组件" |
| **Tailwind 响应式** | 移动端适配              | "grid 布局自动响应，手机一列、平板两列、桌面三列"       |

---

### 5.9 📝 `src/components/AddTopicModal.jsx` — 添加话题弹窗

**这个模块要做什么**：模态弹窗表单，输入话题名 + 选择扫描频率，提交后关闭。

**核心逻辑预览**：

```jsx
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
```

**知识点**：

| 知识点             | 说明                       | 面试怎么讲                                                   |
| ------------------ | -------------------------- | ------------------------------------------------------------ |
| **模态弹窗** | 遮罩层 + 居中弹窗          | "fixed 全屏遮罩 + flex 居中弹窗，点遮罩关闭"                 |
| **受控组件** | React 表单标准模式         | "input 的 value 绑定 state，onChange 更新 state，单向数据流" |
| **条件渲染** | `if (!open) return null` | "不渲染 DOM 比 display:none 更干净，React 完全卸载组件"      |

---

### 5.10 📝 `src/components/ScanPanel.jsx` — 扫描进度面板

**这个模块要做什么**：调用 SSE 接口，实时展示 4 个 Agent 的执行状态。每个阶段从"等待"变为"进行中"再到"完成"，扫描结束后显示摘要。

**核心逻辑预览**：

```jsx
import { useState, useEffect, useRef } from 'react'
import { Loader2, CheckCircle2, Circle } from 'lucide-react'
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
          <div className="bg-bg rounded-lg p-4 text-sm whitespace-pre-wrap max-h-80 overflow-y-auto">
            {result.digest}
          </div>
        </div>
      )}
    </div>
  )
}
```

⚠️ `useEffect` 的 `return () => esRef.current?.close()` 是清理函数——组件卸载时关闭 SSE 连接，防止内存泄漏。

**知识点**：

| 知识点                   | 说明                  | 面试怎么讲                                                               |
| ------------------------ | --------------------- | ------------------------------------------------------------------------ |
| **useEffect 清理** | 组件卸载时关闭连接    | "return 一个清理函数，React 在卸载和重新执行 effect 前自动调用"          |
| **useRef**         | 存储不触发重渲染的值  | "EventSource 实例存 ref 里，不需要每次赋值都触发重渲染"                  |
| **animate-spin**   | Tailwind 内置旋转动画 | "Loader2 图标加 animate-spin 自动旋转，表示加载中"                       |
| **SSE 实时更新**   | 服务端单向推送        | "后端用 EventSourceResponse 推送进度，前端 addEventListener 实时更新 UI" |

---

### 5.11 📝 `src/components/DigestList.jsx` — 历史摘要列表

**这个模块要做什么**：时间线形式展示历史摘要。每条摘要显示时间和内容，内容区可折叠展开。

**核心逻辑预览**：

```jsx
import { useState } from 'react'
import { ChevronDown, ChevronRight, FileText } from 'lucide-react'

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
                {d.created_at}
              </span>
              {isExpanded
                ? <ChevronDown size={16} className="text-text-muted" />
                : <ChevronRight size={16} className="text-text-muted" />
              }
            </button>
            {isExpanded && (
              <div className="px-4 pb-4 text-sm whitespace-pre-wrap border-t border-border pt-3">
                {d.content}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

**知识点**：

| 知识点                        | 说明               | 面试怎么讲                                             |
| ----------------------------- | ------------------ | ------------------------------------------------------ |
| **手风琴交互**          | 同时只展开一条     | "expandedId 记录当前展开的 ID，点击其他自动收起上一条" |
| **whitespace-pre-wrap** | 保留换行但自动折行 | "LLM 输出的 Markdown 摘要有换行，pre-wrap 保留格式"    |

---

### 5.12 📝 `src/pages/Dashboard.jsx` — 主页

**这个模块要做什么**：Dashboard 页面。顶部标题 + 统计信息 + "添加话题"按钮，下方网格展示所有话题卡片。管理话题的增删和扫描触发。

**核心逻辑预览**：

```jsx
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
```

⚠️ `Promise.all([getTopics(), getStats()])` 并行请求两个接口，比 `await` 两次快一半。

**知识点**：

| 知识点                | 说明                                      | 面试怎么讲                                                |
| --------------------- | ----------------------------------------- | --------------------------------------------------------- |
| **Promise.all** | 并行执行多个异步操作                      | "话题列表和统计数据没有依赖关系，并行请求节省等待时间"    |
| **响应式网格**  | grid-cols-1 md:grid-cols-2 lg:grid-cols-3 | "Tailwind 断点系统，不同屏幕宽度自动切换列数"             |
| **confirm()**   | 浏览器原生确认弹窗                        | "删除操作前用 confirm 防误操作，生产环境可换成自定义弹窗" |

---

### 5.13 📝 `src/pages/TopicDetail.jsx` — 话题详情页

**这个模块要做什么**：话题详情页。左侧显示话题信息 + 扫描面板（SSE 实时进度），右侧显示历史摘要列表。点"开始扫描"后实时看到 4 个 Agent 的执行状态。

**核心逻辑预览**：

```jsx
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
```

⚠️ `scanKey` 用来强制 ScanPanel 重新挂载——每次点"开始扫描"时 `scanKey` 变化，React 销毁旧组件创建新组件，`useEffect` 重新执行，SSE 连接重新开始。这比在组件内部手动管理连接状态更干净。

**知识点**：

| 知识点                   | 说明                            | 面试怎么讲                                                             |
| ------------------------ | ------------------------------- | ---------------------------------------------------------------------- |
| **useParams**      | 获取 URL 路径参数               | "/topic/:id 中的 :id 通过 useParams() 获取"                            |
| **key 强制重渲染** | 改变 key 触发组件重新挂载       | "scanKey 变化 → React 销毁旧 ScanPanel → 新建新实例 → SSE 重新连接" |
| **useEffect 依赖** | `[id]` 表示 id 变化时重新执行 | "切换话题时自动重新加载数据，不需要手动刷新"                           |

---

### 5.14 📝 后端改动 — CORS + 统计 API

**这个模块要做什么**：在 `app/main.py` 中添加两处改动。一是 CORS 中间件允许前端跨域访问，二是新增 `/api/stats` 接口返回统计数据。

**核心逻辑预览（在 main.py 中添加）**：

```python
# ── 添加在文件顶部 import 区域 ──
from fastapi.middleware.cors import CORSMiddleware

# ── 添加在 app = FastAPI(...) 之后 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 添加在摘要查询 API 之后 ──
@app.get("/api/stats")
def get_stats():
    """返回系统统计信息"""
    conn = get_db()
    total_topics = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    total_findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    total_digests = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
    conn.close()
    return {
        "total_topics": total_topics,
        "total_findings": total_findings,
        "total_digests": total_digests,
    }
```

⚠️ `allow_origins` 要包含 Vite 开发服务器的地址 `http://localhost:5173`。生产环境部署后需要替换为实际域名。

**知识点**：

| 知识点             | 说明         | 面试怎么讲                                                |
| ------------------ | ------------ | --------------------------------------------------------- |
| **CORS**     | 跨域资源共享 | "前后端不同端口时浏览器阻止请求，CORS 中间件放行指定来源" |
| **COUNT(*)** | SQL 聚合统计 | "统计总数用 COUNT(*)，不需要查全部行，数据库引擎优化过"   |

---

### 5.15 启动与验证

```bash
# 终端 1：FastAPI 后端
cd /Users/xiaoy/inforadar
uvicorn app.main:app --reload --port 8000

# 终端 2：React 前端
cd /Users/xiaoy/inforadar/frontend
npm run dev
```

浏览器打开 `http://localhost:5173`，验证以下功能：

1. Dashboard 页面加载，显示统计栏和空状态
2. 点"添加话题"弹窗添加一个话题
3. 话题卡片出现在网格中
4. 点"扫描"跳转到详情页，SSE 实时显示 4 个 Agent 状态
5. 扫描完成后摘要显示在左侧面板，同时出现在右侧历史摘要列表

---

## 知识点速查表（按面试频率排序）

| 排名 | 知识点                  | 对应模块      | 一句话回答                                                      |
| ---- | ----------------------- | ------------- | --------------------------------------------------------------- |
| 1    | LangGraph 状态图        | graph.py      | "StateGraph 定义节点和边，state 在节点间共享，compile() 后复用" |
| 2    | 多 Agent 协作           | 5 个 Agent    | "4 Agent 流水线 + 1 归档 Agent，各自独立 Prompt 和工具"         |
| 3    | 混合存储架构            | tools.py      | "SQLite 存结构化字段做精确查询，ChromaDB 存正文做语义检索"      |
| 4    | 规则检测 + LLM 总结     | analyst.py    | "确定性高的用代码（零 token），需要理解的用 LLM"                |
| 5    | 质量过滤                | researcher.py | "LLM 批量打分 → 低分丢弃 → URL 去重 → 高分抓全文"            |
| 6    | 冷热分层存储            | archiver.py   | "hot/cold/archive 三态，原文不删只标记，摘要供日常检索"         |
| 7    | 每话题独立频率          | tasks.py      | "用户自定义每个话题多久扫一次，Celery Beat 按各自频率触发"      |
| 8    | SSE 实时推送            | main.py       | "Server-Sent Events 单向推送扫描进度，前端实时更新"             |
| 9    | Celery Beat 调度        | tasks.py      | "定时器 + 消息队列解耦，Beat 生产任务 Worker 消费"              |
| 10   | React + Vite 前后端分离 | frontend/     | "Vite proxy 解决开发跨域，EventSource 对接 SSE 实时推送"        |
| 11   | ChromaDB metadata 过滤  | tools.py      | "按 tier 字段过滤只检索热区+归档区，冷区按需查"                 |
