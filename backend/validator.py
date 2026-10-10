"""
Business-level quest validation for WildQuest AI.

Runs AFTER Pydantic schema validation to enforce:
  - Duration within ±20% of the request
  - Non-empty safety note
  - 3–6 steps
  - No unsafe content across ALL text fields
"""
from __future__ import annotations

import re
from typing import Optional

from schemas import Quest, QuestRequest

# ── Unsafe content patterns ───────────────────────────────────────────────────
#
# Each tuple is (human-readable label, compiled regex).
# Patterns are checked against the concatenation of ALL text fields so a model
# cannot hide unsafe content in steps or things_to_notice.
# Word-boundary anchors (\b) prevent partial-word false positives.

_UNSAFE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # ── Eating / tasting plants, fungi, berries ────────────────────────────
    (
        "eating or tasting plants/fungi",
        re.compile(
            # action verb near plant noun
            r"\b(?:eat|eating|ate|taste|tasting|tasted|nibble|nibbling|chew|chewing|"
            r"consume|consuming|consumed|ingest|ingesting|lick|licking|try)\b"
            r".{0,60}"
            r"\b(?:plant|plants|leaf|leaves|berry|berries|fungi|fungus|mushroom|mushrooms|"
            r"flower|flowers|herb|herbs|root|roots|bark|seed|seeds|nut|nuts|fruit|fruits)\b"
            r"|"
            # plant noun marked edible or safe to eat
            r"\b(?:plant|plants|leaf|leaves|berry|berries|fungi|fungus|mushroom|mushrooms|"
            r"flower|flowers|herb|herbs|seed|seeds)\b"
            r".{0,40}"
            r"\b(?:edible|safe to eat|can be eaten|are edible|taste good|try one)\b"
            r"|"
            # direct phrasing
            r"\b(?:pick and (?:eat|taste)|forage and eat|gather and eat)\b"
            r"|"
            r"\b(?:taste|eat|sample) (?:a |the |some )?(?:berry|berries|leaf|leaves|"
            r"mushroom|mushrooms|plant|flower|flowers)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # ── Swimming / wading / entering water ────────────────────────────────
    (
        "swimming or wading in water",
        re.compile(
            r"\b(?:swim|swimming|swam|wade|wading|wades|waded)\b"
            r"|"
            r"\bgo(?:ing)? for a swim\b"
            r"|"
            r"\bjump(?:ing)? (?:in(?:to)?|off) (?:the )?(?:water|pond|lake|river|stream|creek|pool)\b"
            r"|"
            r"\b(?:dip|dipping|submerge|submerging) (?:your(?:self)?|yourself|"
            r"(?:your )?(?:feet|toes|hands|body|legs)) (?:in(?:to)? )?(?:the )?(?:water|stream|"
            r"pond|lake|river|creek)\b"
            r"|"
            r"\bsplash(?:ing)? (?:around |in )?(?:the )?(?:water|stream|pond|lake|river)\b",
            re.IGNORECASE,
        ),
    ),

    # ── Climbing trees or structures ──────────────────────────────────────
    (
        "climbing trees or structures",
        re.compile(
            # climb/scale near a climbable object
            r"\b(?:climb|climbing|climbed|scale|scaling|scaled|scramble up|scrambling up)\b"
            r".{0,50}"
            r"\b(?:tree|trees|branch|branches|fence|fences|wall|walls|structure|structures|"
            r"pole|poles|building|buildings|boulder|boulders|rock|rocks|hill|hills|"
            r"rooftop|roof)\b"
            r"|"
            # object near climb verb
            r"\b(?:tree|trees|fence|fences|wall|walls)\b"
            r".{0,30}"
            r"\b(?:climb|climbing|scale|scaling)\b"
            r"|"
            # direct phrasing (allow up to 25 chars of adjectives between verb and noun)
            r"\b(?:get|go|climb) up .{0,25}\b(?:tree|trees|fence|fences|wall|walls|structure|structures|rock|rocks|boulder|boulders|hill|roof|rooftop)\b"
            r"|"
            r"\btree[-\s]?climbing\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # ── Approaching or handling wild animals ──────────────────────────────
    (
        "approaching or handling wild animals",
        re.compile(
            # action verb near animal
            r"\b(?:approach|approaching|approached|pet|petting|petted|feed|feeding|fed|"
            r"handle|handling|handled|chase|chasing|chased|corner|cornering|"
            r"catch|catching|caught|grab|grabbing|grabbed|hold|holding|held)\b"
            r".{0,50}"
            r"\b(?:wild|wildlife|stray|animal|animals|bird|birds|snake|snakes|deer|fox|"
            r"foxes|squirrel|squirrels|rabbit|rabbits|raccoon|raccoons|coyote|coyotes|"
            r"insect|insects|bug|bugs|caterpillar|caterpillars|bee|bees|wasp|wasps)\b"
            r"|"
            # touch wild / get close to wild
            r"\btouch(?:ing|ed)? (?:a |the )?(?:wild|stray)\b"
            r"|"
            r"\bget(?:ting)? (?:close|near) to (?:a |the )?(?:wild|wildlife|animal|animals)\b"
            r"|"
            # feeding wildlife (direct or indirect word order)
            r"\bfeed(?:ing|s)? (?:the )?(?:wildlife|birds|ducks|squirrels|deer|animals|insects|bugs)\b"
            r"|"
            # indirect: "when you feed them" / "react when you feed" near animal nouns
            r"\b(?:squirrel|squirrels|deer|duck|ducks|bird|birds|rabbit|rabbits|raccoon|raccoons)\b.{0,80}\bfeed(?:ing|s|ed)?\b"
            r"|"
            r"\bfeed(?:ing|s|ed)?.{0,60}\b(?:squirrel|squirrels|deer|duck|ducks|rabbit|rabbits|raccoon|raccoons)\b"
            r"|"
            r"\bwhen you feed (?:them|it|the animals|the birds|the squirrels|the deer|the ducks|the rabbits)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # ── Entering private property ──────────────────────────────────────────
    (
        "entering private property or trespassing",
        re.compile(
            r"\bprivate property\b"
            r"|"
            r"\btrespass(?:ing|ed)?\b"
            r"|"
            r"\b(?:enter|entering|go into|going into|sneak into|sneaking into|"
            r"break into|breaking into|cross into|crossing into)\b"
            r".{0,50}"
            r"\b(?:private|property|neighbor|neighbour|someone.s|another.s|"
            r"stranger.s|restricted)\b"
            r"|"
            r"\b(?:someone|neighbor|neighbour|stranger).s (?:yard|garden|property|land|"
            r"backyard|lawn)\b"
            r"|"
            r"\bno[- ]?trespassing\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # ── After dark / night-time ────────────────────────────────────────────
    (
        "going out after dark or at night",
        re.compile(
            r"\bafter dark\b"
            r"|"
            r"\bat night\b"
            r"|"
            r"\bnighttime\b"
            r"|"
            r"\bnight[-\s]time\b"
            r"|"
            r"\bafter sunset\b"
            r"|"
            r"\bonce it.s dark\b"
            r"|"
            r"\bwhen it.s dark\b"
            r"|"
            r"\bin the dark\b"
            r"|"
            r"\bat dusk\b"
            r"|"
            r"\bdusk\b"
            r"|"
            r"\bafter the sun (?:goes|sets|has set)\b"
            r"|"
            r"\bwait until dark\b",
            re.IGNORECASE,
        ),
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _collect_text(quest: Quest) -> str:
    """Concatenate all user-visible text fields for safety scanning."""
    parts: list[str] = [
        quest.title,
        quest.description,
        quest.safety_note,
        quest.screen_free_tip,
        *quest.steps,
        *quest.things_to_notice,
    ]
    return " ".join(parts)


# ── Public API ────────────────────────────────────────────────────────────────


def validate_quest(quest: Quest, request: QuestRequest) -> Optional[str]:
    """
    Business-level validation beyond Pydantic schema checks.

    Returns:
        None  — quest is valid and safe
        str   — semicolon-separated human-readable error messages
    """
    errors: list[str] = []

    # ── 1. Duration within ±20% ──────────────────────────────────────────
    allowed_min = round(request.duration_minutes * 0.8)
    allowed_max = round(request.duration_minutes * 1.2)
    if not (allowed_min <= quest.duration_minutes <= allowed_max):
        errors.append(
            f"duration_minutes {quest.duration_minutes} is outside ±20% of requested "
            f"{request.duration_minutes} (allowed range: {allowed_min}–{allowed_max})"
        )

    # ── 2. Safety note must be non-empty / non-whitespace ────────────────
    if not quest.safety_note.strip():
        errors.append("safety_note must not be empty or contain only whitespace")

    # ── 3. Step count 3–6 ────────────────────────────────────────────────
    n_steps = len(quest.steps)
    if not (3 <= n_steps <= 6):
        errors.append(f"steps must contain 3–6 items, got {n_steps}")

    # ── 4. Unsafe content check across ALL text fields ───────────────────
    full_text = _collect_text(quest)
    for label, pattern in _UNSAFE_PATTERNS:
        if pattern.search(full_text):
            errors.append(f"Unsafe content detected: {label}")
            break  # one safety rejection is enough; model must redo the whole quest

    return "; ".join(errors) if errors else None
