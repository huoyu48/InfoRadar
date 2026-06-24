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