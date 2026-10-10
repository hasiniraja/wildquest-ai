"""
Tests for WildQuest AI backend.

Coverage:
  - _strip_markdown_fences / _parse_quest helpers
  - validate_quest: duration bounds, safety note, step count
  - validate_quest: unsafe content in description, steps, things_to_notice,
    screen_free_tip — with varied phrasings for every unsafe category
"""
from __future__ import annotations

import os
import sys

# Make sure the backend package root is on the path when running pytest from
# the repo root or the backend/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from quest_generator import _parse_quest, _strip_markdown_fences
from schemas import Quest, QuestRequest
from validator import validate_quest

# ── Helpers ────────────────────────────────────────────────────────────────────


def make_request(**overrides) -> QuestRequest:
    defaults = {
        "duration_minutes": 20,
        "energy_level": "low",
        "setting": "park",
        "interests": ["plants"],
        "age_group": "adults",
    }
    defaults.update(overrides)
    return QuestRequest(**defaults)


def make_quest(**overrides) -> Quest:
    defaults = {
        "title": "Leaf Detective",
        "description": "Explore the park and observe leaf shapes carefully.",
        "duration_minutes": 20,
        "difficulty": "easy",
        "steps": [
            "Walk slowly to a grassy area.",
            "Look for three different leaf shapes.",
            "Describe each leaf shape in one word.",
        ],
        "things_to_notice": ["Vein patterns on leaves", "How light filters through leaves"],
        "safety_note": "Stay on marked paths and watch for trip hazards.",
        "screen_free_tip": "Leave your phone in your pocket and use your memory.",
    }
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
        quest, _err = _parse_quest(raw)
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


# ═════════════════════════════════════════════════════════════════════════════
# NEW CHECKS (rules 5–8 + 3b)
# ═════════════════════════════════════════════════════════════════════════════


# ── Rule 5: Running / racing ──────────────────────────────────────────────────

class TestRunningRacing:
    """Steps or description must not instruct participants to run or race."""

    def test_race_to_tree_flagged(self):
        quest = make_quest(steps=[
            "Walk to the open field.",
            "Race to the nearest tree as fast as you can.",
            "Walk slowly back.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None, "race-to-tree should be flagged"
        assert "running or racing" in err

    def test_sprint_to_bench_flagged(self):
        quest = make_quest(steps=[
            "Find a wide open path.",
            "Sprint to the bench at the end of the path.",
            "Catch your breath and observe the view.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_race_each_other_flagged(self):
        quest = make_quest(steps=[
            "Stand at the start of the path.",
            "Race each other to the big oak tree.",
            "Sit quietly and listen for bird calls.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_start_running_flagged(self):
        quest = make_quest(steps=[
            "Warm up with a slow walk.",
            "Start running between the two benches.",
            "Cool down and observe your surroundings.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_how_fast_you_can_run_in_description_flagged(self):
        quest = make_quest(description="See how fast you can run around the park loop.")
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_dash_across_field_flagged(self):
        quest = make_quest(steps=[
            "Find a wide grassy area.",
            "Dash across it toward the hedge.",
            "Pause and look back at the path you took.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    # ── Negative tests (must NOT be flagged) ──

    def test_walking_briskly_passes(self):
        quest = make_quest(steps=[
            "Walk briskly along the trail.",
            "Pause every 5 minutes to look around.",
            "Return to your starting point.",
        ])
        assert validate_quest(quest, make_request()) is None

    def test_running_water_in_description_passes(self):
        """'Running water' must not trigger the running check."""
        quest = make_quest(
            description="Listen for the sound of running water in the nearby stream.",
            steps=[
                "Walk to the stream bank.",
                "Sit quietly and identify three sounds.",
                "Draw a mental map of what you heard.",
            ],
        )
        assert validate_quest(quest, make_request()) is None

    def test_move_quickly_no_race_keyword_passes(self):
        quest = make_quest(steps=[
            "Move to the shadiest part of the park.",
            "Look around and note three textures.",
            "Return to the entrance and reflect.",
        ])
        assert validate_quest(quest, make_request()) is None


# ── Rule 6: Equipment not provided by user ────────────────────────────────────

class TestEquipmentNotProvided:
    """Steps must not require equipment the user hasn't brought."""

    def test_binoculars_in_steps_flagged(self):
        quest = make_quest(steps=[
            "Go to the park entrance.",
            "Use binoculars to spot birds perched in distant trees.",
            "Note the colours you observe.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None, "binoculars should be flagged"
        assert "equipment" in err.lower()

    def test_magnifying_glass_in_steps_flagged(self):
        quest = make_quest(steps=[
            "Find a patch of clover.",
            "Use a magnifying glass to examine an individual flower.",
            "Count the petals without touching the plant.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_notebook_in_steps_flagged(self):
        quest = make_quest(steps=[
            "Explore the garden perimeter.",
            "Write in your notebook every colour you spot.",
            "Sit quietly and review your notes.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_bug_net_in_steps_flagged(self):
        quest = make_quest(steps=[
            "Walk through the meadow area.",
            "Use your bug net to observe an insect up close.",
            "Release it immediately after looking.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_pencil_in_steps_flagged(self):
        quest = make_quest(steps=[
            "Find an interesting tree.",
            "Sketch its outline using your pencil.",
            "Shade the bark texture from memory.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_measuring_tape_flagged(self):
        quest = make_quest(steps=[
            "Choose the widest tree you can find.",
            "Use a measuring tape to measure its trunk circumference.",
            "Compare it to the span of your arms.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_field_journal_flagged(self):
        quest = make_quest(steps=[
            "Walk the trail slowly.",
            "Record your observations in your field journal.",
            "Review them when you get home.",
        ])
        err = validate_quest(quest, make_request())
        assert err is not None

    # ── Negative tests (must NOT be flagged) ──

    def test_equipment_mentioned_only_in_tip_passes(self):
        """Equipment in screen_free_tip but NOT in steps should not be flagged."""
        quest = make_quest(
            screen_free_tip="Imagine you had a notebook — what would you sketch?",
        )
        assert validate_quest(quest, make_request()) is None

    def test_binoculars_in_description_only_passes(self):
        """Equipment named in description but not steps is OK (steps-only check)."""
        quest = make_quest(
            description="This quest suits birdwatchers who own binoculars.",
            steps=[
                "Walk to the open field.",
                "Look up and try to spot shapes moving in the sky.",
                "Count how many distinct bird calls you hear.",
            ],
        )
        assert validate_quest(quest, make_request()) is None

    def test_senses_only_quest_passes(self):
        quest = make_quest(steps=[
            "Walk slowly around the garden edge.",
            "Notice any insects moving on the leaves.",
            "Close your eyes and count the different sounds you hear.",
        ])
        assert validate_quest(quest, make_request()) is None


# ── Rule 7: Kids-only — lifting rocks/logs, digging, collecting ───────────────

class TestKidsLiftDigCollect:
    """Lifting rocks, digging, and collecting are banned for kids quests only."""

    # ── Positive tests — kids age group (should be flagged) ──

    def test_lift_rocks_kids_flagged(self):
        quest = make_quest(steps=[
            "Walk to a stony area.",
            "Lift up rocks carefully to see what lives underneath.",
            "Put the rocks back gently.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None, "lifting rocks should be flagged for kids"
        assert "kids" in err.lower() or "lifting" in err.lower()

    def test_look_under_log_kids_flagged(self):
        quest = make_quest(steps=[
            "Find a fallen log on the ground.",
            "Look under the log for insects or fungi.",
            "Observe without disturbing.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None

    def test_flip_stone_kids_flagged(self):
        quest = make_quest(steps=[
            "Explore the rocky path.",
            "Flip a stone to check for creatures underneath.",
            "Replace it carefully.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None

    def test_dig_hole_kids_flagged(self):
        quest = make_quest(steps=[
            "Find a soft patch of soil.",
            "Dig a small hole and see what you find.",
            "Fill it back in.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None

    def test_collect_leaves_take_home_kids_flagged(self):
        quest = make_quest(steps=[
            "Walk through the garden.",
            "Collect interesting leaves to take home.",
            "Arrange them by size on the table.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None

    def test_gather_rocks_kids_flagged(self):
        quest = make_quest(steps=[
            "Walk the gravel path.",
            "Gather five different rocks and compare their weights.",
            "Put them back where you found them.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None

    def test_peek_under_bark_kids_flagged(self):
        quest = make_quest(steps=[
            "Find a tree with loose bark.",
            "Peek under the bark to see what insects live there.",
            "Step back and observe from a distance.",
        ])
        err = validate_quest(quest, make_request(age_group="kids"))
        assert err is not None

    # ── Negative tests — adults (same content must NOT be flagged) ──

    def test_look_under_log_adults_passes(self):
        quest = make_quest(steps=[
            "Find a fallen log on the ground.",
            "Look under the log for insects or fungi.",
            "Observe without disturbing.",
        ])
        assert validate_quest(quest, make_request(age_group="adults")) is None

    def test_lift_rocks_adults_passes(self):
        quest = make_quest(steps=[
            "Walk to a stony area.",
            "Lift up rocks carefully to see what lives underneath.",
            "Replace each rock as you found it.",
        ])
        assert validate_quest(quest, make_request(age_group="adults")) is None

    def test_lift_rocks_teens_passes(self):
        quest = make_quest(steps=[
            "Find a rocky patch.",
            "Lift rocks carefully and note any creatures.",
            "Replace them gently.",
        ])
        assert validate_quest(quest, make_request(age_group="teens")) is None

    # ── Negative tests — kids (safe observation, must NOT be flagged) ──

    def test_observation_only_kids_passes(self):
        quest = make_quest(steps=[
            "Walk slowly to the garden.",
            "Look for insects on leaves without touching them.",
            "Count how many different types you spot.",
        ])
        assert validate_quest(quest, make_request(age_group="kids")) is None

    def test_collecting_memories_kids_passes(self):
        """'Collecting' in a mental/memory sense must not be flagged."""
        quest = make_quest(steps=[
            "Walk the trail slowly.",
            "Collect mental snapshots of three things that surprise you.",
            "Share your favourite memory when you return.",
        ])
        assert validate_quest(quest, make_request(age_group="kids")) is None


# ── Rule 8: Safety-note contradiction ────────────────────────────────────────

class TestSafetyNoteContradiction:
    """Safety note prohibitions must not be contradicted by step instructions."""

    # ── Positive tests (should be flagged) ──

    def test_no_touch_plants_but_steps_pick_leaf(self):
        quest = make_quest(
            safety_note="Do not touch any plants or insects you find.",
            steps=[
                "Walk slowly along the path.",
                "Pick up a fallen leaf and examine its shape.",
                "Count the veins on the leaf.",
            ],
        )
        err = validate_quest(quest, make_request())
        assert err is not None, "picking leaf contradicts safety note"
        assert "contradiction" in err.lower() or "safety_note" in err.lower()

    def test_never_handle_insects_but_steps_pick_up_caterpillar(self):
        quest = make_quest(
            safety_note="Never touch or handle insects you encounter.",
            steps=[
                "Search the garden for insect activity.",
                "Gently pick up the caterpillar to examine its texture.",
                "Return it to the leaf afterwards.",
            ],
        )
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_avoid_collecting_but_steps_gather_stones(self):
        quest = make_quest(
            safety_note="Avoid collecting or removing anything from the park.",
            steps=[
                "Walk the gravel loop.",
                "Gather a handful of interesting stones to compare sizes.",
                "Replace them before leaving.",
            ],
        )
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_refrain_picking_but_steps_pick_flower(self):
        quest = make_quest(
            safety_note="Please refrain from picking flowers or disturbing the plants.",
            steps=[
                "Explore the garden borders.",
                "Pick a small flower to smell its fragrance.",
                "Observe how the petals are arranged.",
            ],
        )
        err = validate_quest(quest, make_request())
        assert err is not None

    def test_dont_disturb_but_steps_disturb_insects(self):
        quest = make_quest(
            safety_note="Don't disturb any insects or small creatures.",
            steps=[
                "Find an ant trail on the ground.",
                "Gently disturb the trail with a stick to watch how they react.",
                "Step back and observe from a distance.",
            ],
        )
        err = validate_quest(quest, make_request())
        assert err is not None

    # ── Negative tests (must NOT be flagged) ──

    def test_no_touch_note_observation_only_steps_passes(self):
        """Safety note prohibits touching but steps are observation-only."""
        quest = make_quest(
            safety_note="Do not touch any plants or insects you find.",
            steps=[
                "Walk slowly along the path.",
                "Observe the leaf shapes from a distance.",
                "Listen for insect sounds in the undergrowth.",
            ],
        )
        assert validate_quest(quest, make_request()) is None

    def test_generic_safety_note_no_prohibition_passes(self):
        """Standard safety note with no touch prohibition never triggers check."""
        quest = make_quest(
            safety_note="Stay on marked paths and watch your step on uneven ground.",
        )
        assert validate_quest(quest, make_request()) is None

    def test_avoid_disturbing_wildlife_non_touch_steps_passes(self):
        quest = make_quest(
            safety_note="Avoid disturbing any wildlife you encounter.",
            steps=[
                "Walk quietly through the meadow.",
                "Watch birds from at least 5 metres away.",
                "Notice which direction they are facing.",
            ],
        )
        assert validate_quest(quest, make_request()) is None


# ── Rule 3b: Minimum 4 steps for quests ≥30 min ──────────────────────────────

class TestMinStepsForLongQuests:
    """Quests of 30+ minutes require at least 4 steps."""

    def test_three_steps_30min_flagged(self):
        quest = make_quest(
            steps=["Walk to the trail head.", "Look around and breathe.", "Walk back."],
            duration_minutes=30,
        )
        err = validate_quest(quest, make_request(duration_minutes=30))
        assert err is not None, "3 steps for 30-min quest should be flagged"
        assert "4" in err

    def test_three_steps_45min_flagged(self):
        quest = make_quest(
            steps=["Walk to the park.", "Observe the surroundings.", "Return home."],
            duration_minutes=45,
        )
        err = validate_quest(quest, make_request(duration_minutes=45))
        assert err is not None

    def test_three_steps_60min_flagged(self):
        quest = make_quest(
            steps=["Head to the trail.", "Sit and listen.", "Walk back slowly."],
            duration_minutes=60,
        )
        err = validate_quest(quest, make_request(duration_minutes=60))
        assert err is not None

    def test_four_steps_30min_passes(self):
        quest = make_quest(
            steps=[
                "Walk to the open area.",
                "Find a comfortable spot to sit.",
                "Count the colours you can see from where you are.",
                "Walk a different route back.",
            ],
            duration_minutes=30,
        )
        assert validate_quest(quest, make_request(duration_minutes=30)) is None

    def test_five_steps_60min_passes(self):
        quest = make_quest(
            steps=[
                "Start at the park entrance.",
                "Walk the perimeter and note five distinct sounds.",
                "Choose a tree and observe it for 2 minutes.",
                "Find the spot with the most shade and breathe slowly.",
                "Return via a different path and compare your observations.",
            ],
            duration_minutes=60,
        )
        assert validate_quest(quest, make_request(duration_minutes=60)) is None

    def test_three_steps_20min_passes(self):
        """3 steps is fine for a quest under 30 minutes."""
        quest = make_quest(
            steps=["Walk to the garden.", "Notice leaf shapes.", "Return to the gate."],
            duration_minutes=20,
        )
        assert validate_quest(quest, make_request(duration_minutes=20)) is None

    def test_three_steps_29min_passes(self):
        """29 minutes is just below threshold — 3 steps still acceptable."""
        quest = make_quest(
            steps=["Start at the entrance.", "Observe plants.", "Walk back."],
            duration_minutes=29,
        )
        assert validate_quest(quest, make_request(duration_minutes=29)) is None
