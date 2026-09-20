"""Validated environment configuration; secrets never appear in repr."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    owner_id: int
    sudo_ids: frozenset[int] = frozenset()
    db_path: str = "data/swagger.db"
    api_mode: str = "http"
    api_url: str = ""
    api_key: str = field(default="", repr=False)
    mode: str = "polling"
    webhook_url: str = ""
    webhook_secret: str = field(default="", repr=False)
    port: int = 8080
    force_sub_chat_id: str = ""
    force_sub_url: str = ""

    def is_admin(self, user_id: int) -> bool:
        return user_id == self.owner_id or user_id in self.sudo_ids

    @classmethod
    def load(cls):
        load_dotenv()
        try:
            s = cls(
                token=os.getenv("BOT_TOKEN", ""),
                owner_id=int(os.getenv("OWNER_ID", "0")),
                sudo_ids=frozenset(
                    int(x.strip()) for x in os.getenv("SUDO_IDS", "").split(",") if x.strip()
                ),
                db_path=os.getenv("DB_PATH", "data/swagger.db"),
                api_mode=os.getenv("API_MODE", "http").strip().lower(),
                api_url=os.getenv("API_BASE_URL", "").rstrip("/"),
                api_key=os.getenv("API_KEY", ""),
                mode=os.getenv("BOT_MODE", "polling").strip().lower(),
                webhook_url=os.getenv("WEBHOOK_URL", "").rstrip("/"),
                webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
                port=int(os.getenv("PORT", "8080")),
                force_sub_chat_id=os.getenv("FORCE_SUB_CHAT_ID", "").strip(),
                force_sub_url=os.getenv("FORCE_SUB_URL", "").strip(),
            )
        except ValueError:
            raise ValueError("OWNER_ID, SUDO_IDS and PORT must be integers") from None
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", s.token):
            raise ValueError("Set a valid BOT_TOKEN")
        if s.owner_id <= 0 or any(x <= 0 for x in s.sudo_ids):
            raise ValueError("Set positive Telegram user IDs")
        if s.api_mode not in {"mock", "http", "sandbox"}:
            raise ValueError("API_MODE must be http, sandbox or mock")
        if s.mode not in {"polling", "webhook"}:
            raise ValueError("BOT_MODE must be polling or webhook")
        if not 1 <= s.port <= 65535:
            raise ValueError("Invalid PORT")
        if s.force_sub_chat_id or s.force_sub_url:
            if not re.fullmatch(r"-100[0-9]+|@[A-Za-z][A-Za-z0-9_]{4,}", s.force_sub_chat_id):
                raise ValueError("FORCE_SUB_CHAT_ID requires exact -100... ID or @channelusername")
            if not re.fullmatch(r"https://t\.me/[A-Za-z0-9_+/-]+", s.force_sub_url):
                raise ValueError("FORCE_SUB_URL requires an HTTPS Telegram invite/channel link")
        if s.api_mode == "http":
            u = urlparse(s.api_url)
            if u.scheme != "https" or not u.netloc or u.username or u.query or u.fragment:
                raise ValueError("API_BASE_URL must be a trusted HTTPS base URL")
        if s.mode == "webhook":
            if not s.webhook_url.startswith("https://"):
                raise ValueError("WEBHOOK_URL requires HTTPS")
            if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", s.webhook_secret):
                raise ValueError("WEBHOOK_SECRET needs 32-256 URL-safe characters")
        return s
