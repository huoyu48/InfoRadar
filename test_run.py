"""命令行快速测试 — 不启动 Web 也能跑通完整流水线"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from app.tools import init_db, get_db
from app.models import Topic
from app.graph import run_scan

init_db()

# 创建测试话题
conn = get_db()
conn.execute(
    "INSERT OR IGNORE INTO topics (name, scan_interval_hours) VALUES (?, ?)",
    ("上海Agent开发实习", 24),
)
conn.commit()
row = conn.execute(
    "SELECT * FROM topics WHERE name = ?", ("上海Agent开发实习",)
).fetchone()
conn.close()

topic = Topic(id=row["id"], name=row["name"], scan_interval_hours=row["scan_interval_hours"])

print(f"\n{'═'*50}")
print(f"开始扫描话题: {topic.name}")
print(f"{'═'*50}\n")

result = run_scan(topic)

print(f"\n{'═'*50}")
print(f"新增: {result['new_entries_count']} 条")
print(f"{'═'*50}")
print(result["digest"])
