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
    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"), answer=AsyncMock(), edit_text=AsyncMock()
    )
    callback = SimpleNamespace(
        message=message,
        from_user=SimpleNamespace(id=5),
        data="home",
        answer=AsyncMock(),
        edit_text=AsyncMock(),
    )
    await user_callback(callback, None, Settings("unused", 1, api_mode="mock"))
    assert "DEMO MODE" in message.edit_text.call_args.args[0]
    callback.answer.assert_awaited_once()


async def test_help_has_menu_and_privacy():
    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"), answer=AsyncMock(), edit_text=AsyncMock()
    )
    callback = SimpleNamespace(
        message=message,
        from_user=SimpleNamespace(id=5),
        data="help",
        answer=AsyncMock(),
        edit_text=AsyncMock(),
    )
    await user_callback(callback, None, Settings("unused", 1, api_mode="mock"))
    assert "screenshots" in message.edit_text.call_args.args[0]
    assert message.edit_text.call_args.kwargs["reply_markup"]


async def test_http_home_has_no_demo_instructions():
    message = SimpleNamespace(chat=SimpleNamespace(type="private"), edit_text=AsyncMock())
    callback = SimpleNamespace(
        message=message, from_user=SimpleNamespace(id=1), data="home", answer=AsyncMock()
    )
    await user_callback(callback, None, Settings("unused", 1))
    text = message.edit_text.call_args.args[0]
    assert "HTTP mode" in text and "demo" not in text.lower()
    menu = message.edit_text.call_args.kwargs["reply_markup"]
    assert any(b.callback_data == "admin:stats" for row in menu.inline_keyboard for b in row)
    assert not any(
        b.callback_data == "admin:stats" for row in user_menu().inline_keyboard for b in row
    )


async def test_repeated_navigation_ignores_only_not_modified():
    import pytest
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import EditMessageText

    from helpers import edit_panel

    method = EditMessageText(text="Home", chat_id=1, message_id=1)
    message = SimpleNamespace(
        edit_text=AsyncMock(
            side_effect=TelegramBadRequest(
                method=method, message="Bad Request: message is not modified"
            )
        )
    )
    await edit_panel(message, "Home", user_menu())
    message.edit_text.side_effect = TelegramBadRequest(method=method, message="Permission denied")
    with pytest.raises(TelegramBadRequest, match="Permission denied"):
        await edit_panel(message, "Home", user_menu())


async def test_admin_navigation_and_account(tmp_path):
    from database import Database
    from handlers.admin import control

    db = Database(str(tmp_path / "panel.db"))
    await db.open()
    settings = Settings("unused", 1, api_url="https://example.invalid", api_key="SECRET")
    message = SimpleNamespace(chat=SimpleNamespace(type="private"), edit_text=AsyncMock())
    callback = SimpleNamespace(
        message=message, from_user=SimpleNamespace(id=1), data="admin:on", answer=AsyncMock()
    )
    try:
        await control(callback, db, settings)
        assert await db.maintenance()
        assert "Paused" in message.edit_text.call_args.args[0]
        callback.data = "admin:off"
        await control(callback, db, settings)
        assert not await db.maintenance()
        callback.data = "admin:api"
        await control(callback, db, settings)
        text = message.edit_text.call_args.args[0]
        assert "Configured" in text and "SECRET" not in text and "example.invalid" not in text
        callback.data = "admin:users:0"
        await control(callback, db, settings)
        assert "No users" in message.edit_text.call_args.args[0]
        assert message.edit_text.call_args.kwargs["reply_markup"]
        callback.from_user.id = 5
        await db.reserve(5, exempt=True)
        await db.set_maintenance(False)
        await db.reserve(5)
        callback.data = "account"
        await user_callback(callback, db, settings)
        assert "0 / 1" in message.edit_text.call_args.args[0]
    finally:
        await db.close()
