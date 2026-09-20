from dataclasses import replace

import aiohttp
import pytest

from api import APIClient, APIError
from config import Settings
from handlers.user import welcome
from helpers import card
from sandbox_api import sandbox_endpoint


async def test_sandbox_actual_http_ignores_external_settings_and_cleans_up():
    settings = Settings(
        "unused", 1, api_mode="sandbox", api_url="https://unused.invalid", api_key="DO_NOT_SEND"
    )
    async with aiohttp.ClientSession() as session:
        async with sandbox_endpoint("sandbox") as url:
            assert url.startswith("http://127.0.0.1:")
            client = APIClient(settings, session, sandbox_url=url)
            record = await client.search("info", "demo")
            assert record.demo and record.entity == "FICTIONAL TEST ITEM 001"
            assert "DEMO" in card("demo", record)
            assert await client.search("num", "0000000000") == record
            assert "HTTP SANDBOX" in welcome(settings)
            # Only GET is supported by the sandbox, proving APIClient used GET above.
            async with session.post(url + "/info", json={"query": "demo"}) as response:
                assert response.status == 405
            async with session.get(url + "/info", params={"query": "a&b + / हिन्दी"}) as response:
                assert response.status == 200
            # Validate the live server directly, including malformed requests.
            async with session.get(url + "/info", params={"query": ""}) as response:
                assert response.status == 400
            async with session.get(url + "/info") as response:
                assert response.status == 400
        with pytest.raises(aiohttp.ClientError):
            await session.get(url + "/info", params={"query": "demo"})


@pytest.mark.parametrize(
    "query,error",
    [
        ("test-not-found", "No record found"),
        ("test-rate-limit", "temporarily unavailable"),
        ("test-server-error", "temporarily unavailable"),
        ("test-invalid-json", "invalid JSON"),
        ("test-timeout", "Provider unavailable"),
    ],
)
async def test_sandbox_http_error_scenarios(query, error):
    async with sandbox_endpoint("sandbox") as url, aiohttp.ClientSession() as session:
        settings = Settings("unused", 1, api_mode="sandbox")
        with pytest.raises(APIError, match=error):
            await APIClient(settings, session, sandbox_url=url).search("info", query)


async def test_missing_sandbox_never_falls_back_to_external_url():
    settings = Settings("unused", 1, api_mode="sandbox", api_url="https://unused.invalid")
    with pytest.raises(APIError, match="not running"):
        await APIClient(settings, None).search("info", "demo")
    with pytest.raises(APIError, match="Invalid API mode"):
        await APIClient(replace(settings, api_mode="typo"), None).search("info", "demo")
    async with sandbox_endpoint("http") as url:
        assert url is None


def test_sandbox_config_does_not_require_external_url(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:" + "A" * 35)
    monkeypatch.setenv("OWNER_ID", "1")
    monkeypatch.setenv("FORCE_SUB_CHAT_ID", "")
    monkeypatch.setenv("FORCE_SUB_URL", "")
    monkeypatch.setenv("API_MODE", " Sandbox ")
    monkeypatch.setenv("BOT_MODE", " POLLING ")
    monkeypatch.setenv("API_BASE_URL", "")
    assert Settings.load().api_mode == "sandbox"
    monkeypatch.setenv("API_BASE_URL", "not-a-url")
    assert Settings.load().mode == "polling"
    monkeypatch.setenv("API_MODE", "http")
    with pytest.raises(ValueError, match="HTTPS"):
        Settings.load()
