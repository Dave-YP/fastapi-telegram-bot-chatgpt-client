from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    TELEGRAM_TOKEN: str
    API_URL: str
    DAILY_MESSAGE_LIMIT: int
    DATABASE_URL: str
    SECRET_KEY: str
    REDIS_URL: str
    TELEGRAM_BOT_URL: str
    MAX_CONTEXT_MESSAGES: int

    class Config:
        env_file = "../.env"


settings = Settings()
