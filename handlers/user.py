"""Private, ephemeral search results and subscription controls."""

import time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart

from api import APIError
from helpers import card
from keyboards import user_menu
from middlewares.subscription import membership, require_membership
from middlewares.throttling import SearchGuard

router = Router(name="user")
search_router = Router(name="search")
search_router.message.middleware(SearchGuard())
router.include_router(search_router)

HELP = (
    "📘 <b>SWAGGER • HELP CENTRE</b>\n\n"
    "/num &lt;number&gt; — demo / authorized metadata lookup\n"
    "/info &lt;term&gt; — demo / authorized record lookup\n"
    "One valid search attempt per UTC calendar day, shared by both commands. "
    "Failures also consume the attempt; owner/sudo are exempt.\n"
    "Results and query commands are scheduled for deletion after 60 seconds. "
    "Deletion cannot remove screenshots, notifications or provider logs.\n"
    "/subscribe and /unsubscribe control announcements.\n"
    "Use only records you have permission to access."
)


WELCOME = (
    "⚡ <b>SWAGGER</b>\n"
    "<i>Your Telegram workspace</i>\n\n"
    "🧪 Demo-first • 🛡 Private chat • ⏱ Daily quota\n\n"
    "<b>Get started</b>\n"
    "Try <code>/info demo</code> for a fictional sample.\n"
    "Open Help for commands and privacy limits.\n\n"
    "👇 Choose an option below"
)


@router.message(CommandStart())
async def start(message, db, settings):
    if message.chat.type != "private":
        await message.answer("Open a private chat to use SWAGGER.")
        return
    await db.register(message.from_user.id)
    if not await require_membership(message, settings, message.from_user.id):
        return
    mode = "🧪 DEMO MODE — fictional responses only.\n" if settings.api_mode == "mock" else ""
    await message.answer(mode + WELCOME, reply_markup=user_menu())


@router.callback_query(F.data == "force:check")
async def force_check(callback, settings):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("Use the bot's private chat.", show_alert=True)
        return
    # Acknowledge promptly; getChatMember may need several seconds.
    await callback.answer("Checking membership…")
    state = await membership(callback.bot, settings, callback.from_user.id)
    if state == "ok":
        await callback.message.answer(
            "✅ Membership verified. Send /info demo or /num followed by a number.",
            reply_markup=user_menu(),
        )
    elif state == "join":
        await callback.message.answer("Please join first. Pending join requests need approval.")
    else:
        await callback.message.answer("Membership check unavailable. Please contact the owner.")


@router.message(Command("help"))
async def help_command(message):
    await message.answer(HELP, reply_markup=user_menu())


@router.message(Command("subscribe", "unsubscribe"))
async def subscription(message, command, db):
    if message.chat.type != "private":
        return
    enabled = command.command == "subscribe"
    await db.subscribe(message.from_user.id, enabled)
    await message.answer("Announcements enabled." if enabled else "Announcements stopped.")


@router.callback_query(F.data.in_({"home", "help", "subscribe", "unsubscribe"}))
async def user_callback(callback, db, settings):
    await callback.answer()
    if not callback.message or callback.message.chat.type != "private":
        return
    if callback.data == "home":
        mode = "🧪 DEMO MODE — fictional responses only.\n" if settings.api_mode == "mock" else ""
        await callback.message.answer(mode + WELCOME, reply_markup=user_menu())
    elif callback.data == "help":
        await callback.message.answer(HELP, reply_markup=user_menu())
    else:
        await db.subscribe(callback.from_user.id, callback.data == "subscribe")
        await callback.message.answer("Announcement preference updated.")


@search_router.message(Command("num", "info"))
async def search(message, command, query, db, api):
    progress = await message.answer("🔍 Fetching secure records...", protect_content=True)
    await db.schedule_delete(progress.chat.id, progress.message_id, time.time() + 60)
    try:
        record = await api.search(command.command, query)
        text = card(query, record)
        status = "demo" if record.demo else "found"
    except APIError as exc:
        text = f"⚠️ {exc}\nDeletion scheduled in 60 seconds."
        status = "error"
    try:
        await progress.edit_text(text)
    finally:
        due = time.time() + 60
        await db.schedule_delete(message.chat.id, message.message_id, due)
        await db.schedule_delete(progress.chat.id, progress.message_id, due)
    await db.log_search(command.command, status)
