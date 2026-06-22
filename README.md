# InfoRadar - 个人情报雷达

> 基于多 Agent 协作的自动化情报追踪系统，定时扫描互联网，为你关注的领域生成情报简报。

## 项目简介

InfoRadar 是一个个人情报追踪 Agent 系统。你配置感兴趣的话题（如"上海 AI Agent 实习"、"Rust 编程语言动态"），系统自动定时扫描互联网，搜集、过滤、分析新信息，生成结构化的情报摘要。

**和 ChatGPT 的区别**：ChatGPT 是问一次答一次，InfoRadar 是持续追踪——今天搜到 3 条，明天搜到 5 条，后天发现趋势变化。**时间维度的知识积累**是核心价值。

## 系统架构

```
Celery Beat 定时触发
    │
    ▼
┌─ 扫描流水线 (LangGraph StateGraph) ─────────────────┐
│                                                       │
│  Planner → Researcher → Analyst → Writer              │
│  (生成搜索)   (搜索+过滤)   (规则+LLM分析)  (生成摘要) │
│                                                       │
└───────────────────────────────────────────────────────┘
    │
    ▼
┌─ 混合存储 ──────────────────────────────────────────┐
│  SQLite (结构化数据) + ChromaDB (语义检索)            │
│  热区(hot) / 冷区(cold) / 归档(archive) 三层分级      │
└───────────────────────────────────────────────────────┘
    │
    ▼
  FastAPI + Web UI (话题管理 / 手动扫描 / 摘要查看)
```

### 5 个 Agent 分工

| Agent | 职责 | 关键技术 |
|-------|------|----------|
| **Planner** | 根据话题生成 3-5 个搜索查询 | LLM + Prompt Engineering |
| **Researcher** | 搜索互联网，LLM 批量打分过滤，存入知识库 | Tavily API + 质量评分 |
| **Analyst** | 规则引擎做变化检测（零 token），LLM 做趋势总结 | 规则检测 + LLM 两阶段 |
| **Writer** | 基于分析结果生成 Markdown 情报摘要 | LLM + 结构化 Prompt |
| **Archiver** | 定期归档旧数据，LLM 压缩摘要，冷热分层 | ChromaDB metadata 过滤 |

## 技术栈

| 技术 | 用途 |
|------|------|
| **LangGraph** | 多 Agent 状态图编排 |
| **LangChain + DeepSeek** | LLM 调用（兼容 OpenAI 接口） |
| **FastAPI** | Web API 服务 |
| **Celery + Redis** | 定时任务调度（Beat + Worker） |
| **ChromaDB** | 向量数据库（语义检索） |
| **SQLite** | 结构化数据存储 |
| **SSE** | 实时扫描进度推送 |
| **Tavily API** | 互联网搜索 |

## 核心亮点

- **混合存储架构**：SQLite 存结构化字段做精确查询，ChromaDB 存正文做语义检索，各取所长
- **规则引擎 + LLM 两阶段分析**：URL 去重、频率统计、版本号提取用纯代码（零 token），趋势归纳用 LLM
- **质量过滤机制**：LLM 批量打分 1-5 分，低于 3 分丢弃，4-5 分抓全文，3 分只存摘要
- **冷热分层存储**：热区日常检索 → 冷区保留原文低频查 → 归档区存 LLM 摘要，原文永不删除
- **每话题独立频率**：每个话题可配置不同的扫描间隔（6h / 12h / 24h / 72h）
- **SSE 实时推送**：扫描过程中前端实时看到每个 Agent 的执行状态

## 快速开始

### 环境要求

- Python 3.11+
- Redis（用于 Celery 任务队列）

### 安装

```bash
# 克隆项目
git clone https://github.com/huoyu48/InfoRadar.git
cd InfoRadar

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（填入你的 API Key）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 TAVILY_API_KEY
```

### 启动

```bash
# 终端 1：启动 Redis
redis-server

# 终端 2：启动 Celery Worker
celery -A app.tasks worker --loglevel=info

# 终端 3：启动 Celery Beat（定时调度）
celery -A app.tasks beat --loglevel=info

# 终端 4：启动 FastAPI 服务
uvicorn app.main:app --reload --port 8000
```

打开浏览器访问 `http://localhost:8000`，在 Web UI 中添加话题即可开始追踪。

### 命令行快速测试

```bash
# 不需要启动 Web 和 Celery，直接测试完整流水线
python test_run.py
```

## 项目结构

```
InfoRadar/
├── app/
│   ├── config.py          # 配置管理（pydantic-settings）
│   ├── models.py          # 数据模型（Topic, Finding, RadarState）
│   ├── tools.py           # 工具函数（搜索、存储、规则引擎）
│   ├── planner.py         # Planner Agent
│   ├── researcher.py      # Researcher Agent
│   ├── analyst.py         # Analyst Agent
│   ├── writer.py          # Writer Agent
│   ├── archiver.py        # Archiver Agent
│   ├── graph.py           # LangGraph 状态图编排
│   ├── tasks.py           # Celery 任务 + Beat 调度
│   ├── main.py            # FastAPI 入口
│   └── static/
│       └── index.html     # Web UI（暗色主题）
├── data/                  # 运行时数据（SQLite + ChromaDB）
├── .env                   # 环境变量（API Key）
├── .gitignore
├── requirements.txt
└── test_run.py            # 命令行测试脚本
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/topics` | 添加追踪话题 |
| `GET` | `/api/topics` | 获取话题列表 |
| `DELETE` | `/api/topics/{id}` | 删除话题 |
| `POST` | `/api/scans/{topic_id}` | 手动触发扫描 |
| `GET` | `/api/scans/{topic_id}/stream` | SSE 实时扫描进度 |
| `GET` | `/api/digests/{topic_id}` | 获取历史摘要 |

## 面试知识点

本项目涵盖以下 Agent 开发核心技能：

1. **LangGraph 状态图编排** — StateGraph + 条件边 + compile() 复用
2. **多 Agent 协作** — 5 个 Agent 各司其职，线性流水线
3. **Tool Calling** — Tavily 搜索、网页抓取、知识库读写
4. **RAG 检索增强** — ChromaDB 向量存储 + metadata 过滤
5. **Prompt Engineering** — System Prompt 角色设定、输出格式约束
6. **异步任务调度** — Celery Beat + Redis + Worker
7. **FastAPI 后端** — RESTful API + SSE 流式推送
8. **混合存储架构** — SQLite 精确查询 + ChromaDB 语义检索

## License

MIT
