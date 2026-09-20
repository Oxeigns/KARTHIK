"""Private, ephemeral search results and subscription controls."""

import time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart

from api import APIError
from database import utc_day
from helpers import card, edit_panel, remaining
from keyboards import user_menu
from middlewares.subscription import membership, require_membership
from middlewares.throttling import SearchGuard

router = Router(name="user")
search_router = Router(name="search")
search_router.message.middleware(SearchGuard())
router.include_router(search_router)

HELP = (
    "📘 <b>SWAGGER • HELP CENTRE</b>\n\n"
    "/num &lt;number&gt; — authorized metadata lookup\n"
    "/info &lt;term&gt; — authorized record lookup\n"
    "One valid search attempt per UTC calendar day, shared by both commands. "
    "Failures also consume the attempt; owner/sudo are exempt.\n"
    "Results and query commands are scheduled for deletion after 60 seconds. "
    "Deletion cannot remove screenshots, notifications or provider logs.\n"
    "/subscribe and /unsubscribe control announcements.\n"
    "Use only records you have permission to access."
)


def welcome(settings):
    mode = (
        "🧪 DEMO MODE — fictional responses only."
        if settings.api_mode == "mock"
        else "🔌 HTTP mode • Provider responses"
    )
    if settings.api_mode == "sandbox":
        mode = "🧪 HTTP SANDBOX — fictional data over real HTTP. Try /info demo"
    return (
        "⚡ <b>SWAGGER</b>\n<i>Your private API workspace</i>\n\n"
        f"{mode}\n\n"
        "<b>Ready when you are</b>\n"
        "Open Search guide for commands, or My account to check your quota.\n"
        "Use Help for privacy and usage details."
    )


@router.message(CommandStart())
async def start(message, db, settings):
    if message.chat.type != "private":
        await message.answer("Open a private chat to use SWAGGER.")
        return
    await db.register(message.from_user.id)
    if not await require_membership(message, settings, message.from_user.id):
        return
    await message.answer(
        welcome(settings), reply_markup=user_menu(settings.is_admin(message.from_user.id))
    )


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
            welcome(settings),
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


@router.callback_query(
    F.data.in_({"home", "help", "subscribe", "unsubscribe", "account", "search:guide"})
)
async def user_callback(callback, db, settings):
    await callback.answer()
    if not callback.message or callback.message.chat.type != "private":
        return
    uid = callback.from_user.id
    menu = user_menu(settings.is_admin(uid))
    if callback.data == "home":
        text = welcome(settings)
    elif callback.data == "help":
        text = HELP
    elif callback.data == "search:guide":
        text = (
            "🔎 <b>Search guide</b>\n\n"
            "Send <code>/info &lt;record reference&gt;</code> for authorized metadata.\n"
            "Or <code>/num &lt;number&gt;</code> for your provider's number metadata.\n\n"
            "Each valid attempt uses your daily quota, including provider failures."
        )
        if settings.api_mode == "sandbox":
            text = (
                "🧪 <b>HTTP sandbox</b>\n\n"
                "Fictional data only. Try <code>/info demo</code>.\n"
                "Error fixtures: <code>/info test-not-found</code>, "
                "<code>/info test-rate-limit</code>, "
                "<code>/info test-server-error</code>, "
                "<code>/info test-invalid-json</code>, "
                "<code>/info test-timeout</code>.\n\n"
                "Daily quota still applies; owner/sudo are exempt."
            )
    elif callback.data == "account":
        await db.register(uid)
        row = await db.one("SELECT banned,subscribed FROM users WHERE id=?", (uid,))
        quota = await db.one("SELECT day FROM quotas WHERE user_id=?", (uid,))
        available = "0 / 1" if quota and quota[0] == utc_day() else "1 / 1"
        if settings.is_admin(uid):
            available = "Unlimited (admin)"
        text = (
            "👤 <b>My account</b>\n\n"
            f"ID: <code>{uid}</code>\n"
            f"Access: {'Restricted' if row[0] else 'Active'}\n"
            f"Attempts remaining: {available}\n"
            f"Quota resets in: {remaining()} (UTC)\n"
            f"Announcements: {'On' if row[1] else 'Off'}"
        )
    else:
        enabled = callback.data == "subscribe"
        await db.subscribe(uid, enabled)
        text = "🔔 Announcements enabled." if enabled else "🔕 Announcements stopped."
    await edit_panel(callback.message, text, menu)


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
