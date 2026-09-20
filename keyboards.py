"""Small callback payloads never contain query data."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

OWNER_URL = "https://t.me/Notethicals"
SUPPORT_URL = "https://t.me/+hQh4Azoq9BoxMjk1"


def keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def user_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Home", callback_data="home", style="primary"),
                InlineKeyboardButton(text="📘 Help", callback_data="help", style="primary"),
            ],
            [
                InlineKeyboardButton(text="👑 Owner", url=OWNER_URL),
                InlineKeyboardButton(text="💬 Support", url=SUPPORT_URL),
            ],
            [
                InlineKeyboardButton(
                    text="🔔 Get updates", callback_data="subscribe", style="success"
                ),
                InlineKeyboardButton(
                    text="🔕 Stop updates", callback_data="unsubscribe", style="danger"
                ),
            ],
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
        inline_keyboard=[[InlineKeyboardButton(text="Upgrade / Contact Owner", url=OWNER_URL)]]
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
