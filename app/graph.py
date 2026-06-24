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
