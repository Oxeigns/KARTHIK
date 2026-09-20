"""Owner/sudo controls; opt-in announcements, confirmation, paced delivery."""

import asyncio
import secrets
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command

from keyboards import admin_menu, keyboard, user_pages
from middlewares.auth import AdminGuard

router = Router(name="admin")
router.message.middleware(AdminGuard())
router.callback_query.middleware(AdminGuard())


@router.message(Command("admin", "stats"))
async def panel(message, db):
    users, searches = await db.stats()
    await message.answer(
        f"<b>Admin panel</b>\nUsers: {users}\nSearch attempts (30d): {searches}",
        reply_markup=admin_menu(),
    )


@router.message(Command("ban", "unban", "reset"))
async def change_user(message, command, db, settings):
    try:
        uid = int(command.args or "")
        if uid <= 0:
            raise ValueError
    except ValueError:
        await message.answer(f"Usage: /{command.command} &lt;positive user_id&gt;")
        return
    if settings.is_admin(uid) and command.command == "ban":
        await message.answer("Cannot ban owner/sudo users.")
        return
    if command.command == "reset":
        await db.reset(uid)
    else:
        await db.ban(uid, command.command == "ban")
    await message.answer("Done.")


@router.callback_query(F.data.startswith("admin:"))
async def control(callback, db):
    await callback.answer()
    action = callback.data.split(":")[1]
    if action in {"on", "off"}:
        await db.set_maintenance(action == "on")
        await callback.message.answer(f"Maintenance: {action}")
    elif action == "stats":
        users, searches = await db.stats()
        await callback.message.answer(f"Users: {users}\nSearch attempts (30d): {searches}")
    elif action == "users":
        try:
            page = int(callback.data.split(":")[2])
            if not 0 <= page <= 100000:
                raise ValueError
        except (ValueError, IndexError):
            return
        rows = await db.all(
            "SELECT id,banned FROM users ORDER BY id LIMIT 11 OFFSET ?", (page * 10,)
        )
        text = "\n".join(
            f"<code>{r['id']}</code> — {'banned' if r['banned'] else 'active'}" for r in rows[:10]
        )
        await callback.message.answer(
            text or "No users.", reply_markup=user_pages(page, len(rows) > 10)
        )


@router.message(Command("broadcast"))
async def prepare_broadcast(message, command, pending):
    text = (command.args or "").strip()
    if not 1 <= len(text) <= 3000:
        await message.answer("Usage: /broadcast &lt;plain text, max 3000 chars&gt;")
        return
    nonce = secrets.token_hex(8)
    pending[message.from_user.id] = (nonce, text, time.monotonic() + 120)
    await message.answer(
        text,
        parse_mode=None,
        reply_markup=keyboard([[("Confirm send to subscribers", "broadcast:" + nonce)]]),
    )


@router.callback_query(F.data.startswith("broadcast:"))
async def send_broadcast(callback, db, pending, broadcast_lock):
    item = pending.get(callback.from_user.id)
    if not item or item[0] != callback.data.split(":")[1] or item[2] < time.monotonic():
        await callback.answer("Confirmation expired.", show_alert=True)
        return
    if broadcast_lock.locked():
        await callback.answer("A broadcast is already running.", show_alert=True)
        return
    async with broadcast_lock:
        pending.pop(callback.from_user.id, None)
        await callback.answer("Broadcast started.")
        sent = failed = last_id = 0
        while True:
            rows = await db.all(
                "SELECT id FROM users WHERE subscribed=1 AND banned=0 AND id>? "
                "ORDER BY id LIMIT 100",
                (last_id,),
            )
            if not rows:
                break
            for row in rows:
                uid = last_id = row["id"]
                # Recheck consent and ban state immediately before sending.
                current = await db.one("SELECT subscribed,banned FROM users WHERE id=?", (uid,))
                if not current[0] or current[1]:
                    continue
                try:
                    try:
                        await callback.bot.send_message(uid, item[1], parse_mode=None)
                    except TelegramRetryAfter as exc:
                        await asyncio.sleep(exc.retry_after)
                        await callback.bot.send_message(uid, item[1], parse_mode=None)
                    sent += 1
                except TelegramForbiddenError:
                    await db.subscribe(uid, False)
                    failed += 1
                except TelegramAPIError:
                    failed += 1
                await asyncio.sleep(0.1)
        await callback.message.answer(f"Broadcast finished. Sent: {sent}; failed: {failed}.")
