"""Mock provider and an explicit, provider-neutral HTTP adapter contract."""

import asyncio
import json
from dataclasses import dataclass

import aiohttp


class APIError(Exception):
    """Safe end-user message, with no upstream payload or URL."""


@dataclass(frozen=True)
class Record:
    entity: str
    provider: str
    region: str
    risk: str
    demo: bool = False


def parse_record(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise APIError("Provider returned an invalid response.")
    data = payload["data"]
    fields = ("entity", "provider", "region", "risk_score")
    if not any(data.get(k) is not None for k in fields):
        raise APIError("No record found.")
    values = []
    for key in fields:
        value = data.get(key)
        if value is None:
            value = "Not supplied"
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise APIError("Provider returned an invalid field.")
        values.append(str(value)[:250])
    return Record(*values)


class APIClient:
    def __init__(self, settings, session):
        self.settings = settings
        self.session = session
        self.slots = asyncio.Semaphore(20)

    async def search(self, kind, query):
        if kind not in {"num", "info"}:
            raise APIError("Unsupported search.")
        if self.settings.api_mode == "mock":
            return Record(
                "DEMO ENTITY — fictional", "Demo provider", "Demo region", "Not assessed", True
            )
        try:
            # Total deadline includes concurrency wait, retries, and HTTP reads.
            async with asyncio.timeout(10):
                async with self.slots:
                    return await self._request(kind, query)
        except (TimeoutError, aiohttp.ClientError):
            raise APIError("Provider unavailable. Please try again later.") from None

    async def _request(self, kind, query):
        headers = {}
        if self.settings.api_key:
            headers["Authorization"] = "Bearer " + self.settings.api_key
        for attempt in range(3):
            async with self.session.post(
                self.settings.api_url + "/" + kind,
                json={"query": query},
                headers=headers,
                allow_redirects=False,
            ) as response:
                if response.status >= 500 or response.status == 429:
                    if attempt < 2:
                        await asyncio.sleep(0.25 * (2**attempt))
                        continue
                    raise APIError("Provider temporarily unavailable.")
                if response.status == 404:
                    raise APIError("No record found.")
                if response.status == 400:
                    raise APIError("Provider rejected this query.")
                if response.status != 200:
                    raise APIError("Provider configuration or access error.")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(16384):
                    raw.extend(chunk)
                    if len(raw) > 262144:
                        raise APIError("Provider response is too large.")
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise APIError("Provider returned invalid JSON.") from None
                return parse_record(payload)
        raise APIError("Provider unavailable.")
