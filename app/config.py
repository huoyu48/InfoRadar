"""InfoRadar 配置管理 — 自动从 .env 读取"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek LLM 配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Tavily 搜索 API
    tavily_api_key: str = ""

    # 知识库配置
    chroma_dir: str = "data/chroma"
    sqlite_path: str = "data/inforadar.db"

    # 归档配置
    archive_after_days: int = 30
    min_relevance_score: int = 3

    model_config = {"env_file": ".env"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
