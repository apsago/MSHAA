import aiohttp
import asyncio
from datetime import datetime
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent / "robotpolicies"
POLICY_DIR.mkdir(exist_ok=True)

ROBOTS_URL = "https://www.mshsaa.org/robots.txt"

async def fetch_and_save_robots():
    filename = POLICY_DIR / f"robots_{datetime.now():%Y%m%d_%H%M%S}.txt"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ROBOTS_URL, timeout=20) as r:
                text = await r.text()
        filename.write_text(text, encoding="utf-8")
        print(f"Saved {ROBOTS_URL} to {filename}")
    except Exception as e:
        print(f"Could not fetch {ROBOTS_URL}: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_and_save_robots())