"""Small callback payloads never contain query data."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def user_menu():
    return keyboard(
        [
            [("Help", "help")],
            [("Subscribe to updates", "subscribe")],
            [("Stop updates", "unsubscribe")],
        ]
    )


def force_sub_menu(url):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join channel", url=url)],
            [InlineKeyboardButton(text="✅ I've joined — Check", callback_data="force:check")],
        ]
    )


def owner_link(owner_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Upgrade / Contact Owner", url=f"tg://user?id={owner_id}")]
        ]
    )


def admin_menu():
    return keyboard(
        [
            [("Statistics", "admin:stats"), ("Users", "admin:users:0")],
            [("Maintenance ON", "admin:on"), ("OFF", "admin:off")],
        ]
    )


def user_pages(page, more):
    row = []
    if page > 0:
        row.append(("Previous", f"admin:users:{page - 1}"))
    if more:
        row.append(("Next", f"admin:users:{page + 1}"))
    return keyboard([row]) if row else None
