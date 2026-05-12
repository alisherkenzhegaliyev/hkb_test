from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Email
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    email_poll_interval: int = 5  # minutes

    # Groq (kept for backward compat, not used if openai_api_key is set)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # OpenAI (takes priority over Groq for LLM matching)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Database
    database_url: str = "postgresql+asyncpg://recruiting:recruiting@postgres:5432/recruiting"

    # hh.kz
    employer_id: str = "49971"
    employer_url: str = "https://almaty.hh.kz/employer/49971"

    # Matching thresholds
    tfidf_threshold: float = 0.05
    semantic_threshold: float = 0.35
    top_k: int = 5

    # Paths
    resumes_dir: str = "data/resumes"
    tfidf_model_path: str = "data/tfidf_model.joblib"


settings = Settings()
