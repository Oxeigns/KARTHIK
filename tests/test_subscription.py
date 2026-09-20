from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import CommandObject
from aiogram.methods import GetChatMember

from config import Settings
from database import Database
from middlewares.subscription import membership
from middlewares.throttling import SearchGuard


def settings():
    return Settings(
        "unused", 1, force_sub_chat_id="-1001234567890", force_sub_url="https://t.me/+example"
    )


@pytest.mark.parametrize(
    "status,is_member,expected",
    [
        ("member", True, "ok"),
        ("administrator", True, "ok"),
        ("creator", True, "ok"),
        ("restricted", True, "ok"),
        ("restricted", False, "join"),
        ("left", False, "join"),
        ("kicked", False, "join"),
    ],
)
async def test_membership_states(status, is_member, expected):
    bot = SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status=status, is_member=is_member))
    )
    assert await membership(bot, settings(), 7) == expected
    bot.get_chat_member.assert_awaited_once_with(chat_id=-1001234567890, user_id=7)


async def test_admin_bypass():
    bot = SimpleNamespace(get_chat_member=AsyncMock())
    assert await membership(bot, settings(), 1) == "ok"
    bot.get_chat_member.assert_not_awaited()


async def test_error_fails_closed():
    failure = TelegramBadRequest(
        method=GetChatMember(chat_id=-1001234567890, user_id=7), message="Bot is not a member"
    )
    bot = SimpleNamespace(get_chat_member=AsyncMock(side_effect=failure))
    assert await membership(bot, settings(), 7) == "unavailable"


async def test_no_quota_spent_and_leaving_blocks_next_search(tmp_path):
    db = Database(str(tmp_path / "gate.db"))
    await db.open()
    bot = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="left")))
    event = SimpleNamespace(
        bot=bot,
        chat=SimpleNamespace(id=7, type="private"),
        message_id=8,
        from_user=SimpleNamespace(id=7),
        answer=AsyncMock(),
    )
    data = {"settings": settings(), "db": db, "command": CommandObject(command="info", args="demo")}
    handler = AsyncMock()
    try:
        await SearchGuard()(handler, event, data)
        handler.assert_not_awaited()
        assert await db.one("SELECT * FROM quotas WHERE user_id=7") is None
        bot.get_chat_member.return_value = SimpleNamespace(status="member")
        await SearchGuard()(handler, event, data)
        assert handler.await_count == 1
        await db.reset(7)
        bot.get_chat_member.return_value = SimpleNamespace(status="left")
        await SearchGuard()(handler, event, data)
        assert handler.await_count == 1
        assert await db.one("SELECT * FROM quotas WHERE user_id=7") is None
    finally:
        await db.close()


def test_incomplete_config_rejected(monkeypatch):
    monkeypatch.setenv("API_MODE", "mock")
    monkeypatch.setenv("BOT_TOKEN", "123456:" + "A" * 35)
    monkeypatch.setenv("OWNER_ID", "1")
    monkeypatch.setenv("FORCE_SUB_URL", "https://t.me/+example")
    monkeypatch.setenv("FORCE_SUB_CHAT_ID", "")
    with pytest.raises(ValueError, match="FORCE_SUB_CHAT_ID"):
        Settings.load()
    monkeypatch.setenv("FORCE_SUB_CHAT_ID", "-1001234567890")
    assert Settings.load().force_sub_chat_id == "-1001234567890"
