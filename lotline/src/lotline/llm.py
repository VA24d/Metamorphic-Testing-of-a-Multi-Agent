"""LLM backend detection: Ollama when available, otherwise mock mode."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def ollama_available(host: str | None = None, timeout: float = 0.6) -> bool:
    base = host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ollama_generate(
    prompt: str,
    model: str | None = None,
    host: str | None = None,
    temperature: float = 0.0,
) -> str:
    """Best-effort JSON/text generation via Ollama HTTP API (no extra deps)."""
    base = host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
        "format": "json",
    }
    req = urllib.request.Request(
        f"{base}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("response", "")


def resolve_mode(force: str | None = None) -> str:
    """Return 'ollama' or 'mock'."""
    if force in {"ollama", "mock"}:
        return force
    env = (
        os.environ.get("METROMORPH_MODE")
        or os.environ.get("LOTLINE_MODE")
        or ""
    ).lower()
    if env in {"ollama", "mock"}:
        return env
    return "ollama" if ollama_available() else "mock"
