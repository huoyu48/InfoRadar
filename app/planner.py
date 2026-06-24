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

PLANNER_PROMPT = """你是一个招聘情报搜索专家。给定一个求职追踪话题，你需要生成 3-5 个精准的搜索查询。
规则：
1. 必须包含 site: 定向搜索主流招聘平台（如 site:zhipin.com、site:nowcoder.com、site:lagou.com、site:liepin.com、site:linkedin.com/jobs）
2. 关键词要具体到岗位名称+城市+方向，例如「AI Agent 实习 上海」
3. 混合使用招聘平台定向搜索和通用搜索（如「2026 上海 AI Agent 实习 招聘」）
4. 每条查询都要能直接命中具体岗位列表页，不要搜趋势分析类文章
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