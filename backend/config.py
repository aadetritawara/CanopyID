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
    LANGSMITH_TRACING: bool

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"     
    )

settings = Settings()