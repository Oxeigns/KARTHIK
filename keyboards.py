"""Consistent Telegram-native colour styles and short navigation payloads."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

OWNER_URL = "https://t.me/Notethicals"
SUPPORT_URL = "https://t.me/+hQh4Azoq9BoxMjk1"


def keyboard(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=item[0],
                    callback_data=item[1],
                    style=item[2] if len(item) > 2 else "primary",
                )
                for item in row
            ]
            for row in rows
        ]
    )


def user_menu(is_admin=False):
    menu = keyboard(
        [
            [("🔎 Search guide", "search:guide"), ("👤 My account", "account")],
            [("🏠 Home", "home"), ("📘 Help", "help")],
            [
                ("🔔 Updates on", "subscribe", "success"),
                ("🔕 Updates off", "unsubscribe", "danger"),
            ],
        ]
    )
    menu.inline_keyboard.append(
        [
            InlineKeyboardButton(text="👑 Owner", url=OWNER_URL),
            InlineKeyboardButton(text="💬 Support", url=SUPPORT_URL),
        ]
    )
    if is_admin:
        menu.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="⚙️ Control panel", callback_data="admin:stats", style="primary"
                )
            ]
        )
    return menu


def force_sub_menu(url):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join channel", url=url, style="primary")],
            [
                InlineKeyboardButton(
                    text="✅ Check membership", callback_data="force:check", style="success"
                )
            ],
        ]
    )


def owner_link(owner_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Contact owner", url=OWNER_URL, style="primary")]
        ]
    )


def admin_menu(maintenance=False):
    toggle = (
        ("▶️ Resume service", "admin:off", "success")
        if maintenance
        else ("⏸ Pause service", "admin:on", "danger")
    )
    return keyboard(
        [
            [("📊 Overview", "admin:stats"), ("👥 Users", "admin:users:0")],
            [("🔌 API setup", "admin:api"), ("🛠 User controls", "admin:help")],
            [toggle],
            [("🏠 Home", "home")],
        ]
    )


def user_pages(page, more):
    row = []
    if page > 0:
        row.append(("← Previous", f"admin:users:{page - 1}"))
    if more:
        row.append(("Next →", f"admin:users:{page + 1}"))
    return keyboard(([row] if row else []) + [[("← Control panel", "admin:stats")]])
