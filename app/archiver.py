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
