"""Small multi-provider text model router for CartoonTamilan automation.

API keys are read only from the process environment / Oracle .env file.
This module never logs credentials or sends them to the browser.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AIConfigError(RuntimeError):
    """AI provider configuration is incomplete or invalid."""


class AIRequestError(RuntimeError):
    """AI request failed without exposing credentials."""


class AIDailyLimitError(RuntimeError):
    """The configured daily request budget has been reached."""


_PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL"),
    "xai": ("XAI_API_KEY", "XAI_MODEL"),
}
_ALIASES = {"claude": "anthropic", "grok": "xai", "google": "gemini"}


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise AIConfigError(f"{name} must be an integer.") from exc
    if value < 1:
        raise AIConfigError(f"{name} must be at least 1.")
    return value


def _request_limit() -> int:
    raw = os.getenv("AI_DAILY_REQUEST_LIMIT", "20").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise AIConfigError("AI_DAILY_REQUEST_LIMIT must be an integer.") from exc
    if value < 0:
        raise AIConfigError("AI_DAILY_REQUEST_LIMIT cannot be negative.")
    return value


def _reserve_request(provider: str) -> None:
    """Atomically reserve one daily request; failed API calls count toward budget."""
    limit = _request_limit()
    if limit == 0 or provider == "ollama":
        return
    db_path = Path(os.getenv("AI_USAGE_DB", "data/ai_usage.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        with sqlite3.connect(db_path, timeout=15) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS daily_usage ("
                "provider TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL, "
                "PRIMARY KEY(provider, day))"
            )
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT count FROM daily_usage WHERE provider=? AND day=?",
                (provider, day),
            ).fetchone()
            count = row[0] if row else 0
            if count >= limit:
                raise AIDailyLimitError(
                    f"Daily AI request limit ({limit}) reached for {provider}."
                )
            db.execute(
                "INSERT INTO daily_usage(provider, day, count) VALUES(?, ?, 1) "
                "ON CONFLICT(provider, day) DO UPDATE SET count=count+1",
                (provider, day),
            )
    except AIDailyLimitError:
        raise
    except sqlite3.Error as exc:
        raise AIRequestError("Could not reserve the AI usage budget.") from exc


def _text_from_responses(data: dict) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    pieces = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {
                "output_text", "text"
            }:
                value = content.get("text")
                if isinstance(value, str):
                    pieces.append(value)
    result = "\n".join(pieces).strip()
    if not result:
        raise AIRequestError("The AI provider returned no text.")
    return result


def _post(url: str, *, headers: dict, payload: dict, timeout: int = 90) -> dict:
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise AIRequestError("Could not connect to the selected AI provider.") from exc
    if not response.ok:
        # Do not include response bodies or request headers: they can contain secrets.
        raise AIRequestError(
            f"AI provider returned HTTP {response.status_code}; check its key, model, "
            "quota and API access."
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise AIRequestError("AI provider returned an unreadable response.") from exc
    if not isinstance(data, dict):
        raise AIRequestError("AI provider returned an unexpected response.")
    return data


def _local_url() -> str:
    raw = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise AIConfigError("LOCAL_LLM_URL must point to localhost over HTTP.")
    return raw


def complete(
    prompt: str,
    *,
    provider: str | None = None,
    system_prompt: str = "",
    model: str | None = None,
    max_output_tokens: int = 800,
    timeout: int = 90,
) -> str:
    """Generate text using OpenAI, Claude, Gemini, Grok, or a local Ollama model.

    Set AI_PROVIDER and the chosen provider's API key/model in Oracle's .env.
    AI_DAILY_REQUEST_LIMIT defaults to 20 per provider (set 0 to disable the cap).
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string.")
    provider = (provider or os.getenv("AI_PROVIDER", "ollama")).strip().lower()
    provider = _ALIASES.get(provider, provider)
    maximum = min(_positive_int("AI_MAX_OUTPUT_TOKENS", 1200), 4096)
    if not isinstance(max_output_tokens, int) or max_output_tokens < 1:
        raise ValueError("max_output_tokens must be a positive integer.")
    if max_output_tokens > maximum:
        raise ValueError(
            f"max_output_tokens exceeds the configured cap ({maximum})."
        )
    timeout = max(5, min(int(timeout), 180))
    if provider == "ollama":
        selected_model = model or os.getenv("LOCAL_LLM_MODEL", "").strip()
        if not selected_model:
            raise AIConfigError("Set LOCAL_LLM_MODEL to an installed Ollama model.")
        _reserve_request(provider)
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        data = _post(
            _local_url() + "/api/chat",
            headers={"Content-Type": "application/json"},
            payload={
                "model": selected_model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_output_tokens},
            },
            timeout=timeout,
        )
        text = (data.get("message") or {}).get("content", "")
        if not isinstance(text, str) or not text.strip():
            raise AIRequestError("The local model returned no text.")
        return text.strip()

    if provider not in _PROVIDER_ENV:
        raise AIConfigError(
            "AI_PROVIDER must be openai, anthropic/claude, gemini, xai/grok, or ollama."
        )
    key_name, model_name = _PROVIDER_ENV[provider]
    api_key = os.getenv(key_name, "").strip()
    selected_model = model or os.getenv(model_name, "").strip()
    if not api_key:
        raise AIConfigError(f"Set {key_name} in Oracle .env (never in chat or GitHub).")
    if not selected_model:
        raise AIConfigError(f"Set {model_name} to a model enabled for your account.")
    _reserve_request(provider)

    if provider == "openai":
        payload = {
            "model": selected_model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if system_prompt.strip():
            payload["instructions"] = system_prompt
        data = _post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            payload=payload,
            timeout=timeout,
        )
        return _text_from_responses(data)

    if provider == "xai":
        input_items = []
        if system_prompt.strip():
            input_items.append({"role": "system", "content": system_prompt})
        input_items.append({"role": "user", "content": prompt})
        data = _post(
            "https://api.x.ai/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            payload={
                "model": selected_model,
                "input": input_items,
                "max_output_tokens": max_output_tokens,
            },
            timeout=timeout,
        )
        return _text_from_responses(data)

    if provider == "anthropic":
        payload = {
            "model": selected_model,
            "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt.strip():
            payload["system"] = system_prompt
        data = _post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
            timeout=timeout,
        )
        parts = [
            item.get("text", "")
            for item in data.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]
    else:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }
        if system_prompt.strip():
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        data = _post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{selected_model}:generateContent",
            headers={"x-goog-api-key": api_key},
            payload=body,
            timeout=timeout,
        )
        parts = [
            part.get("text", "")
            for candidate in data.get("candidates", [])
            if isinstance(candidate, dict)
            for part in candidate.get("content", {}).get("parts", [])
            if isinstance(part, dict)
        ]

    result = "\n".join(part for part in parts if isinstance(part, str)).strip()
    if not result:
        raise AIRequestError("The AI provider returned no text.")
    return result
