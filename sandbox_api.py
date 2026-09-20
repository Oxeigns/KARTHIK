"""Fictional HTTP service, bound only to loopback and never to a public port."""

import asyncio
from contextlib import asynccontextmanager

from aiohttp import web


async def lookup(request):
    query = request.query.get("query")
    if not isinstance(query, str) or not 1 <= len(query) <= 120:
        return web.json_response({"status": False}, status=400)

    # These exact fixture names exercise the client's real HTTP error paths.
    scenario = query.strip().lower()
    if scenario == "test-not-found":
        return web.json_response({"status": False}, status=404)
    if scenario == "test-rate-limit":
        return web.json_response({"status": False}, status=429)
    if scenario == "test-server-error":
        return web.json_response({"status": False}, status=503)
    if scenario == "test-invalid-json":
        return web.Response(text="Fictional invalid JSON fixture")
    if scenario == "test-timeout":
        await asyncio.sleep(11)

    # Never reflect input or resolve an identity. Every successful query gets this fixture.
    return web.json_response(
        {
            "status": True,
            "data": {
                "entity": "FICTIONAL TEST ITEM 001",
                "provider": "Local HTTP Sandbox",
                "region": "Imaginary Test Region",
                "risk_score": "Not assessed — synthetic data",
            },
        }
    )


def create_app():
    app = web.Application(client_max_size=4096)
    app.router.add_get("/info", lookup)
    app.router.add_get("/num", lookup)
    return app


@asynccontextmanager
async def sandbox_endpoint(mode):
    """Start alongside the bot in sandbox mode; clean up even if startup fails."""
    if mode != "sandbox":
        yield None
        return
    runner = web.AppRunner(create_app(), access_log=None, shutdown_timeout=1)
    try:
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        port = runner.addresses[0][1]
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()
