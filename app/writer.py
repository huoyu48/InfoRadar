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

输出格式（根据话题类型自动选择最合适的格式）：

## 核心发现
用 3-5 条要点总结最重要的发现，每条包含具体数据/事实。

## 详细信息
展开说明每个核心发现的背景和细节。如果是价格类话题，列出具体价格数据；如果是技术话题，列出具体项目/工具；如果是招聘话题，列出具体岗位。

## 趋势与判断
基于本次扫描结果，给出趋势判断和简短分析。

## 来源
列出所有来源链接。

风格：简洁、有信息密度、不废话。不要编造信息，搜索结果里没有的就写「未获取到」。"""


def write_digest(topic_name: str, analysis: str, sources: list[str]) -> str:
    sources_text = "\n".join(f"- {url}" for url in sources)
    messages = [
        SystemMessage(content=WRITER_PROMPT),
        HumanMessage(content=f"话题：{topic_name}\n分析结果：\n{analysis}\n来源：\n{sources_text}"),
    ]
    response = writer_llm.invoke(messages)
    return response.content
