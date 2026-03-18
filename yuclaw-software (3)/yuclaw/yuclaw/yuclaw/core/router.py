"""yuclaw/core/router.py — Single router that works everywhere."""
from __future__ import annotations
import os
import httpx
from typing import Optional


class Router:
    """
    Routes LLM requests to:
    - Local vLLM on DGX Spark (YUCLAW_SUPER_ENDPOINT / YUCLAW_NANO_ENDPOINT)
    - OpenRouter as fallback (OPENROUTER_API_KEY)
    
    DGX Spark: set YUCLAW_SUPER_ENDPOINT=http://localhost:8001/v1
    Cloud:     set OPENROUTER_API_KEY=your_key
    """

    def __init__(self):
        self._super_endpoint = os.getenv("YUCLAW_SUPER_ENDPOINT", "")
        self._nano_endpoint  = os.getenv("YUCLAW_NANO_ENDPOINT", "")
        self._openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=600.0)

        if self._super_endpoint:
            self._mode = "local"
            self._super_model = "nemotron-3-super-local"
            self._nano_model  = "nemotron-3-super-local"
            print(f"[Router] DGX Spark mode — Super: {self._super_endpoint}")
        elif self._openrouter_key:
            self._mode = "openrouter"
            self._super_endpoint = "https://openrouter.ai/api/v1"
            self._nano_endpoint  = "https://openrouter.ai/api/v1"
            self._super_model = "nvidia/nemotron-3-super-120b-a12b:free"
            self._nano_model  = "nvidia/nemotron-3-super-120b-a12b:free"
            print("[Router] OpenRouter mode — Nemotron 3 Super free")
        else:
            raise ValueError(
                "Set YUCLAW_SUPER_ENDPOINT (DGX Spark) or OPENROUTER_API_KEY (cloud)"
            )

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        fast: bool = False,
        max_tokens: int = 8192,
    ) -> str:
        endpoint = self._nano_endpoint if fast else self._super_endpoint
        model    = self._nano_model   if fast else self._super_model

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {"Content-Type": "application/json"}
        if self._mode == "openrouter":
            headers["Authorization"] = f"Bearer {self._openrouter_key}"
            headers["HTTP-Referer"]   = "https://github.com/yuclaw"

        resp = await self._client.post(
            f"{endpoint}/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": 0.1},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def close(self):
        await self._client.aclose()


# Singleton
_router: Optional[Router] = None

def get_router() -> Router:
    global _router
    if _router is None:
        _router = Router()
    return _router
