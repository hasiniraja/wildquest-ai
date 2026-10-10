"""
Pydantic models for WildQuest AI.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_INTERESTS: frozenset[str] = frozenset(
    {"birds", "plants", "sounds", "textures", "colors", "insects", "sky"}
)


# ── Request / Response models ─────────────────────────────────────────────────


class QuestRequest(BaseModel):
    """Input from the user describing their quest preferences."""

    duration_minutes: int = Field(ge=10, le=60, description="Desired quest length in minutes (10–60)")
    energy_level: Literal["low", "medium", "high"]
    setting: Literal["park", "garden", "street", "trail", "backyard"]
    interests: list[str] = Field(
        min_length=1,
        max_length=3,
        description="1–3 interests from the allowed set",
    )
    age_group: Literal["kids", "teens", "adults"]

    @field_validator("interests")
    @classmethod
    def _check_interests(cls, v: list[str]) -> list[str]:
        invalid = [i for i in v if i not in VALID_INTERESTS]
        if invalid:
            raise ValueError(
                f"Invalid interests: {invalid}. "
                f"Choose from: {sorted(VALID_INTERESTS)}"
            )
        return v


class Quest(BaseModel):
    """A generated outdoor quest, validated to schema before returning to the client."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    duration_minutes: int = Field(ge=1)
    difficulty: Literal["easy", "medium"]
    steps: list[str] = Field(min_length=1)  # business rule: 3–6 enforced in validator.py
    things_to_notice: list[str] = Field(min_length=1)  # business rule: 2–5 enforced in validator.py
    safety_note: str  # business rule: non-empty enforced in validator.py
    screen_free_tip: str = Field(min_length=1)


class QuestResponse(BaseModel):
    """Full API response, including the quest and metadata."""

    quest: Quest
    source: Literal["gemma", "fallback"]
    model: str
    latency_ms: int
    attempts: int
