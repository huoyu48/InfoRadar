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

ANALYST_PROMPT = """你是一个情报分析师。基于检测结果，针对话题「{topic}」进行分析。
要求：
1. 提取关键事实和数据（价格、数字、时间、人名、公司名等）
2. 识别变化趋势和异动信号
3. 对比不同来源的信息，标注一致性或矛盾点
4. 不写废话，信息密度要高"""


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
