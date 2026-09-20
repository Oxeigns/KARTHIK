"""Entrypoint: one process/replica, polling or authenticated webhook."""

import asyncio
import contextlib
import logging
import signal

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from api import APIClient
from config import Settings
from database import Database
from handlers import admin, user
from helpers import deletion_worker, housekeeping
from sandbox_api import sandbox_endpoint

log = logging.getLogger(__name__)


async def run(settings):
    db = Database(settings.db_path)
    await db.open()
    bot = Bot(settings.token, default=DefaultBotProperties(parse_mode="HTML"))
    runner = None
    tasks = []
    try:
        async with (
            sandbox_endpoint(settings.api_mode) as sandbox_url,
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
        ):
            dp = Dispatcher(
                settings=settings,
                db=db,
                api=APIClient(settings, session, sandbox_url=sandbox_url),
                pending={},
                broadcast_lock=asyncio.Lock(),
            )
            dp.include_router(admin.router)
            dp.include_router(user.router)

            @dp.errors()
            async def error_handler(event):
                # No exception text: upstream errors may contain credentials/queries.
                log.error("Update failed: %s", type(event.exception).__name__)
                return True

            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Start / help"),
                    BotCommand(command="num", description="Authorized number metadata"),
                    BotCommand(command="info", description="Authorized record metadata"),
                    BotCommand(command="help", description="Usage and privacy"),
                    BotCommand(command="unsubscribe", description="Stop announcements"),
                ]
            )
            tasks = [
                asyncio.create_task(deletion_worker(bot, db)),
                asyncio.create_task(housekeeping(db)),
            ]
            app = web.Application(client_max_size=1024 * 1024)

            async def health(request):
                healthy = all(not task.done() for task in tasks)
                return web.json_response(
                    {"status": "ok" if healthy else "degraded"}, status=200 if healthy else 503
                )

            app.router.add_get("/healthz", health)
            if settings.mode == "webhook":
                SimpleRequestHandler(
                    dp, bot, secret_token=settings.webhook_secret, handle_in_background=False
                ).register(app, path="/telegram")
                setup_application(app, dp, bot=bot)
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", settings.port).start()
            if settings.mode == "webhook":
                await bot.set_webhook(
                    settings.webhook_url + "/telegram",
                    secret_token=settings.webhook_secret,
                    allowed_updates=dp.resolve_used_update_types(),
                    max_connections=20,
                )
                stop = asyncio.Event()
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    with contextlib.suppress(NotImplementedError):
                        loop.add_signal_handler(sig, stop.set)
                try:
                    await stop.wait()
                finally:
                    # Drain webhook requests before closing the HTTP API session.
                    await runner.cleanup()
                    runner = None
                    for sig in (signal.SIGTERM, signal.SIGINT):
                        with contextlib.suppress(NotImplementedError):
                            loop.remove_signal_handler(sig)
            else:
                await bot.delete_webhook(drop_pending_updates=False)
                await dp.start_polling(bot, close_bot_session=False, tasks_concurrency_limit=100)
    finally:
        if runner:
            await runner.cleanup()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    try:
        asyncio.run(run(Settings.load()))
    except KeyboardInterrupt:
        pass
