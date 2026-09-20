"""Reserve daily quota only after command parsing and query validation."""

import re
import time

from aiogram import BaseMiddleware

from helpers import remaining
from keyboards import owner_link
from middlewares.subscription import require_membership


class SearchGuard(BaseMiddleware):
    async def __call__(self, handler, event, data):
        db, settings = data["db"], data["settings"]
        command = data["command"]
        query = (command.args or "").strip()
        # Even denied/invalid query messages receive best-effort cleanup.
        await db.schedule_delete(event.chat.id, event.message_id, time.time() + 60)
        if event.chat.type != "private":
            await event.answer("Please search in a private chat with this bot.")
            return
        if not event.from_user:
            return
        valid = 1 <= len(query) <= 120 and all(c.isprintable() for c in query)
        if command.command == "num":
            valid = valid and bool(re.fullmatch(r"\+?[0-9]{7,15}", query))
        if not valid:
            await event.answer("Usage: /num +15551234567 or /info demo")
            return
        if settings.force_sub_chat_id or settings.force_sub_url:
            if not await require_membership(event, settings, event.from_user.id):
                return
        status = await db.reserve(event.from_user.id, settings.is_admin(event.from_user.id))
        if status != "ok":
            messages = {
                "banned": "Access disabled. Contact the owner.",
                "maintenance": "🛠 Maintenance in progress. Please return later.",
                "quota": "⏳ <b>Daily Quota Exhausted!</b>\n"
                f"Next search available in <code>{remaining()}</code> (UTC reset).",
            }
            await event.answer(messages[status], reply_markup=owner_link(settings.owner_id))
            return
        data["query"] = query
        return await handler(event, data)
