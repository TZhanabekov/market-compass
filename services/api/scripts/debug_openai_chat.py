#!/usr/bin/env python3
"""Debug OpenAI Chat Completions call locally.

This script mirrors the backend's OpenAI call shape for GPT-5 models.

Usage:
  cd services/api
  OPENAI_API_KEY="..." python -m scripts.debug_openai_chat

Optional:
  OPENAI_BASE_URL=https://api.openai.com/v1
  OPENAI_MODEL_PARSE=gpt-5-mini

Modes:
  - Default: minimal ping returning {"ok":true}
  - PATTERN_SUGGEST_DEMO=1: send a prompt similar to /v1/admin/patterns/suggest
"""

import asyncio
import json
import os
import re
from urllib.parse import urlparse

import httpx


def _extract_first_json_object(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _extract_message_content(choice: dict) -> str:
    """Mimic backend extraction for message.content."""
    msg = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts)
    return ""


def _pattern_suggest_prompts(items: list[dict[str, str]]) -> tuple[str, str]:
    system_prompt = (
        "You analyze iPhone shopping listings.\n"
        "Task: propose literal phrases (not regex) that help detect:\n"
        "- contract/plan listings (subscription/installments)\n"
        "- condition hints: new vs used vs refurbished\n\n"
        "You MUST use only phrases that appear in the provided inputs (title or link_hint).\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        '{ "contract": string[], "condition_new": string[], "condition_used": string[], "condition_refurbished": string[] }\n'
        "Rules:\n"
        "- lowercase phrases\n"
        "- phrases are 2..80 chars\n"
        "- no regex syntax, no wildcards\n"
        "- prefer multi-word phrases when possible"
    )
    user_prompt = (
        "inputs:\n"
        + "\n".join(f"- title: {x['title']}\n  link_hint: {x['link_hint']}" for x in items)
    )
    return system_prompt, user_prompt


async def main() -> None:
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL_PARSE", "gpt-5-mini")
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set")

    url = base_url + "/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if os.getenv("PATTERN_SUGGEST_DEMO", "").strip() == "1":
        # Use a small, real-looking sample similar to what we store in raw_offers.
        demo_items = [
            {
                "title": "Apple - Pre-Owned Excellent iPhone 16 Pro 5G 512GB - (Unlocked) - Black Titanium",
                "link_hint": "www.bestbuy.com/product/apple-pre-owned-excellent-iphone-16-pro-5g-512gb-unlocked-black-titanium",
            },
            {
                "title": "iPhone 17 Pro 1TB with contract - monthly payments",
                "link_hint": "www.google.com/search?ibp=oshop&q=iPhone+17+Pro+1TB&prds=productid:123,headlineOfferDocid:456",
            },
            {
                "title": "iPhone 16 Pro 256GB refurbished (renewed) - certified pre-owned",
                "link_hint": "example.com/iphone-16-pro-256gb-renewed?plan=installments",
            },
        ]
        system_prompt, user_prompt = _pattern_suggest_prompts(demo_items)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_completion_tokens": 1200,
            "reasoning_effort": "minimal",
            "response_format": {"type": "json_object"},
        }
        print("MODE=PATTERN_SUGGEST_DEMO")
        print("prompt preview:")
        print((system_prompt + "\n\n" + user_prompt)[:1200])
    else:
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
            if isinstance(data, dict) and isinstance(data.get("choices"), list) and data["choices"]:
                choice0 = data["choices"][0]
                if isinstance(choice0, dict):
                    print("finish_reason:", choice0.get("finish_reason"))
                    usage = data.get("usage")
                    if isinstance(usage, dict):
                        print("usage:", json.dumps(usage, ensure_ascii=False))
                    print("choice[0].message (truncated):")
                    print(json.dumps(choice0.get("message"), ensure_ascii=False)[:2000])
                    refusal = choice0.get("message", {}).get("refusal") if isinstance(choice0.get("message"), dict) else None
                    if refusal:
                        print("refusal:", refusal)
                    content_text = _extract_message_content(choice0)
                    print("extracted content_text:")
                    print(content_text[:2000])
                    parsed_obj = _extract_first_json_object(content_text)
                    print("parsed json_object from content_text:")
                    print(json.dumps(parsed_obj, ensure_ascii=False)[:2000])
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())

