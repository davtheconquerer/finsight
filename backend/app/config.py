from pydantic_settings import BaseSettings


APP_VERSION = "v1.2.0"


class Settings(BaseSettings):
    jellyfin_url: str = "http://localhost:8096"
    jellyfin_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/finsight.db"
    poll_interval: int = 30
    cold_media_months: int = 6
    demo_mode: bool = False
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
