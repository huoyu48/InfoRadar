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

ANALYST_PROMPT = """你是一个求职市场分析师。基于检测结果，分析以下内容：
话题：{topic}
要求：
1. 提取所有具体的岗位信息（公司名、岗位、薪资、地点、要求）
2. 总结岗位数量变化趋势
3. 识别高频出现的技能要求
4. 不要写废话，重点放在可直接投递的岗位上"""


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
