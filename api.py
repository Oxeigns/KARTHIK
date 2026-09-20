import asyncio
import aiohttp

async def main():
    # Example URL hai; actual running API nahi.
    url = "https://venomsmm.info/PrimeAPIs/?key=OXYGEN-UKNOW&num=9876543210"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            params={"test_id": "sample-001"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
            data = await response.json()

            print(data["result"])

asyncio.run(main())

Bs i
