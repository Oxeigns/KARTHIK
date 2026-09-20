"""Enforce authorization on every administrative event."""

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery


class AdminGuard(BaseMiddleware):
    async def __call__(self, handler, event, data):
        settings = data["settings"]
        if not event.from_user or not settings.is_admin(event.from_user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Owner / sudo access required.", show_alert=True)
            else:
                await event.answer("Owner / sudo access required.")
            return
        chat = (
            event.message.chat
            if isinstance(event, CallbackQuery) and event.message
            else (getattr(event, "chat", None))
        )
        if not chat or chat.type != "private":
            await event.answer("Use the private admin chat.")
            return
        return await handler(event, data)
