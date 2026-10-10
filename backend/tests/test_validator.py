"""
Tests for WildQuest AI backend.

Coverage:
  - _strip_markdown_fences / _parse_quest helpers
  - validate_quest: duration bounds, safety note, step count
  - validate_quest: unsafe content in description, steps, things_to_notice,
    screen_free_tip — with varied phrasings for every unsafe category
"""
from __future__ import annotations

import sys
import os

# Make sure the backend package root is on the path when running pytest from
# the repo root or the backend/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from schemas import Quest, QuestRequest
from validator import validate_quest
from quest_generator import _strip_markdown_fences, _parse_quest


# ── Helpers ────────────────────────────────────────────────────────────────────


def make_request(**overrides) -> QuestRequest:
    defaults = dict(
        duration_minutes=20,
        energy_level="low",
        setting="park",
        interests=["plants"],
        age_group="adults",
    )
    defaults.update(overrides)
    return QuestRequest(**defaults)


def make_quest(**overrides) -> Quest:
    defaults = dict(
        title="Leaf Detective",
        description="Explore the park and observe leaf shapes carefully.",
        duration_minutes=20,
        difficulty="easy",
        steps=[
            "Walk slowly to a grassy area.",
            "Look for three different leaf shapes.",
            "Describe each leaf shape in one word.",
        ],
        things_to_notice=["Vein patterns on leaves", "How light filters through leaves"],
        safety_note="Stay on marked paths and watch for trip hazards.",
        screen_free_tip="Leave your phone in your pocket and use your memory.",
    )
    defaults.update(overrides)
    return Quest(**defaults)


# ── JSON parsing helpers ───────────────────────────────────────────────────────


class TestStripMarkdownFences:
    def test_no_fences_unchanged(self):
        raw = '{"title": "Hello"}'
        assert _strip_markdown_fences(raw) == raw

    def test_json_fence_stripped(self):
        raw = '```json\n{"title": "Hello"}\n```'
        result = _strip_markdown_fences(raw)
        assert result == '{"title": "Hello"}'

    def test_plain_fence_stripped(self):
        raw = '```\n{"key": "value"}\n```'
        result = _strip_markdown_fences(raw)
        assert result == '{"key": "value"}'

    def test_fence_with_extra_whitespace(self):
        raw = '  ```json  \n{"a":1}\n```  '
        result = _strip_markdown_fences(raw)
        assert result == '{"a":1}'


class TestParseQuest:
    def test_valid_quest_parsed(self):
        data = make_quest()
        raw = data.model_dump_json()
        quest, err = _parse_quest(raw)
        assert quest is not None
        assert err == ""

    def test_malformed_json_returns_error(self):
        raw = '{"title": "Oops", broken json here'
        quest, err = _parse_quest(raw)
        assert quest is None
        assert "JSON parse error" in err

    def test_completely_non_json_returns_error(self):
        raw = "Sure! Here is your quest for today. Go for a walk!"
        quest, err = _parse_quest(raw)
        assert quest is None
        assert "JSON parse error" in err

    def test_json_in_markdown_fence_parsed(self):
        """Model wrapped the JSON in ```json ... ``` — must still parse correctly."""
        inner = make_quest().model_dump_json()
        raw = f"```json\n{inner}\n```"
        quest, err = _parse_quest(raw)
        assert quest is not None, f"Expected success but got error: {err}"

    def test_json_in_plain_fence_parsed(self):
        inner = make_quest().model_dump_json()
        raw = f"```\n{inner}\n```"
        quest, err = _parse_quest(raw)
        assert quest is not None

    def test_missing_required_field(self):
        """JSON that is syntactically valid but missing a required field."""
        raw = '{"title": "No other fields here"}'
        quest, err = _parse_quest(raw)
        assert quest is None
        assert "Schema validation error" in err

    def test_wrong_difficulty_value(self):
        data = make_quest().model_dump()
        data["difficulty"] = "extreme"
        import json
        raw = json.dumps(data)
        quest, err = _parse_quest(raw)
        assert quest is None
        assert "Schema validation error" in err


# ── Validate quest: structural rules ──────────────────────────────────────────


class TestDurationValidation:
    def test_exact_duration_passes(self):
        quest = make_quest(duration_minutes=20)
        assert validate_quest(quest, make_request(duration_minutes=20)) is None

    def test_duration_at_upper_boundary_passes(self):
        # 20 * 1.2 = 24
        quest = make_quest(duration_minutes=24)
        assert validate_quest(quest, make_request(duration_minutes=20)) is None

    def test_duration_at_lower_boundary_passes(self):
        # 20 * 0.8 = 16
        quest = make_quest(duration_minutes=16)
        assert validate_quest(quest, make_request(duration_minutes=20)) is None

    def test_duration_too_long_fails(self):
        # 25 > 24 (upper bound for 20 min request)
        quest = make_quest(duration_minutes=25)
        err = validate_quest(quest, make_request(duration_minutes=20))
        assert err is not None
        assert "duration_minutes" in err

    def test_duration_too_short_fails(self):
        # 15 < 16 (lower bound for 20 min request)
        quest = make_quest(duration_minutes=15)
        err = validate_quest(quest, make_request(duration_minutes=20))
        assert err is not None
        assert "duration_minutes" in err

    def test_duration_way_off_fails(self):
        quest = make_quest(duration_minutes=60)
        err = validate_quest(quest, make_request(duration_minutes=20))
        assert err is not None


class TestSafetyNoteValidation:
    def test_empty_safety_note_fails(self):
        # Use model_construct to bypass Pydantic schema so we test validate_quest logic
        quest = Quest.model_construct(
            **{**make_quest().model_dump(), "safety_note": ""}
        )
        err = validate_quest(quest, make_request())
        assert err is not None
        assert "safety_note" in err

    def test_whitespace_only_safety_note_fails(self):
        quest = Quest.model_construct(
            **{**make_quest().model_dump(), "safety_note": "   \t  "}
        )
        err = validate_quest(quest, make_request())
        assert err is not None
        assert "safety_note" in err

    def test_valid_safety_note_passes(self):
        quest = make_quest(safety_note="Watch your step on uneven ground.")
        assert validate_quest(quest, make_request()) is None


class TestStepCountValidation:
    def test_three_steps_passes(self):
        quest = make_quest(steps=["Step A", "Step B", "Step C"])
        assert validate_quest(quest, make_request()) is None

    def test_six_steps_passes(self):
        quest = make_quest(steps=[f"Step {i}" for i in range(6)])
        assert validate_quest(quest, make_request()) is None

    def test_two_steps_fails(self):
        # Use model_construct to bypass Pydantic so we test validate_quest logic
        quest = Quest.model_construct(
            **{**make_quest().model_dump(), "steps": ["Step A", "Step B"]}
        )
        err = validate_quest(quest, make_request())
        assert err is not None
        assert "steps" in err

    def test_seven_steps_fails(self):
        quest = Quest.model_construct(
            **{**make_quest().model_dump(), "steps": [f"Step {i}" for i in range(7)]}
        )
        err = validate_quest(quest, make_request())
        assert err is not None
        assert "steps" in err

    def test_one_step_fails(self):
        quest = Quest.model_construct(
            **{**make_quest().model_dump(), "steps": ["Only one step"]}
        )
        err = validate_quest(quest, make_request())
        assert err is not None


# ── Validate quest: unsafe content ────────────────────────────────────────────


class TestUnsafeEatingPlants:
    """Varied phrasings for eating/tasting plants or fungi."""

    def _assert_unsafe(self, **overrides):
        quest = make_quest(**overrides)
        err = validate_quest(quest, make_request())
        assert err is not None, f"Expected unsafe rejection but got None for: {overrides}"
        assert "eating" in err or "unsafe" in err.lower() or "Unsafe" in err

    def test_eat_berries_in_description(self):
        self._assert_unsafe(description="You can eat the berries you find along the path.")

    def test_taste_leaves_in_description(self):
        self._assert_unsafe(description="Taste the fresh leaves to identify different plants.")

    def test_nibble_mushroom_in_steps(self):
        self._assert_unsafe(steps=[
            "Walk slowly.", "Find a mushroom.", "Nibble on the mushroom to see if it's bitter.",
        ])

    def test_edible_fungi_in_things_to_notice(self):
        self._assert_unsafe(things_to_notice=[
            "Notice which fungi are edible", "Colour of flowers"
        ])

    def test_consume_plant_in_screen_free_tip(self):
        self._assert_unsafe(
            screen_free_tip="Try consuming a leaf from the plant to really connect with nature."
        )

    def test_pick_and_eat_phrasing(self):
        self._assert_unsafe(description="Pick and eat any berries you spot along the way.")

    def test_try_a_berry_phrasing(self):
        self._assert_unsafe(description="If you see any ripe ones, try a berry to test your ID skills.")

    def test_licking_bark_in_steps(self):
        self._assert_unsafe(steps=[
            "Find a tree.", "Lick the bark to detect different flavours.", "Move on.",
        ])


class TestUnsafeSwimming:
    """Varied phrasings for swimming or wading."""

    def _assert_unsafe(self, **overrides):
        quest = make_quest(**overrides)
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_swim_in_pond(self):
        self._assert_unsafe(description="Feel free to swim in the park pond to cool down.")

    def test_wading_in_stream(self):
        self._assert_unsafe(description="Wade through the shallow stream at the trail crossing.")

    def test_go_for_a_swim(self):
        self._assert_unsafe(description="After the quest go for a swim in the nearby river.")

    def test_jump_into_water_in_steps(self):
        self._assert_unsafe(steps=[
            "Walk to the lake edge.", "Jump into the water to refresh yourself.", "Dry off and walk back.",
        ])

    def test_dip_feet_in_stream(self):
        self._assert_unsafe(
            screen_free_tip="Dip your feet in the stream at the halfway point to relax."
        )

    def test_splash_in_pond_in_things_to_notice(self):
        self._assert_unsafe(things_to_notice=[
            "Notice how splashing in the pond disturbs the surface", "Cloud shapes"
        ])


class TestUnsafeClimbing:
    """Varied phrasings for climbing trees or structures."""

    def _assert_unsafe(self, **overrides):
        quest = make_quest(**overrides)
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_climb_a_tree(self):
        self._assert_unsafe(description="Climb a tree to get a bird's-eye view of the park.")

    def test_scale_the_fence(self):
        self._assert_unsafe(description="Scale the fence at the park boundary for a better vantage point.")

    def test_climbing_trees_in_steps(self):
        self._assert_unsafe(steps=[
            "Head to the oak tree.", "Try climbing the tree to see higher up.", "Describe what you see.",
        ])

    def test_scramble_up_rocks(self):
        self._assert_unsafe(description="Scramble up the rocks at the trail bend for a panoramic view.")

    def test_tree_climbing_hyphenated(self):
        self._assert_unsafe(
            screen_free_tip="Tree-climbing is a great way to gain perspective without a screen."
        )

    def test_get_up_a_wall(self):
        self._assert_unsafe(description="Get up the old stone wall to see the field on the other side.")


class TestUnsafeApproachingAnimals:
    """Varied phrasings for approaching or handling wild animals."""

    def _assert_unsafe(self, **overrides):
        quest = make_quest(**overrides)
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_approach_the_deer(self):
        self._assert_unsafe(description="Carefully approach the deer grazing in the meadow.")

    def test_pet_a_wild_bird(self):
        self._assert_unsafe(description="If a bird lands near you, try to pet a wild bird gently.")

    def test_feeding_wildlife_in_steps(self):
        self._assert_unsafe(steps=[
            "Find the duck pond.", "Start feeding the birds your snack.", "Observe their behaviour.",
        ])

    def test_feed_squirrels_in_things_to_notice(self):
        self._assert_unsafe(things_to_notice=[
            "How squirrels react when you feed them", "The colour of leaves"
        ])

    def test_chase_insects(self):
        self._assert_unsafe(description="Chase insects around the meadow and see how many you can catch.")

    def test_get_close_to_animals(self):
        self._assert_unsafe(
            screen_free_tip="Get close to the wild animals to really appreciate their behaviour."
        )

    def test_touch_a_wild_rabbit(self):
        self._assert_unsafe(description="If you see a rabbit, touch the wild animal to feel its fur.")

    def test_handle_insects_in_steps(self):
        self._assert_unsafe(steps=[
            "Find a caterpillar.", "Handle the insect gently so you can examine it.", "Return it.",
        ])


class TestUnsafePrivateProperty:
    """Varied phrasings for entering private property or trespassing."""

    def _assert_unsafe(self, **overrides):
        quest = make_quest(**overrides)
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_private_property_literal(self):
        self._assert_unsafe(description="Cut through the private property for a shortcut.")

    def test_trespassing(self):
        self._assert_unsafe(description="Don't worry about trespassing — it's worth it for the view.")

    def test_enter_neighbors_garden(self):
        self._assert_unsafe(description="Enter your neighbour's garden to see the flowers up close.")

    def test_sneak_into_private_in_steps(self):
        self._assert_unsafe(steps=[
            "Walk to the end of the street.", "Sneak into the private yard behind the hedge.", "Observe.",
        ])

    def test_someones_yard_in_things_to_notice(self):
        self._assert_unsafe(things_to_notice=[
            "Plants in someone's garden that you can inspect", "Colours of doors"
        ])

    def test_go_into_strangers_land(self):
        self._assert_unsafe(
            screen_free_tip="Go into the stranger's land at the edge of the trail for a quieter experience."
        )


class TestUnsafeAfterDark:
    """Varied phrasings for going out after dark or at night."""

    def _assert_unsafe(self, **overrides):
        quest = make_quest(**overrides)
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_after_dark(self):
        self._assert_unsafe(description="Best experienced after dark when the park is quiet.")

    def test_at_night(self):
        self._assert_unsafe(description="Try repeating this quest at night for a different perspective.")

    def test_nighttime_in_steps(self):
        self._assert_unsafe(steps=[
            "Wait until nighttime.", "Head to the park.", "Listen for owls.",
        ])

    def test_at_dusk(self):
        self._assert_unsafe(description="Head out at dusk when the birds are most active.")

    def test_dusk_in_things_to_notice(self):
        self._assert_unsafe(things_to_notice=[
            "Sounds that emerge at dusk", "Cloud shapes"
        ])

    def test_after_sunset_in_screen_free_tip(self):
        self._assert_unsafe(
            screen_free_tip="The best views happen after sunset — plan to stay out late."
        )

    def test_when_its_dark(self):
        self._assert_unsafe(description="When it's dark outside the stars are easier to see.")

    def test_wait_until_dark(self):
        self._assert_unsafe(description="Wait until dark before starting the sky observation portion.")

    def test_night_hyphen_time(self):
        self._assert_unsafe(
            screen_free_tip="This is best enjoyed as a night-time adventure."
        )


# ── Passing cases ──────────────────────────────────────────────────────────────


class TestValidQuestPasses:
    """Ensure well-formed, safe quests pass all validations."""

    def test_baseline_quest_passes(self):
        quest = make_quest()
        assert validate_quest(quest, make_request()) is None

    def test_quest_with_six_steps_passes(self):
        quest = make_quest(steps=[f"Step number {i}" for i in range(1, 7)])
        assert validate_quest(quest, make_request()) is None

    def test_quest_with_many_things_to_notice_passes(self):
        quest = make_quest(
            things_to_notice=["Colours", "Textures", "Sounds", "Smells in the air", "Shadows"],
        )
        assert validate_quest(quest, make_request()) is None

    def test_observe_insects_without_touching_passes(self):
        """'Observe insects' is safe; only handling/touching/feeding is rejected."""
        quest = make_quest(
            description="Observe insects carefully without disturbing them.",
            steps=[
                "Find a sunny patch of ground.",
                "Watch insects moving through the grass.",
                "Count how many different types you can see.",
            ],
        )
        assert validate_quest(quest, make_request()) is None

    def test_mention_berries_for_visual_id_passes(self):
        """Mentioning berries for visual observation (not eating) should pass."""
        quest = make_quest(
            description="Look for red berries and observe their clusters from a distance.",
            steps=[
                "Walk along the path and look for berry-bearing shrubs.",
                "Count how many clusters you can see.",
                "Sketch the colour and arrangement from memory.",
            ],
        )
        assert validate_quest(quest, make_request()) is None
