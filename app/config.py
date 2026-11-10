from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_SECRET_KEY: str = ""
    SUPABASE_BUCKET: str = "documents"
    GEMINI_API_KEY: str = ""
    GEMINI_CHAT_MODEL: str = ""
    GEMINI_EMBED_MODEL: str = ""
    EMBED_DIM: int = 768
    JWT_SECRET: str = Field(min_length=32)  # required; fail closed if missing or weak
    JWT_EXPIRE_MINUTES: int = 720
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    PUBLIC_APP_URL: str = "http://localhost:5173"
    GATE_MIN_SIMILARITY: float = 0.60
    GATE_KEYWORD_MIN_SIMILARITY: float = 0.55

    @property
    def frontend_origins(self) -> list[str]:
        """FRONTEND_ORIGIN may be a comma-separated list, e.g. "https://app.vercel.app,http://localhost:5173"."""
        return [o.strip().rstrip("/") for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
