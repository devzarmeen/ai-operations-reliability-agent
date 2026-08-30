from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql://reliability_user:reliability_password"
        "@localhost:5432/reliability_agent"
    )
    groq_api_key: str = ""
    prometheus_url: str = "http://prometheus:9090"
    simulated_api_url: str = "http://simulated-api:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
