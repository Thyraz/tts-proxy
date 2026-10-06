"""Behavioral checks for entity-conditioned replacement and insertion."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from custom_components.tts_proxy.config import form_defaults, serializable_config
from custom_components.tts_proxy.const import (
    CONF_OUTPUT_LANGUAGE,
    CONF_REPLACEMENT_RULES,
    CONF_TARGET_TTS_ENTITY,
    RULE_CONDITION_ENTITY,
    RULE_CONDITION_MAX_AGE,
    RULE_CONDITION_STATE,
    RULE_MODE,
    RULE_MODE_INSERT,
    RULE_PLACEMENTS,
    RULE_REPLACE,
)
from custom_components.tts_proxy.date_normalizer import DateNormalizer
from custom_components.tts_proxy.markdown_normalizer import MarkdownCleanupNormalizer
from custom_components.tts_proxy.normalizer import (
    normalize_stream,
    normalize_text,
    normalize_text_from_raw_config,
    parse_rules,
)
from custom_components.tts_proxy.rules import (
    EntityStateCondition,
    EntityStateReport,
    RuleMode,
    RuleValidationError,
    TextProcessingRule,
    condition_snapshot,
    rules_from_snapshot,
)
from custom_components.tts_proxy.rules import (
    InsertionPlacement as Placement,
)
from custom_components.tts_proxy.text_cleanup_normalizer import TextCleanupNormalizer
from custom_components.tts_proxy.text_insertion import TextInsertionProcessor


def insertion(text="[whisper] ", placements=(Placement.SENTENCE_START,), **kwargs):
    return TextProcessingRule(
        replace=text, mode=RuleMode.INSERT, placements=placements, **kwargs
    )


class TextProcessingTests(unittest.TestCase):
    def test_sentence_punctuation_quotes_and_simple_abbreviations(self):
        self.assertEqual(
            normalize_text(
                'Hello! Ready? He said "Yes." Next. Dr. Smith', [insertion()]
            ),
            '[whisper] Hello! [whisper] Ready? [whisper] He said "Yes." '
            "[whisper] Next. [whisper] Dr. [whisper] Smith",
        )

    def test_overlapping_placements_skip_blank_lines_and_preserve_spaces(self):
        rule = insertion(placements=tuple(Placement))
        self.assertEqual(
            normalize_text("  Hello.\n\n \t\r\n  Good night.\rAgain\r\nDone.", [rule]),
            "  [whisper] Hello.\n\n \t\r\n  [whisper] Good night.\r"
            "[whisper] Again\r\n[whisper] Done.",
        )
        self.assertEqual(normalize_text(" \n\t\r\n", [rule]), " \n\t\r\n")
        self.assertEqual(normalize_text("", [rule]), "")

    def test_line_and_sentence_scopes_are_distinct(self):
        text = "First. Second\nThird"
        self.assertEqual(
            normalize_text(text, [insertion(placements=(Placement.LINE_START,))]),
            "[whisper] First. Second\n[whisper] Third",
        )
        self.assertEqual(
            normalize_text(text, [insertion()]),
            "[whisper] First. [whisper] Second\nThird",
        )
        self.assertEqual(
            normalize_text(text, [insertion(placements=(Placement.MESSAGE_START,))]),
            "[whisper] First. Second\nThird",
        )

    def test_protected_tags_are_not_new_starts_or_punctuation(self):
        self.assertEqual(
            normalize_text(
                '<speak>[other. ?\n!] Hello <break time="1.0s"/> world. Next.</speak>',
                [insertion()],
            ),
            '<speak>[other. ?\n!] [whisper] Hello <break time="1.0s"/> world. '
            "[whisper] Next.</speak>",
        )
        self.assertEqual(
            normalize_text("<speak>[whisper]</speak>", [insertion()]),
            "<speak>[whisper]</speak>",
        )

    def test_exact_existing_tag_among_leading_tags_is_not_duplicated(self):
        self.assertEqual(
            normalize_text(
                "[whisper] [another_extremely_long_tag] Hello. [whisper] Next.",
                [insertion()],
            ),
            "[whisper] [another_extremely_long_tag] Hello. [whisper] Next.",
        )
        self.assertEqual(
            normalize_text("[whisper]Hello.", [insertion()]),
            "[whisper][whisper] Hello.",
        )  # Different literal spacing.

    def test_exact_ordinary_prefix_and_distinct_case(self):
        rule = insertion("Attention: ")
        self.assertEqual(
            normalize_text("Attention: Hello. Bye.", [rule]),
            "Attention: Hello. Attention: Bye.",
        )
        self.assertEqual(
            normalize_text("attention: Hello.", [rule]), "Attention: attention: Hello."
        )

    def test_prefixes_are_verbatim_and_do_not_create_recursive_positions(self):
        self.assertEqual(
            normalize_text("Hello.", [insertion("Notice. "), insertion("[sleepy] ")]),
            "Notice. [sleepy] Hello.",
        )
        self.assertEqual(
            normalize_text("Hello.", [insertion("  prefix\n")]), "  prefix\nHello."
        )

    def test_all_active_rules_compose_in_list_order(self):
        self.assertEqual(
            normalize_text("Hello.", [insertion(), insertion("[sleepy] ")]),
            "[whisper] [sleepy] Hello.",
        )
        self.assertEqual(
            normalize_text("Hello.", [insertion(), insertion()]), "[whisper] Hello."
        )
        self.assertEqual(normalize_text("Hello.", [insertion(enabled=False)]), "Hello.")

    def test_replacements_precede_markdown_and_insertions_then_cleanup(self):
        rules = [
            insertion(placements=(Placement.LINE_START,)),
            TextProcessingRule("whisper", "CHANGED"),
            TextProcessingRule("First", "One"),
        ]
        self.assertEqual(
            normalize_text(
                "- First\n- Second",
                rules,
                markdown_normalizer=MarkdownCleanupNormalizer(enabled=True),
                text_cleanup_normalizer=TextCleanupNormalizer(replace_line_breaks=True),
            ),
            "[whisper] One [whisper] Second",
        )

    def test_conditions_match_exactly_and_missing_entities_skip_only_their_rules(self):
        rules = [
            insertion(condition=EntityStateCondition("binary_sensor.whisper", "on")),
            insertion(
                "[sleepy] ", condition=EntityStateCondition("sun.sun", "below_horizon")
            ),
        ]
        self.assertEqual(
            normalize_text(
                "Hello.",
                rules,
                entity_states={
                    "binary_sensor.whisper": "on",
                    "sun.sun": "below_horizon",
                },
            ),
            "[whisper] [sleepy] Hello.",
        )
        for state in ("off", "unknown", "unavailable", "ON"):
            self.assertEqual(
                normalize_text(
                    "Hello.", rules, entity_states={"binary_sensor.whisper": state}
                ),
                "Hello.",
            )
        self.assertEqual(normalize_text("Hello.", rules), "Hello.")

    def test_conditioned_replacements_and_explicit_unavailable_match(self):
        rules = [
            TextProcessingRule(
                "Hello",
                "Bye",
                condition=EntityStateCondition("sensor.test", "unavailable"),
            )
        ]
        self.assertEqual(
            normalize_text(
                "Hello", rules, entity_states={"sensor.test": "unavailable"}
            ),
            "Bye",
        )
        self.assertEqual(
            normalize_text("Hello", rules, entity_states={"sensor.test": "unknown"}),
            "Hello",
        )

    def test_snapshot_reads_each_entity_once_and_remains_frozen(self):
        states = {"binary_sensor.whisper": "on"}
        calls = []

        def getter(entity_id):
            calls.append(entity_id)
            return states.get(entity_id)

        condition = EntityStateCondition("binary_sensor.whisper", "on")
        rules = [
            insertion(condition=condition),
            insertion("[sleepy] ", condition=condition),
        ]
        snapshot = condition_snapshot(rules, getter)
        states["binary_sensor.whisper"] = "off"
        self.assertEqual(calls, ["binary_sensor.whisper"])
        self.assertEqual(
            normalize_text("Hello.", rules_from_snapshot(rules, snapshot)),
            "[whisper] [sleepy] Hello.",
        )

    def test_condition_age_boundaries_and_missing_report_times(self):
        now = datetime(2026, 10, 6, 12, tzinfo=UTC)
        rules = [
            insertion(condition=EntityStateCondition("binary_sensor.whisper", "on", 30))
        ]
        for age, expected in ((0, True), (30, True), (30.001, False), (-1, False)):
            with self.subTest(age=age):
                report = EntityStateReport("on", now - timedelta(seconds=age))
                self.assertEqual(
                    condition_snapshot(
                        rules, lambda _entity_id, report=report: report, now=now
                    ),
                    (expected,),
                )
        for report in (
            None,
            "on",
            EntityStateReport("on"),
            EntityStateReport("off", now),
        ):
            with self.subTest(report=report):
                self.assertEqual(
                    condition_snapshot(
                        rules, lambda _entity_id, report=report: report, now=now
                    ),
                    (False,),
                )

    def test_age_limits_are_per_rule_and_frozen_with_one_entity_read(self):
        now = datetime(2026, 10, 6, 12, tzinfo=UTC)
        report = EntityStateReport("on", now - timedelta(seconds=15))
        calls = []

        def getter(entity_id):
            calls.append(entity_id)
            return report

        rules = [
            insertion(
                "Expired: ", condition=EntityStateCondition("sensor.test", "on", 10)
            ),
            insertion(
                "Fresh: ", condition=EntityStateCondition("sensor.test", "on", 30)
            ),
            insertion(
                "Unlimited: ", condition=EntityStateCondition("sensor.test", "on")
            ),
        ]
        snapshot = condition_snapshot(rules, getter, now=now)
        self.assertEqual(snapshot, (False, True, True))
        self.assertEqual(calls, ["sensor.test"])
        report = EntityStateReport("off", now + timedelta(minutes=1))
        self.assertEqual(
            normalize_text("Hello.", rules_from_snapshot(rules, snapshot)),
            "Fresh: Unlimited: Hello.",
        )

    def test_age_limited_replacements_and_preview_use_report_time(self):
        raw = {
            CONF_REPLACEMENT_RULES: [
                {
                    "find": "Hello",
                    RULE_REPLACE: "Bye",
                    RULE_CONDITION_ENTITY: "sensor.test",
                    RULE_CONDITION_STATE: "on",
                    RULE_CONDITION_MAX_AGE: 30,
                }
            ]
        }
        for age, expected in ((1, "Bye."), (300, "Hello.")):
            with self.subTest(age=age):
                report = EntityStateReport(
                    "on", datetime.now(UTC) - timedelta(seconds=age)
                )
                self.assertEqual(
                    normalize_text_from_raw_config(
                        "Hello.", raw, entity_states={"sensor.test": report}
                    ),
                    expected,
                )

    def test_condition_maximum_age_validation(self):
        raw = {
            RULE_MODE: RULE_MODE_INSERT,
            RULE_REPLACE: "[whisper] ",
            RULE_PLACEMENTS: ["message_start"],
            RULE_CONDITION_ENTITY: "sensor.test",
            RULE_CONDITION_STATE: "on",
        }
        for age in (
            0,
            -1,
            True,
            1.5,
            float("nan"),
            float("inf"),
            "invalid",
            [],
            10**400,
        ):
            with self.subTest(age=age), self.assertRaises(RuleValidationError):
                parse_rules([{**raw, RULE_CONDITION_MAX_AGE: age}])
        with self.assertRaises(RuleValidationError):
            parse_rules(
                [{"find": "Hello", RULE_REPLACE: "Bye", RULE_CONDITION_MAX_AGE: 30}]
            )
        for age in (None, ""):
            with self.subTest(age=age):
                rule = parse_rules([{**raw, RULE_CONDITION_MAX_AGE: age}])[0]
                self.assertIsNone(rule.condition.max_age_seconds)
                saved = serializable_config(
                    {
                        CONF_TARGET_TTS_ENTITY: "tts.target",
                        CONF_OUTPUT_LANGUAGE: "en",
                        CONF_REPLACEMENT_RULES: [{**raw, RULE_CONDITION_MAX_AGE: age}],
                    }
                )
                self.assertNotIn(
                    RULE_CONDITION_MAX_AGE, saved[CONF_REPLACEMENT_RULES][0]
                )

    def test_conditional_preview_uses_unsaved_values_and_current_states(self):
        raw = {
            CONF_REPLACEMENT_RULES: [
                {
                    RULE_MODE: RULE_MODE_INSERT,
                    RULE_REPLACE: "[whisper] ",
                    RULE_PLACEMENTS: ["sentence_start"],
                    RULE_CONDITION_ENTITY: "binary_sensor.whisper",
                    RULE_CONDITION_STATE: "on",
                }
            ]
        }
        self.assertEqual(
            normalize_text_from_raw_config(
                "Hello.", raw, entity_states={"binary_sensor.whisper": "on"}
            ),
            "[whisper] Hello.",
        )
        self.assertEqual(
            normalize_text_from_raw_config(
                "Hello.", raw, entity_states={"binary_sensor.whisper": "off"}
            ),
            "Hello.",
        )

    def test_sentence_insertion_and_date_normalization(self):
        dates = DateNormalizer(
            enabled=True,
            locale="en-US",
            input_formats=("dmy_dot", "dmy_dot_spaced"),
            converter=lambda value, language, kind: str(value),
        )
        compact = dates.normalize("23.05.2026")
        self.assertEqual(
            normalize_text(
                "Date: 23.05.2026. Next.", [insertion()], date_normalizer=dates
            ),
            f"[whisper] Date: {compact}. [whisper] Next.",
        )
        # The explicitly simple punctuation heuristic also splits spaced date dots.
        self.assertEqual(
            normalize_text("Date: 23. 05. 2026.", [insertion()], date_normalizer=dates),
            "[whisper] Date: 23. [whisper] 05. [whisper] 2026.",
        )

    def test_new_fields_round_trip_without_stripping_insertion_whitespace(self):
        raw_rule = {
            RULE_MODE: RULE_MODE_INSERT,
            RULE_REPLACE: " [whisper] ",
            RULE_PLACEMENTS: ["message_start", "line_start"],
            RULE_CONDITION_ENTITY: "binary_sensor.whisper",
            RULE_CONDITION_STATE: "on",
            RULE_CONDITION_MAX_AGE: 30,
        }
        raw = {
            CONF_TARGET_TTS_ENTITY: "tts.target",
            CONF_OUTPUT_LANGUAGE: "en",
            CONF_REPLACEMENT_RULES: [raw_rule],
        }
        saved = serializable_config(raw)
        displayed = form_defaults(saved)
        for key, value in raw_rule.items():
            self.assertEqual(displayed[CONF_REPLACEMENT_RULES][0][key], value)
        self.assertEqual(
            parse_rules(saved[CONF_REPLACEMENT_RULES]),
            parse_rules(displayed[CONF_REPLACEMENT_RULES]),
        )

    def test_incomplete_conditions_invalid_placements_and_empty_insertions_are_rejected(
        self,
    ):
        invalid = [
            {RULE_CONDITION_ENTITY: "sensor.test"},
            {RULE_CONDITION_STATE: "on"},
            {RULE_CONDITION_ENTITY: "invalid", RULE_CONDITION_STATE: "on"},
            {RULE_MODE: RULE_MODE_INSERT, RULE_REPLACE: "[whisper]"},
            {
                RULE_MODE: RULE_MODE_INSERT,
                RULE_REPLACE: "",
                RULE_PLACEMENTS: ["line_start"],
            },
            {
                RULE_MODE: RULE_MODE_INSERT,
                RULE_REPLACE: "x",
                RULE_PLACEMENTS: "line_start",
            },
            {
                RULE_MODE: RULE_MODE_INSERT,
                RULE_REPLACE: "x",
                RULE_PLACEMENTS: ["invalid"],
            },
        ]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(RuleValidationError):
                parse_rules([raw])


class StreamingInsertionTests(unittest.IsolatedAsyncioTestCase):
    async def test_insertions_are_independent_of_input_chunks_and_flush_sizes(self):
        text = '  [other] Hello. "Good night!"\r\n\nNext line\rFinal? Yes.'
        for placements in (
            (Placement.MESSAGE_START,),
            (Placement.LINE_START,),
            (Placement.SENTENCE_START,),
            tuple(Placement),
        ):
            rules = [
                insertion(placements=placements),
                insertion("[sleepy] ", placements=placements),
            ]
            expected = normalize_text(text, rules)
            for cut in range(len(text) + 1):
                for tail, limit in ((0, 1), (2, 9), (64, 500)):

                    async def chunks(split_at=cut):
                        for piece in (text[:split_at], "", text[split_at:]):
                            yield piece

                    output = "".join(
                        [
                            part
                            async for part in normalize_stream(
                                chunks(),
                                rules,
                                safety_tail_chars=tail,
                                max_buffer_chars=limit,
                            )
                        ]
                    )
                    self.assertEqual(output, expected, (placements, cut, tail, limit))

    async def test_long_ordinary_duplicate_prefix_spanning_flushes(self):
        text = "This is a rather long existing prefix: Hello. Next."
        rule = insertion("This is a rather long existing prefix: ")

        async def chunks():
            for char in text:
                yield char

        result = "".join(
            [
                part
                async for part in normalize_stream(
                    chunks(), [rule], safety_tail_chars=0, max_buffer_chars=1
                )
            ]
        )
        self.assertEqual(
            result,
            "This is a rather long existing prefix: Hello. "
            "This is a rather long existing prefix: Next.",
        )

    async def test_stream_captures_conditions_once(self):
        states = {"binary_sensor.whisper": "on"}

        async def chunks():
            yield "First. "
            states["binary_sensor.whisper"] = "off"
            yield "Next."

        result = "".join(
            [
                part
                async for part in normalize_stream(
                    chunks(),
                    [
                        insertion(
                            condition=EntityStateCondition(
                                "binary_sensor.whisper", "on"
                            )
                        )
                    ],
                    entity_states=states,
                    safety_tail_chars=0,
                    max_buffer_chars=1,
                )
            ]
        )
        self.assertEqual(result, "[whisper] First. [whisper] Next.")

    async def test_first_output_does_not_wait_for_entire_message(self):
        async def chunks():
            yield "First. "
            raise AssertionError(
                "First speech must be emitted before requesting more input"
            )

        stream = normalize_stream(
            chunks(), [insertion()], safety_tail_chars=0, max_buffer_chars=1
        )
        try:
            self.assertEqual(await anext(stream), "[whisper] First. ")
        finally:
            await stream.aclose()

    async def test_existing_tag_duplicate_survives_every_character_split(self):
        text = "[whisper] [other_tag] Hello. [whisper] Next."

        async def chunks():
            for char in text:
                yield char

        result = "".join(
            [
                part
                async for part in normalize_stream(
                    chunks(), [insertion()], safety_tail_chars=0, max_buffer_chars=1
                )
            ]
        )
        self.assertEqual(result, text)

    def test_insertion_processor_handles_every_split_including_incomplete_tags(self):
        text = '<speak>[whisper] Hello. "Bye."\nNext</speak>'
        rule = insertion(placements=tuple(Placement))
        expected = normalize_text(text, [rule])
        for cut in range(len(text) + 1):
            processor = TextInsertionProcessor([rule])
            self.assertEqual(
                processor.feed(text[:cut]) + processor.feed(text[cut:], final=True),
                expected,
            )
