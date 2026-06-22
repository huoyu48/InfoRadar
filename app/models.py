"""InfoRadar 数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict


# ── SQLite 结构化数据模型 ──

@dataclass
class Topic:
    """用户配置的话题"""
    id: int = 0
    name: str = ""
    scan_interval_hours: int = 24
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