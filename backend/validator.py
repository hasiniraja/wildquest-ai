"""
Business-level quest validation for WildQuest AI.

Runs AFTER Pydantic schema validation to enforce:
  1. Duration within ±20% of the request
  2. Non-empty safety note
  3. Step count 3–6 (and at least 4 for quests ≥30 min)
  4. No unsafe content across ALL text fields (eating, swimming, climbing, …)
  5. No running or racing instructions
  6. No equipment assumed to be in the user's pocket
  7. No rock/log lifting, digging, or collecting (kids quests only)
  8. No contradiction between the safety note's prohibitions and the steps
"""
from __future__ import annotations

import re

from schemas import Quest, QuestRequest

# ─────────────────────────────────────────────────────────────────────────────
# § A  Broad unsafe-content patterns (scanned across ALL text fields)
# ─────────────────────────────────────────────────────────────────────────────
#
# Each tuple is (human-readable label, compiled regex).
# Word-boundary anchors (\b) prevent partial-word false positives.

_UNSAFE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # ── Eating / tasting plants, fungi, berries ────────────────────────────
    (
        "eating or tasting plants/fungi",
        re.compile(
            r"\b(?:eat|eating|ate|taste|tasting|tasted|nibble|nibbling|chew|chewing|"
            r"consume|consuming|consumed|ingest|ingesting|lick|licking|try)\b"
            r".{0,60}"
            r"\b(?:plant|plants|leaf|leaves|berry|berries|fungi|fungus|mushroom|mushrooms|"
            r"flower|flowers|herb|herbs|root|roots|bark|seed|seeds|nut|nuts|fruit|fruits)\b"
            r"|"
            r"\b(?:plant|plants|leaf|leaves|berry|berries|fungi|fungus|mushroom|mushrooms|"
            r"flower|flowers|herb|herbs|seed|seeds)\b"
            r".{0,40}"
            r"\b(?:edible|safe to eat|can be eaten|are edible|taste good|try one)\b"
            r"|"
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
            r"\b(?:climb|climbing|climbed|scale|scaling|scaled|scramble up|scrambling up)\b"
            r".{0,50}"
            r"\b(?:tree|trees|branch|branches|fence|fences|wall|walls|structure|structures|"
            r"pole|poles|building|buildings|boulder|boulders|rock|rocks|hill|hills|"
            r"rooftop|roof)\b"
            r"|"
            r"\b(?:tree|trees|fence|fences|wall|walls)\b"
            r".{0,30}"
            r"\b(?:climb|climbing|scale|scaling)\b"
            r"|"
            r"\b(?:get|go|climb) up .{0,25}\b(?:tree|trees|fence|fences|wall|walls|structure|structures|rock|rocks|boulder|boulders|hill|roof|rooftop)\b"
            r"|"
            r"\bget up (?:\w+ ){0,4}(?:wall|fence|tree|rock|boulder|structure|rooftop|roof)\b"
            r"|"
            r"\btree[-\s]?climbing\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),

    # ── Approaching or handling wild animals ──────────────────────────────
    (
        "approaching or handling wild animals",
        re.compile(
            r"\b(?:approach|approaching|approached|pet|petting|petted|feed|feeding|fed|"
            r"handle|handling|handled|chase|chasing|chased|corner|cornering|"
            r"catch|catching|caught|grab|grabbing|grabbed|hold|holding|held)\b"
            r".{0,50}"
            r"\b(?:wild|wildlife|stray|animal|animals|bird|birds|snake|snakes|deer|fox|"
            r"foxes|squirrel|squirrels|rabbit|rabbits|raccoon|raccoons|coyote|coyotes|"
            r"insect|insects|bug|bugs|caterpillar|caterpillars|bee|bees|wasp|wasps)\b"
            r"|"
            r"\btouch(?:ing|ed)? (?:a |the )?(?:wild|stray)\b"
            r"|"
            r"\bget(?:ting)? (?:close|near) to (?:a |the )?(?:wild|wildlife|animal|animals)\b"
            r"|"
            r"\bfeed(?:ing|s)? (?:the )?(?:wildlife|birds|ducks|squirrels|deer|animals|insects|bugs)\b"
            r"|"
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
            r"|\bat night\b"
            r"|\bnighttime\b"
            r"|\bnight[-\s]time\b"
            r"|\bafter sunset\b"
            r"|\bonce it.s dark\b"
            r"|\bwhen it.s dark\b"
            r"|\bin the dark\b"
            r"|\bat dusk\b"
            r"|\bdusk\b"
            r"|\bafter the sun (?:goes|sets|has set)\b"
            r"|\bwait until dark\b",
            re.IGNORECASE,
        ),
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# § B  Targeted patterns (scanned against specific fields only)
# ─────────────────────────────────────────────────────────────────────────────

# ── B1. Running / racing instructions (steps + description) ──────────────────
_RUNNING_RE = re.compile(
    # imperative "run/race/sprint to/between/around …"
    r"\b(?:run|race|sprint|dash|jog)\b.{0,40}\b(?:to|between|around|across|back|toward|towards|as fast)\b"
    r"|"
    r"\brace (?:each other|your (?:friend|partner|sibling|classmate|team|group))\b"
    r"|"
    r"\bhow fast (?:you can|can you) (?:run|sprint|dash|race|jog)\b"
    r"|"
    r"\bstart (?:running|racing|sprinting|jogging|dashing)\b"
    r"|"
    r"\bsprint (?:to|between|as|toward|towards|across|around)\b"
    r"|"
    # explicit imperative at start of a step: "Run to …", "Race to …"
    r"(?:^|[.!?]\s+|\n)(?:Run|Race|Sprint|Dash|Jog) (?:to|between|around|as|toward)\b",
    re.IGNORECASE | re.DOTALL,
)

# ── B2. Equipment not provided by user (steps only) ──────────────────────────
# Matches equipment names when they appear in step instructions.
# Mentioning these items implies the user needs to own them.
_EQUIPMENT_RE = re.compile(
    r"\bbinoculars?\b"
    r"|\bmagnifying glass\b"
    r"|\bmagnif(?:ier|ying lens)\b"
    r"|\bhand lens\b"
    r"|\bloupe\b"
    r"|\b(?:bug|butterfly|insect|catching|collecting) net\b"
    r"|\bnotebook\b"
    r"|\bsketchbook\b"
    r"|\bfield (?:journal|guide|notebook)\b"
    r"|\bdrawing (?:pad|book)\b"
    r"|\b(?:your |a |the )?(?:pencil|pen|marker|crayon)\b"    # "use your pencil"
    r"|\bruler\b"
    r"|\bmeasuring tape\b"
    r"|\btape measure\b"
    r"|\bspecimen (?:jar|bag|container)\b"
    r"|\bcollecting (?:jar|bag|box|container)\b"
    r"|\btrowel\b"
    r"|\bgarden (?:trowel|fork|spade)\b",
    re.IGNORECASE,
)

# ── B3. Kids-unsafe: lifting rocks/logs, digging, collecting (kids only) ──────
_KIDS_LIFT_DIG_RE = re.compile(
    # lifting / flipping / turning over ground objects
    r"\b(?:lift|lifting|lifted|flip|flipping|flipped|turn over|turning over|pry up|prying up)\b"
    r".{0,35}"
    r"\b(?:rock|rocks|stone|stones|log|logs|bark|branch|branches|wood)\b"
    r"|"
    r"\b(?:rock|rocks|stone|stones|log|logs)\b"
    r".{0,25}"
    r"\b(?:lift|flip|turn over|pry)\b"
    r"|"
    # look/peek under ground objects
    r"\b(?:look|peek|check|search)\b.{0,20}\b(?:under|beneath|below)\b.{0,20}\b(?:rock|rocks|stone|stones|log|logs|bark)\b"
    r"|"
    # digging
    r"\b(?:dig|digging|dug|dig up|excavate|excavating|burrow|burrowing)\b"
    r"|"
    # collecting and taking items home from nature
    r"\b(?:collect|collecting|collected|gather|gathering|gathered)\b"
    r".{0,50}"
    r"\b(?:rock|rocks|stone|stones|leaf|leaves|flower|flowers|insect|insects|bug|bugs|"
    r"stick|sticks|specimen|specimens|sample|samples|seed|seeds|shell|shells)\b"
    r"|"
    r"\b(?:take home|bring home|keep|pocket|put in (?:your |a )?(?:bag|pocket|jar))\b"
    r".{0,35}"
    r"\b(?:rock|stone|leaf|stick|insect|bug|flower|sample|seed|shell)\b",
    re.IGNORECASE | re.DOTALL,
)

# ── B4. Safety-note contradiction helpers ────────────────────────────────────
# Fire only when the safety note contains a touch/handle prohibition AND
# the steps instruct the very action being prohibited.
_SAFETY_PROHIBIT_RE = re.compile(
    r"\b(?:do\s+not|don'?t|avoid|never|refrain\s+from|please\s+don'?t)\b"
    r".{0,40}"
    r"\b(?:touch|handle|pick(?:ing)?|collect(?:ing)?|disturb(?:ing)?"
    r"|grab(?:bing)?|remove|remov(?:al|ing)|take|gather(?:ing)?)\b",
    re.IGNORECASE | re.DOTALL,
)

_STEP_PROHIBITED_ACTION_RE = re.compile(
    # action verb followed within 60 chars by a nature noun
    r"\b(?:touch|handle|pick\s+up|pick|collect|gather|disturb|grab|remove|take)\b"
    r".{0,60}"
    r"\b(?:plant|plants|leaf|leaves|flower|flowers|insect|insects|bug|bugs|"
    r"caterpillar|caterpillars|butterfly|butterflies|bee|bees|mushroom|fungi|"
    r"rock|rocks|stone|stones|bark|twig|twigs|sample|specimen|ant|trail)\b"
    r"|"
    # pick a/the/some <nature noun> — covers "Pick a small flower"
    r"\bpick\s+(?:a|the|some|one|up)\b.{0,30}"
    r"\b(?:flower|flowers|leaf|leaves|stone|rock|insect|bug|mushroom|berry)\b"
    r"|"
    # gather/disturb + direct noun — covers "Gather a handful of stones"
    r"\b(?:gather|disturb)\b.{0,35}"
    r"\b(?:handful|stones?|rocks?|flowers?|leaves?|insects?|bugs?|trail|ant)\b",
    re.IGNORECASE | re.DOTALL,
)



# ─────────────────────────────────────────────────────────────────────────────
# § C  Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _collect_text(quest: Quest) -> str:
    """Concatenate ALL user-visible text fields for broad safety scanning."""
    return " ".join([
        quest.title,
        quest.description,
        quest.safety_note,
        quest.screen_free_tip,
        *quest.steps,
        *quest.things_to_notice,
    ])


# ─────────────────────────────────────────────────────────────────────────────
# § D  Public API
# ─────────────────────────────────────────────────────────────────────────────


def validate_quest(quest: Quest, request: QuestRequest) -> str | None:
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

    # ── 3a. Step count 3–6 ───────────────────────────────────────────────
    n_steps = len(quest.steps)
    if not (3 <= n_steps <= 6):
        errors.append(f"steps must contain 3–6 items, got {n_steps}")

    # ── 3b. Longer quests need more steps ────────────────────────────────
    #   A 30+ minute quest with only 3 steps is underspecified and likely
    #   to leave participants idle or confused.
    elif request.duration_minutes >= 30 and n_steps < 4:
        errors.append(
            f"steps must contain at least 4 items for a {request.duration_minutes}-minute "
            f"quest, got {n_steps}"
        )

    # ── 4. Broad unsafe content (ALL fields) ─────────────────────────────
    full_text = _collect_text(quest)
    for label, pattern in _UNSAFE_PATTERNS:
        if pattern.search(full_text):
            errors.append(f"Unsafe content detected: {label}")
            break  # one safety rejection is enough; the whole quest must be redone

    # ── 5. Running / racing (description + steps) ────────────────────────
    action_text = quest.description + " " + " ".join(quest.steps)
    if _RUNNING_RE.search(action_text):
        errors.append(
            "Unsafe instruction: running or racing detected — "
            "quests must use walking pace only"
        )

    # ── 6. Equipment not provided by user (steps only) ───────────────────
    steps_text = " ".join(quest.steps)
    if _EQUIPMENT_RE.search(steps_text):
        errors.append(
            "Steps reference equipment the user may not have "
            "(binoculars, magnifying glass, notebook, net, etc.) — "
            "rephrase to use only the naked senses"
        )

    # ── 7. Kids-only: lifting rocks/logs, digging, collecting ────────────
    if request.age_group == "kids":
        kids_action_text = quest.description + " " + steps_text
        if _KIDS_LIFT_DIG_RE.search(kids_action_text):
            errors.append(
                "Unsafe for kids: lifting rocks/logs, digging, or collecting items "
                "detected — these risk injury or disturbing wildlife for young participants"
            )

    # ── 8. Safety-note contradiction ─────────────────────────────────────
    #   If the safety note explicitly prohibits touching/handling, the steps
    #   must not instruct the user to do exactly that.
    if _SAFETY_PROHIBIT_RE.search(quest.safety_note) and _STEP_PROHIBITED_ACTION_RE.search(steps_text):
            errors.append(
                "Contradiction: safety_note prohibits touching/handling/collecting "
                "but steps instruct it"
            )

    return "; ".join(errors) if errors else None
