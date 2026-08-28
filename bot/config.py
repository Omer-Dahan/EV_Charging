from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    api_id: int = Field(..., alias="TELEGRAM_API_ID")
    api_hash: str = Field(..., alias="TELEGRAM_API_HASH")
    bot_token: str = Field(..., alias="BOT_TOKEN")
    # No default paths: both DB locations must be set explicitly in .env (or via env vars).
    # This prevents silent misconfiguration when running outside the expected Linux deployment path.
    db_path: str = Field(..., alias="DB_PATH")
    users_db_path: str = Field(..., alias="USERS_DB_PATH")
    admin_chat_id: Optional[int] = Field(default=None, alias="ADMIN_CHAT_ID")
    debug: bool = Field(default=False, alias="DEBUG")
    map_provider_key: str = Field(default="", alias="MAP_PROVIDER_KEY")


settings = Settings()

# TODO: להחליף בכתובת ה-GitHub Pages הסופית לאחר פרסום הריפו (Settings > Pages > main /webapp).
# עד אז זהו placeholder בלבד וכפתור המפה לא יעבוד בפועל.
WEBAPP_URL = "https://<GITHUB_USERNAME>.github.io/ev-charging-bot/webapp/index.html"
