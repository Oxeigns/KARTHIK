import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.filters.command import CommandObject
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from api import APIClient, APIError, Record, parse_record
from config import Settings
from database import Database
from helpers import card, deletion_worker, remaining
from middlewares.auth import AdminGuard
from middlewares.throttling import SearchGuard


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.open()
    yield database
    await database.close()


async def test_atomic_quota(db):
    results = await asyncio.gather(*(db.reserve(7) for _ in range(50)))
    assert results.count("ok") == 1
    assert results.count("quota") == 49


async def test_quota_cross_connection(tmp_path):
    a, b = Database(str(tmp_path / "shared.db")), Database(str(tmp_path / "shared.db"))
    await a.open()
    await b.open()
    try:
        results = await asyncio.gather(a.reserve(1), b.reserve(1))
        assert sorted(results) == ["ok", "quota"]
    finally:
        await a.close()
        await b.close()


async def test_rollover_ban_maintenance_and_reset(db):
    assert await db.reserve(3, day="2026-01-01") == "ok"
    assert await db.reserve(3, day="2026-01-02") == "ok"
    assert await db.reserve(3, day="2026-01-02") == "quota"
    await db.reset(3)
    assert await db.reserve(3, day="2026-01-02") == "ok"
    await db.set_maintenance(True)
    assert await db.reserve(4) == "maintenance"
    assert await db.reserve(4, exempt=True) == "ok"
    assert await db.reserve(4, exempt=True) == "ok"
    await db.ban(4, True)
    assert await db.reserve(4, exempt=True) == "banned"


async def test_restart_persistence(tmp_path):
    path = str(tmp_path / "persist.db")
    first = Database(path)
    await first.open()
    await first.reserve(1)
    await first.schedule_delete(1, 2, 0)
    await first.close()
    second = Database(path)
    await second.open()
    try:
        assert await second.reserve(1) == "quota"
        assert len(await second.all("SELECT * FROM deletions")) == 1
    finally:
        await second.close()


async def test_deletion_recovery(db):
    await db.schedule_delete(1, 2, 0)
    bot = SimpleNamespace(delete_message=AsyncMock())
    task = asyncio.create_task(deletion_worker(bot, db))
    try:
        for _ in range(100):
            if not await db.all("SELECT * FROM deletions"):
                break
            await asyncio.sleep(0.01)
        bot.delete_message.assert_awaited_once_with(1, 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_escape_and_quota_clock():
    text = card("<secret>", Record("<name>", "&provider", "x", "y", True))
    assert "&lt;secret&gt;" in text and "&lt;name&gt;" in text
    assert "DEMO" in text
    assert remaining(datetime(2026, 1, 1, 23, 59, 59, tzinfo=timezone.utc)) == "00:00:01"
    assert remaining(datetime(2026, 1, 1, tzinfo=timezone.utc)) == "24:00:00"


@pytest.mark.parametrize("payload", [None, [], {}, {"data": {}}, {"data": {"entity": []}}])
def test_bad_schema(payload):
    with pytest.raises(APIError):
        parse_record(payload)


async def test_mock_never_calls_network():
    client = APIClient(SimpleNamespace(api_mode="mock"), None)
    record = await client.search("num", "15551234567")
    assert record.demo and "fictional" in record.entity


@pytest.mark.parametrize(
    "status,body,error",
    [
        (200, '{"data":{"entity":"Demo"}}', None),
        (200, "oops", "invalid JSON"),
        (200, "{}", "invalid response"),
        (400, "private payload", "rejected"),
        (404, "private payload", "No record"),
        (500, "private payload", "temporarily"),
        (403, "private payload", "configuration"),
    ],
)
async def test_http_mapping(status, body, error):
    calls = []

    async def endpoint(request):
        calls.append(await request.json())
        return web.Response(status=status, text=body)

    app = web.Application()
    app.router.add_post("/info", endpoint)
    async with TestServer(app) as server, ClientSession() as session:
        settings = SimpleNamespace(
            api_mode="http", api_url=str(server.make_url("")).rstrip("/"), api_key="test"
        )
        client = APIClient(settings, session)
        if error:
            with pytest.raises(APIError, match=error):
                await client.search("info", "sample")
        else:
            assert (await client.search("info", "sample")).entity == "Demo"
    assert len(calls) == (3 if status == 500 else 1)
    assert calls[0] == {"query": "sample"}


async def test_admin_denied():
    event = SimpleNamespace(from_user=SimpleNamespace(id=9), answer=AsyncMock())
    handler = AsyncMock()
    await AdminGuard()(handler, event, {"settings": Settings("unused", 1)})
    handler.assert_not_awaited()
    event.answer.assert_awaited_once()


async def test_search_guard_consumes_only_valid_attempts(db):
    settings = Settings("unused", 1)
    event = SimpleNamespace(
        chat=SimpleNamespace(id=5, type="private"),
        message_id=2,
        from_user=SimpleNamespace(id=5),
        answer=AsyncMock(),
    )
    handler = AsyncMock()
    data = {"db": db, "settings": settings, "command": CommandObject(command="num", args="bad")}
    await SearchGuard()(handler, event, data)
    handler.assert_not_awaited()
    data["command"] = CommandObject(command="num", args="+15551234567")
    await SearchGuard()(handler, event, data)
    assert handler.await_count == 1
    await SearchGuard()(handler, event, data)
    assert handler.await_count == 1


def test_config_validation(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:" + "A" * 35)
    monkeypatch.setenv("OWNER_ID", "123")
    monkeypatch.setenv("API_MODE", "mock")
    assert Settings.load().api_mode == "mock"
    monkeypatch.setenv("API_MODE", "http")
    monkeypatch.setenv("API_BASE_URL", "http://unsafe.invalid")
    with pytest.raises(ValueError, match="HTTPS"):
        Settings.load()


async def test_search_schedules_both_messages(db):
    from handlers.user import search

    progress = SimpleNamespace(chat=SimpleNamespace(id=9), message_id=11, edit_text=AsyncMock())
    message = SimpleNamespace(
        chat=SimpleNamespace(id=9), message_id=10, answer=AsyncMock(return_value=progress)
    )
    api = APIClient(SimpleNamespace(api_mode="mock"), None)
    await search(message, CommandObject(command="info"), "demo", db, api)
    rows = await db.all("SELECT * FROM deletions ORDER BY message")
    assert [r["message"] for r in rows] == [10, 11]
    assert rows[0]["due"] == rows[1]["due"]
    assert "DEMO" in progress.edit_text.call_args.args[0]


async def test_http_timeout_is_safe():
    from aiohttp import ClientError

    class BrokenSession:
        def post(self, *args, **kwargs):
            raise ClientError("SECRET in upstream URL")

    settings = SimpleNamespace(api_mode="http", api_url="https://example.invalid", api_key="")
    with pytest.raises(APIError) as error:
        await APIClient(settings, BrokenSession()).search("info", "private query")
    assert "SECRET" not in str(error.value)


async def test_deletion_retry_is_persisted(db):
    from aiogram.exceptions import TelegramRetryAfter
    from aiogram.methods import DeleteMessage

    await db.schedule_delete(1, 2, 0)
    failure = TelegramRetryAfter(
        method=DeleteMessage(chat_id=1, message_id=2),
        message="Rate limited",
        retry_after=30,
    )
    bot = SimpleNamespace(delete_message=AsyncMock(side_effect=failure))
    task = asyncio.create_task(deletion_worker(bot, db))
    try:
        for _ in range(100):
            row = await db.one("SELECT attempts FROM deletions")
            if row[0] == 1:
                break
            await asyncio.sleep(0.01)
        assert row[0] == 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_webhook_rejects_missing_secret():
    from aiogram import Bot, Dispatcher
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler

    bot = Bot("123456:" + "A" * 35)
    app = web.Application()
    SimpleRequestHandler(Dispatcher(), bot, secret_token="test-secret").register(
        app, path="/telegram"
    )
    try:
        async with TestServer(app) as server, ClientSession() as session:
            async with session.post(server.make_url("/telegram"), json={}) as response:
                assert response.status == 401
    finally:
        await bot.session.close()


async def test_dispatcher_search_routing(db):
    from aiogram import Bot, Dispatcher
    from aiogram.types import Chat, Message, MessageEntity, Update, User

    from handlers import admin, user

    bot = Bot("123456:" + "A" * 35)
    bot.session = SimpleNamespace(close=AsyncMock())
    # A mocked Bot call avoids all Telegram network traffic.
    response = Message(
        message_id=20,
        date=datetime.now(timezone.utc),
        chat=Chat(id=9, type="private"),
        text="processing",
    )
    bot.session = AsyncMock(return_value=response.as_(bot))
    dispatcher = Dispatcher(
        settings=Settings("unused", 1),
        db=db,
        api=APIClient(SimpleNamespace(api_mode="mock"), None),
        pending={},
        broadcast_lock=asyncio.Lock(),
    )
    dispatcher.include_router(admin.router)
    dispatcher.include_router(user.router)
    update = Update(
        update_id=1,
        message=Message(
            message_id=10,
            date=datetime.now(timezone.utc),
            chat=Chat(id=9, type="private"),
            from_user=User(id=9, is_bot=False, first_name="Tester"),
            text="/info demo",
            entities=[MessageEntity(type="bot_command", offset=0, length=5)],
        ),
    )
    await dispatcher.feed_update(bot, update)
    assert (await db.one("SELECT COUNT(*) FROM searches"))[0] == 1
    assert (await db.one("SELECT COUNT(*) FROM deletions"))[0] == 2
