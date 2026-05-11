from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jellyfin_url: str = "http://localhost:8096"
    jellyfin_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/finsight.db"
    poll_interval: int = 30
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
