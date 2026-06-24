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

SCORE_PROMPT = """请对以下搜索结果与话题的相关度打分（1-5 分），5 分最高。
话题：{topic}

打分标准：
- 5分：直接回答了话题核心问题的具体数据/事实/信息
- 4分：包含与话题高度相关的具体内容
- 3分：与话题相关但信息密度较低，偏概述性
- 2分：仅间接相关或信息过时
- 1分：不相关内容

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
