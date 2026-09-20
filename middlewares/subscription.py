"""Fail-closed live channel membership check; no membership caching."""

import asyncio

from aiogram.exceptions import TelegramAPIError

from keyboards import force_sub_menu


async def membership(bot, settings, uid):
    if settings.is_admin(uid):
        return "ok"
    if not settings.force_sub_chat_id and not settings.force_sub_url:
        return "ok"
    if not settings.force_sub_chat_id or not settings.force_sub_url:
        return "unavailable"
    chat = settings.force_sub_chat_id
    chat = int(chat) if chat.startswith("-") else chat
    try:
        async with asyncio.timeout(8):
            member = await bot.get_chat_member(chat_id=chat, user_id=uid)
    except (TelegramAPIError, TimeoutError):
        return "unavailable"
    if member.status in {"creator", "administrator", "member"}:
        return "ok"
    if member.status == "restricted" and member.is_member:
        return "ok"
    return "join"


async def require_membership(message, settings, uid):
    state = await membership(message.bot, settings, uid)
    if state == "ok":
        return True
    text = (
        "📢 Join our channel, then tap Check before searching."
        if state == "join"
        else "⚠️ Membership verification is unavailable. Contact the owner or retry later."
    )
    markup = force_sub_menu(settings.force_sub_url) if settings.force_sub_url else None
    await message.answer(text, reply_markup=markup)
    return False
