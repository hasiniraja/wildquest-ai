"""
WildQuest AI — FastAPI application entry point.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quest_generator import OLLAMA_BASE_URL, generate_quest
from schemas import QuestRequest, QuestResponse

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="WildQuest AI",
    description="Generates personalized outdoor quests using a local Gemma model via Ollama.",
    version="0.1.0",
)

# ── CORS — allow the Vite dev server ──────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",  # fallback Vite port
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.post("/api/quest", response_model=QuestResponse)
async def create_quest(request: QuestRequest) -> QuestResponse:
    """
    Generate a personalized outdoor quest.

    - Calls the local Gemma model via Ollama.
    - Validates the output with Pydantic + business rules.
    - Retries up to 2 times on failure, feeding the error back to the model.
    - Falls back to a pre-written seed quest if all retries fail.
    - Returns metadata: model, latency_ms, attempts, source.
    """
    return await generate_quest(request)


@app.get("/api/health")
async def health() -> dict:
    """
    Check whether Ollama is reachable.

    Returns {"status": "ok"} when healthy, {"status": "degraded"} otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"status": "ok", "ollama": "reachable", "available_models": models}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "ollama": "unreachable", "error": str(exc)}
