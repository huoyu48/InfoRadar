"""InfoRadar Writer Agent — 生成情报摘要"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings

settings = get_settings()

writer_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.3,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

WRITER_PROMPT = """你是一个情报简报撰稿人。基于分析结果，撰写情报摘要。
格式：## 本期要点（3-5 条） → ## 新增信息 → ## 趋势观察 → ## 来源
风格：简洁、有信息密度、不废话。"""


def write_digest(topic_name: str, analysis: str, sources: list[str]) -> str:
    sources_text = "\n".join(f"- {url}" for url in sources)
    messages = [
        SystemMessage(content=WRITER_PROMPT),
        HumanMessage(content=f"话题：{topic_name}\n分析结果：\n{analysis}\n来源：\n{sources_text}"),
    ]
    response = writer_llm.invoke(messages)
    return response.content
