from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # Database settings
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str

    # LangChain settings
    GROQ_API_KEY: str
    LANGSMITH_API_KEY: str
    LANGSMITH_TRACING: str
    WIKIPEDIA_USER_AGENT: str

    model_config = SettingsConfigDict(
        env_file="../.env.dev", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
