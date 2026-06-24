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

WRITER_PROMPT = """你是一个求职情报整理专家。基于分析结果，整理出具体的岗位信息列表。
输出格式：
## 具体岗位列表

对每个岗位，用以下格式输出：
### 1. 公司名 - 岗位名
- **薪资**：xxx（如有）
- **地点**：xxx
- **任职要求**：列出核心要求（3-5 条）
- **岗位亮点**：1-2 句话总结
- **来源**：来源链接

如果某项信息搜索结果中未提及，标注「未公开」。

## 求职建议
基于本次扫描结果，给出 2-3 条简短的求职建议。

## 来源汇总
列出所有来源链接。

风格：实用、具体、不废话。重点突出能直接投的岗位。"""


def write_digest(topic_name: str, analysis: str, sources: list[str]) -> str:
    sources_text = "\n".join(f"- {url}" for url in sources)
    messages = [
        SystemMessage(content=WRITER_PROMPT),
        HumanMessage(content=f"话题：{topic_name}\n分析结果：\n{analysis}\n来源：\n{sources_text}"),
    ]
    response = writer_llm.invoke(messages)
    return response.content
