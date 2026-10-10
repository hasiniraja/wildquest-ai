"""
Quest generation pipeline: builds prompt → calls Ollama → validates → retries → falls back.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from pathlib import Path

import httpx

from prompts import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt
from schemas import Quest, QuestRequest, QuestResponse
from validator import validate_quest

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:4b")
MAX_ATTEMPTS = 3          # 1 initial + 2 retries
OLLAMA_TIMEOUT_S = 120.0  # generous for slower machines

_SEED_PATH = Path(__file__).parent / "seed_quests.json"

# ── Module-level cache for seed quests ────────────────────────────────────────

_seed_quests: list[dict] | None = None


def _load_seed_quests() -> list[dict]:
    global _seed_quests
    if _seed_quests is None:
        with open(_SEED_PATH, encoding="utf-8") as fh:
            _seed_quests = json.load(fh)
    return _seed_quests


# ── JSON helpers ───────────────────────────────────────────────────────────────


def _strip_markdown_fences(text: str) -> str:
    """
    Strip leading/trailing ``` or ```json code fences that the model sometimes
    emits even when told not to.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text)
    return text.strip()


def _parse_quest(raw: str) -> tuple[Quest | None, str]:
    """
    Attempt to strip fences, parse JSON, and validate against the Quest schema.

    Returns:
        (Quest, "")          — success
        (None, error_msg)   — failure with reason
    """
    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"

    try:
        quest = Quest.model_validate(data)
        return quest, ""
    except Exception as exc:  # noqa: BLE001
        return None, f"Schema validation error: {exc}"


# ── Main generator ─────────────────────────────────────────────────────────────


async def generate_quest(request: QuestRequest) -> QuestResponse:
    """
    Call Ollama, validate the result, retry up to MAX_ATTEMPTS times, then
    fall back to a random seed quest if all attempts fail.

    Logs only setting, duration and age_group — never interests or other fields
    that could be personally identifying.
    """
    start_ms = time.monotonic() * 1000

    # Safe fields only in logs
    logger.info(
        "Quest request received — setting=%s duration=%d age_group=%s",
        request.setting,
        request.duration_minutes,
        request.age_group,
    )

    last_error = "no attempts made"
    attempts = 0

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_S) as client:
        for attempt in range(MAX_ATTEMPTS):
            attempts = attempt + 1

            user_msg = (
                build_user_prompt(request)
                if attempt == 0
                else build_retry_prompt(request, last_error)
            )

            # ── Call Ollama ───────────────────────────────────────────────
            try:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": MODEL_NAME,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                raw: str = resp.json()["message"]["content"]
            except httpx.HTTPError as exc:
                last_error = f"Ollama HTTP error: {exc}"
                logger.warning("Attempt %d — Ollama unreachable: %s", attempts, last_error)
                continue

            # ── Parse & schema-validate ───────────────────────────────────
            quest, parse_error = _parse_quest(raw)
            if quest is None:
                last_error = parse_error
                logger.warning("Attempt %d — parse failed: %s", attempts, last_error)
                continue

            # ── Business rules ────────────────────────────────────────────
            val_error = validate_quest(quest, request)
            if val_error:
                last_error = val_error
                logger.warning("Attempt %d — validation failed: %s", attempts, last_error)
                continue

            # ── Success ───────────────────────────────────────────────────
            latency_ms = int(time.monotonic() * 1000 - start_ms)
            logger.info("Quest generated — attempts=%d latency_ms=%d", attempts, latency_ms)
            return QuestResponse(
                quest=quest,
                source="gemma",
                model=MODEL_NAME,
                latency_ms=latency_ms,
                attempts=attempts,
            )

    # ── Fallback ──────────────────────────────────────────────────────────────
    logger.warning(
        "All %d attempts failed (last error: %s). Returning seed quest.", MAX_ATTEMPTS, last_error
    )
    seed_data = random.choice(_load_seed_quests())
    seed_quest = Quest.model_validate(seed_data)
    latency_ms = int(time.monotonic() * 1000 - start_ms)

    return QuestResponse(
        quest=seed_quest,
        source="fallback",
        model=MODEL_NAME,
        latency_ms=latency_ms,
        attempts=attempts,
    )
