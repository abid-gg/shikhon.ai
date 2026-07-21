import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from services.bloom_engine import _call_llm

MODEL = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-exp:free")


async def main() -> None:
    r = await _call_llm(
        os.environ["LLM_API_KEY"],
        os.environ["LLM_BASE_URL"],
        MODEL,
        "Return JSON only.",
        'Return {"ok": true}',
        retry_invalid_json=False,
    )
    print("LLM OK with model", MODEL, ":", r)


if __name__ == "__main__":
    asyncio.run(main())
