"""FastAPI 入口 — API 路由 + SSE 推送 + 静态文件"""
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.tools import init_db, get_db
from app.models import Topic
from app.graph import run_scan

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ── FastAPI 应用 ──
app = FastAPI(title="InfoRadar", version="1.0.0")

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("InfoRadar 启动完成，访问 http://localhost:8000")


# ── 话题管理 API ──

class TopicCreate(BaseModel):
    name: str
    scan_interval_hours: int = 24


@app.post("/api/topics")
def create_topic(req: TopicCreate):
    from datetime import datetime
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO topics (name, scan_interval_hours, created_at) VALUES (?, ?, ?)",
            (req.name, req.scan_interval_hours, datetime.now().isoformat()),
        )
        conn.commit()
        topic_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        raise HTTPException(400, f"创建失败（话题名重复？）: {e}")
    conn.close()
    return {"id": topic_id, "name": req.name, "scan_interval_hours": req.scan_interval_hours}


@app.get("/api/topics")
def list_topics():
    conn = get_db()
    rows = conn.execute("SELECT * FROM topics ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int):
    conn = get_db()
    conn.execute("DELETE FROM digests WHERE topic_id = ?", (topic_id,))
    conn.execute("DELETE FROM findings WHERE topic_id = ?", (topic_id,))
    conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── 扫描 API ──

@app.post("/api/scans/{topic_id}")
def trigger_scan(topic_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "话题不存在")

    topic = Topic(
        id=row["id"],
        name=row["name"],
        scan_interval_hours=row["scan_interval_hours"],
    )
    try:
        result = run_scan(topic)
        return {
            "topic": topic.name,
            "new_entries": result["new_entries_count"],
            "digest": result["digest"],
            "sources": result["sources"],
        }
    except Exception as e:
        raise HTTPException(500, f"扫描失败: {e}")


@app.get("/api/scans/{topic_id}/stream")
async def stream_scan(topic_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "话题不存在")

    topic = Topic(
        id=row["id"],
        name=row["name"],
        scan_interval_hours=row["scan_interval_hours"],
    )

    async def event_generator():
        stages = {
            "planner": "规划搜索策略",
            "researcher": "搜索和收集信息",
            "analyst": "分析变化趋势",
            "writer": "生成情报摘要",
        }
        for stage, name in stages.items():
            yield {
                "event": "progress",
                "data": json.dumps({"stage": stage, "message": f"正在{name}..."}, ensure_ascii=False),
            }
        try:
            result = run_scan(topic)
            yield {
                "event": "complete",
                "data": json.dumps({
                    "new_entries": result["new_entries_count"],
                    "digest": result["digest"],
                    "sources": result["sources"],
                }, ensure_ascii=False),
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


# ── 摘要查询 API ──

@app.get("/api/digests/{topic_id}")
def get_digests(topic_id: int, limit: int = 10):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, content, created_at FROM digests WHERE topic_id = ? ORDER BY created_at DESC LIMIT ?",
        (topic_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── 首页 ──

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
