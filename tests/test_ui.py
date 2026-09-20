from types import SimpleNamespace
from unittest.mock import AsyncMock

from config import Settings
from handlers.user import user_callback
from keyboards import OWNER_URL, SUPPORT_URL, owner_link, user_menu


def test_links_and_styles():
    buttons = [b for row in user_menu().inline_keyboard for b in row]
    assert OWNER_URL == "https://t.me/Notethicals"
    assert SUPPORT_URL == "https://t.me/+hQh4Azoq9BoxMjk1"
    assert {b.url for b in buttons if b.url} == {OWNER_URL, SUPPORT_URL}
    assert {"primary", "success", "danger"} <= {b.style for b in buttons}
    assert owner_link(123).inline_keyboard[0][0].url == OWNER_URL


async def test_home_is_explicitly_demo():
    message = SimpleNamespace(chat=SimpleNamespace(type="private"), answer=AsyncMock())
    callback = SimpleNamespace(message=message, data="home", answer=AsyncMock())
    await user_callback(callback, None, Settings("unused", 1))
    assert "DEMO MODE" in message.answer.call_args.args[0]
    callback.answer.assert_awaited_once()


async def test_help_has_menu_and_privacy():
    message = SimpleNamespace(chat=SimpleNamespace(type="private"), answer=AsyncMock())
    callback = SimpleNamespace(message=message, data="help", answer=AsyncMock())
    await user_callback(callback, None, Settings("unused", 1))
    assert "screenshots" in message.answer.call_args.args[0]
    assert message.answer.call_args.kwargs["reply_markup"]
