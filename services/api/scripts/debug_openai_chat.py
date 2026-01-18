#!/usr/bin/env python3
"""Debug OpenAI Chat Completions call locally.

This script mirrors the backend's OpenAI call shape for GPT-5 models.

Usage:
  cd services/api
  OPENAI_API_KEY="..." python -m scripts.debug_openai_chat

Optional:
  OPENAI_BASE_URL=https://api.openai.com/v1
  OPENAI_MODEL_PARSE=gpt-5-mini
"""

import asyncio
import json
import os
from urllib.parse import urlparse

import httpx


async def main() -> None:
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL_PARSE", "gpt-5-mini")
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set")

    url = base_url + "/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON: {\"ok\":true}"},
            {"role": "user", "content": "ping"},
        ],
        "max_completion_tokens": 200,
        "response_format": {"type": "json_object"},
    }

    print(f"POST {url} (host={urlparse(base_url).hostname}, model={model})")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=body)
        print("status:", r.status_code)
        print("x-request-id:", r.headers.get("x-request-id"))
        print("body (truncated):")
        text = r.text
        print(text[:4000])
        # Try to parse JSON
        try:
            data = r.json()
            print("parsed json keys:", list(data.keys()) if isinstance(data, dict) else type(data))
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())

