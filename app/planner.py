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

PLANNER_PROMPT = """你是一个情报搜索专家。给定一个追踪话题，你需要分析话题性质，然后生成 3-5 个精准的搜索查询。

搜索策略（根据话题自动选择）：
- 价格/商品类话题：搜索电商平台、价格追踪网站、行业报告（如「蛋白粉价格 2026」「乳清蛋白原料行情」）
- 技术/开源类话题：搜索 GitHub、技术博客、官方文档（如 site:github.com、技术社区）
- 招聘/求职类话题：搜索招聘平台 site:zhipin.com、site:lagou.com、site:nowcoder.com
- 新闻/行业类话题：搜索新闻网站、行业媒体、社交媒体讨论

通用规则：
1. 混合使用通用搜索和 site: 定向搜索
2. 关键词要具体，包含时间限定（如「2026」「最新」）
3. 中英文查询都要覆盖，获取更全面的信息
4. 优先搜索能直接回答用户问题的页面，而非泛泛的综述文章

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