"""Atomic UTC daily reservations and durable message-deletion queue."""

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


def utc_day(now=None):
    return (
        datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc)
        .date()
        .isoformat()
    )


class Database:
    def __init__(self, path):
        self.path = path
        self.lock = asyncio.Lock()

    async def open(self):
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path, isolation_level=None)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA busy_timeout=5000")
        row = await self.one("PRAGMA user_version")
        if row[0] > 1:
            raise RuntimeError("Database schema is newer than this application")
        await self.conn.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, banned INTEGER NOT NULL DEFAULT 0,
          subscribed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS quotas(
          user_id INTEGER PRIMARY KEY, day TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS searches(
          id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
          status TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(
          key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deletions(
          chat INTEGER NOT NULL, message INTEGER NOT NULL,
          due REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(chat,message));
        CREATE INDEX IF NOT EXISTS deletion_due ON deletions(due);
        PRAGMA user_version=1;
        COMMIT;
        """)

    async def close(self):
        await self.conn.close()

    async def one(self, sql, args=()):
        async with self.conn.execute(sql, args) as cursor:
            return await cursor.fetchone()

    async def all(self, sql, args=()):
        async with self.conn.execute(sql, args) as cursor:
            return await cursor.fetchall()

    async def register(self, uid):
        await self.conn.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))

    async def ban(self, uid, banned):
        await self.register(uid)
        await self.conn.execute("UPDATE users SET banned=? WHERE id=?", (banned, uid))

    async def subscribe(self, uid, value):
        await self.register(uid)
        await self.conn.execute("UPDATE users SET subscribed=? WHERE id=?", (value, uid))

    async def maintenance(self):
        row = await self.one("SELECT value FROM settings WHERE key='maintenance'")
        return row is not None and row[0] == "1"

    async def set_maintenance(self, enabled):
        await self.conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('maintenance',?)",
            ("1" if enabled else "0",),
        )

    async def reserve(self, uid, exempt=False, day=None):
        """One atomic SQL write arbitrates simultaneous search requests."""
        await self.register(uid)
        row = await self.one("SELECT banned FROM users WHERE id=?", (uid,))
        if row[0]:
            return "banned"
        if exempt:
            return "ok"
        if await self.maintenance():
            return "maintenance"
        async with self.conn.execute(
            """
            INSERT INTO quotas(user_id,day) VALUES(?,?)
            ON CONFLICT(user_id) DO UPDATE SET day=excluded.day
            WHERE quotas.day != excluded.day RETURNING user_id
        """,
            (uid, day or utc_day()),
        ) as cursor:
            return "ok" if await cursor.fetchone() else "quota"

    async def reset(self, uid):
        await self.conn.execute("DELETE FROM quotas WHERE user_id=?", (uid,))

    async def log_search(self, kind, status):
        # Deliberately exclude queries, personal records, and user IDs.
        await self.conn.execute(
            "INSERT INTO searches(kind,status,created) VALUES(?,?,?)", (kind, status, time.time())
        )

    async def schedule_delete(self, chat, message, due):
        await self.conn.execute(
            """
            INSERT INTO deletions(chat,message,due) VALUES(?,?,?)
            ON CONFLICT(chat,message) DO UPDATE SET due=excluded.due
        """,
            (chat, message, due),
        )

    async def stats(self):
        users = await self.one("SELECT COUNT(*) FROM users")
        searches = await self.one("SELECT COUNT(*) FROM searches")
        return users[0], searches[0]

    async def cleanup(self):
        await self.conn.execute("DELETE FROM quotas WHERE day < ?", (utc_day(),))
        await self.conn.execute(
            "DELETE FROM searches WHERE created < ?", (time.time() - 30 * 86400,)
        )
