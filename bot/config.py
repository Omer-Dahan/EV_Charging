from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, Any


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_id: int = Field(..., alias="TELEGRAM_API_ID")
    api_hash: str = Field(..., alias="TELEGRAM_API_HASH")
    bot_token: str = Field(..., alias="BOT_TOKEN")
    # No default paths: both DB locations must be set explicitly in .env (or via env vars).
    # This prevents silent misconfiguration when running outside the expected Linux deployment path.
    db_path: str = Field(..., alias="DB_PATH")
    users_db_path: str = Field(..., alias="USERS_DB_PATH")
    admin_id: Optional[int] = Field(default=None, alias="ADMIN_ID")
    admin_chat_id: Optional[int] = Field(default=None, alias="ADMIN_CHAT_ID")
    debug: bool = Field(default=False, alias="DEBUG")
    map_provider_key: str = Field(default="", alias="MAP_PROVIDER_KEY")

    @field_validator("admin_id", "admin_chat_id", mode="before")
    @classmethod
    def _parse_optional_int(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            try:
                return int(v)
            except ValueError:
                return None
        if isinstance(v, int):
            return v
        return None


settings = Settings()


def is_admin(user_id: Optional[int]) -> bool:
    """בודק האם ה-ID הנתון שייך למנהל המוגדר ב-ADMIN_ID או ADMIN_CHAT_ID."""
    if user_id is None:
        return False
    admin_ids = set()
    if settings.admin_id is not None:
        admin_ids.add(settings.admin_id)
    if settings.admin_chat_id is not None:
        admin_ids.add(settings.admin_chat_id)
    return user_id in admin_ids


# TODO: להחליף בכתובת ה-GitHub Pages הסופית לאחר פרסום הריפו (Settings > Pages > main /webapp).
# עד אז זהו placeholder בלבד וכפתור המפה לא יעבוד בפועל.
WEBAPP_URL = "https://omer-dahan.github.io/EV_Charging/webapp/index.html"
