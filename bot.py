import os
from dataclasses import dataclass
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

@dataclass
class Config:
    bot_token: str
    main_admin_id: int
    tz: ZoneInfo

def get_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    admin = os.getenv("MAIN_ADMIN_ID", "").strip()
    tz_name = os.getenv("TZ", "Europe/Kyiv").strip() or "Europe/Kyiv"

    if not token:
        raise RuntimeError("BOT_TOKEN is empty in .env")
    if not admin:
        raise RuntimeError("MAIN_ADMIN_ID is empty in .env")

    return Config(bot_token=token, main_admin_id=int(admin), tz=ZoneInfo(tz_name))
