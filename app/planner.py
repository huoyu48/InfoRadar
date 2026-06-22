from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import get_settings

settings = get_settings()

planner_llm = ChatOpenAI(
    model=settings.deepseek_model,
    temperature=0.3,
    openai_api_key=settings.deepseek_api_key,    # type: ignore
    openai_api_base=settings.deepseek_base_url,  # type: ignore
)

PLANNER_PROMPT = """你是一个情报分析经理。给定一个追踪话题，你需要生成 3-5 个精准的搜索查询。
规则：混合使用通用搜索、定向站点搜索、技术关键词搜索。
请只输出查询列表，每行一个，不要编号。"""

def plan_searches(topic_name: str) -> list[str]:
    messages = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=f"话题：{topic_name}"),
    ]
    response = planner_llm.invoke(messages)
    queries = []
    for line in response.content.strip().split("\n"):
        q = line.strip()
        if q and q[0].isdigit():        # 去掉 "1. " 前缀
            q = q.split(".", 1)[-1].strip()
        if q:
            queries.append(q)
    return queries[:5]