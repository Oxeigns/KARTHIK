"""Formatting and restart-safe best-effort deletion/background workers."""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

log = logging.getLogger(__name__)


def remaining(now=None):
    now = now or datetime.now(timezone.utc)
    end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    seconds = max(0, int((end - now).total_seconds()))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def card(query, record):
    mode = "🧪 DEMO — fictional data" if record.demo else "🟢 Record Found"
    rows = [
        "⚡ <b>SWAGGER INTELLIGENCE SYSTEM</b>",
        "────────────────────────",
        f"<b>Query:</b> <code>{escape(query)}</code>",
        f"<b>Status:</b> {mode}",
        "",
        "<b>Result Details:</b>",
    ]
    for label, value in [
        ("Name / Entity", record.entity),
        ("Carrier / Provider", record.provider),
        ("Region / Circle", record.region),
        ("Risk Score", record.risk),
    ]:
        rows.append(f"• <b>{label}:</b> {escape(value)}")
    rows += [
        "────────────────────────",
        "⚠️ <i>Deletion scheduled in 60 seconds. Not a secrecy guarantee.</i>",
    ]
    return "\n".join(rows)


async def deletion_worker(bot, db):
    while True:
        rows = await db.all(
            "SELECT * FROM deletions WHERE due<=? ORDER BY due LIMIT 100", (time.time(),)
        )
        for row in rows:
            retry = None
            try:
                await bot.delete_message(row["chat"], row["message"])
            except TelegramRetryAfter as exc:
                retry = max(1, exc.retry_after)
            except (TelegramBadRequest, TelegramForbiddenError):
                log.warning("Message deletion unavailable; permissions or age limit")
            except TelegramAPIError:
                retry = min(60, 2 ** min(row["attempts"], 6))
            if retry is not None and row["attempts"] < 10:
                await db.conn.execute(
                    "UPDATE deletions SET due=?,attempts=attempts+1 WHERE chat=? AND message=?",
                    (time.time() + retry, row["chat"], row["message"]),
                )
            else:
                if retry is not None:
                    log.warning("Deletion retries exhausted")
                await db.conn.execute(
                    "DELETE FROM deletions WHERE chat=? AND message=?",
                    (row["chat"], row["message"]),
                )
        await asyncio.sleep(0.5)


async def housekeeping(db):
    while True:
        await db.cleanup()
        now = datetime.now(timezone.utc)
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=1, microsecond=0)
        await asyncio.sleep((midnight - now).total_seconds())


async def edit_panel(message, text, reply_markup):
    """Navigate in place; handle repeated taps without hiding other API errors."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
