"""Tests for TTS Proxy text normalization."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import unittest

from custom_components.tts_proxy.config import parse_proxy_config
from custom_components.tts_proxy.const import (
    CONF_FINAL_TTS_ENTITY,
    CONF_MAX_BUFFER_CHARS,
    CONF_OUTPUT_LANGUAGE,
    CONF_REPLACEMENT_RULES,
    CONF_SAFETY_TAIL_CHARS,
    RULE_CASE_SENSITIVE,
    RULE_DISABLED,
    RULE_ENABLED,
    RULE_FIND,
    RULE_IGNORE_CASE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_REPLACE,
)
from custom_components.tts_proxy.normalizer import (
    ReplacementRule,
    RuleMode,
    RuleValidationError,
    normalize_stream,
    normalize_text,
    parse_rules,
    validate_streaming_buffer_config,
)


async def _chunks(values: list[str]) -> AsyncGenerator[str]:
    """Yield test chunks."""
    for value in values:
        yield value


async def _collect_stream(values: list[str], rules: list[ReplacementRule], **kwargs) -> list[str]:
    """Collect normalized stream chunks."""
    return [chunk async for chunk in normalize_stream(_chunks(values), rules, **kwargs)]


class ReplacementRuleTests(unittest.TestCase):
    """Replacement Rule behavior."""

    def test_literal_rule_replaces_exact_text(self) -> None:
        rule = ReplacementRule("kWh", "Kilowattstunden")

        self.assertEqual(
            normalize_text("Heute 12 kWh verbraucht.", [rule]),
            "Heute 12 Kilowattstunden verbraucht.",
        )

    def test_regex_rule_uses_capture_groups(self) -> None:
        rule = ReplacementRule(
            r"(\d+(?:[,.]\d+)?)\s*°C",
            r"\1 Grad",
            mode=RuleMode.REGEX,
        )

        self.assertEqual(
            normalize_text("Temp ist 23,5 °C.", [rule]),
            "Temp ist 23,5 Grad.",
        )

    def test_rules_run_in_order_once_each(self) -> None:
        rules = [
            ReplacementRule("A", "AA"),
            ReplacementRule("AA", "B"),
        ]

        self.assertEqual(normalize_text("A", rules), "B")

    def test_ignore_case_is_opt_in(self) -> None:
        sensitive = ReplacementRule("kwh", "Kilowattstunden")
        insensitive = ReplacementRule("kwh", "Kilowattstunden", ignore_case=True)

        self.assertEqual(normalize_text("1 kWh", [sensitive]), "1 kWh")
        self.assertEqual(normalize_text("1 kWh", [insensitive]), "1 Kilowattstunden")

    def test_raw_rules_default_to_ignore_case(self) -> None:
        rules = parse_rules(
            [
                {
                    RULE_FIND: "kwh",
                    RULE_REPLACE: "Kilowattstunden",
                }
            ]
        )

        self.assertEqual(normalize_text("1 kWh", rules), "1 Kilowattstunden")

    def test_case_sensitive_ui_flag_inverts_to_ignore_case_model(self) -> None:
        rules = parse_rules(
            [
                {
                    RULE_CASE_SENSITIVE: True,
                    RULE_FIND: "kwh",
                    RULE_REPLACE: "Kilowattstunden",
                }
            ]
        )

        self.assertEqual(normalize_text("1 kWh", rules), "1 kWh")

    def test_disabled_rules_are_skipped(self) -> None:
        rule = ReplacementRule("kWh", "Kilowattstunden", enabled=False)

        self.assertEqual(normalize_text("1 kWh", [rule]), "1 kWh")

    def test_provider_control_tags_are_preserved(self) -> None:
        rules = [
            ReplacementRule("whispers", "fluestert", ignore_case=True),
            ReplacementRule("°C", "Grad"),
        ]

        self.assertEqual(
            normalize_text("[whispers] Temp 23°C <break time=\"1s\"/>", rules),
            "[whispers] Temp 23Grad <break time=\"1s\"/>",
        )

    def test_square_bracket_contents_are_opaque(self) -> None:
        rule = ReplacementRule("°C", "Grad")

        self.assertEqual(normalize_text("[23°C] 24°C", [rule]), "[23°C] 24Grad")

    def test_invalid_regex_is_rejected(self) -> None:
        with self.assertRaises(RuleValidationError):
            parse_rules(
                [
                    {
                        RULE_MODE: RULE_MODE_REGEX,
                        RULE_FIND: "(",
                        RULE_REPLACE: "",
                    }
                ]
            )

    def test_empty_find_is_rejected(self) -> None:
        with self.assertRaises(RuleValidationError):
            ReplacementRule("", "x")

    def test_missing_mode_defaults_to_literal(self) -> None:
        rules = parse_rules(
            [
                {
                    RULE_FIND: "kWh",
                    RULE_REPLACE: "Kilowattstunden",
                }
            ]
        )

        self.assertEqual(normalize_text("1 kWh", rules), "1 Kilowattstunden")

    def test_disabled_ui_flag_inverts_to_enabled_model(self) -> None:
        active_rules = parse_rules(
            [
                {
                    RULE_DISABLED: False,
                    RULE_FIND: "kWh",
                    RULE_REPLACE: "Kilowattstunden",
                }
            ]
        )
        disabled_rules = parse_rules(
            [
                {
                    RULE_DISABLED: True,
                    RULE_FIND: "kWh",
                    RULE_REPLACE: "Kilowattstunden",
                }
            ]
        )

        self.assertEqual(normalize_text("1 kWh", active_rules), "1 Kilowattstunden")
        self.assertEqual(normalize_text("1 kWh", disabled_rules), "1 kWh")


class StreamingNormalizerTests(unittest.IsolatedAsyncioTestCase):
    """Streaming normalization behavior."""

    async def test_stream_replacements_can_span_chunks(self) -> None:
        rule = ReplacementRule(
            r"(\d+(?:[,.]\d+)?)\s*°C",
            r"\1 Grad",
            mode=RuleMode.REGEX,
        )

        output = await _collect_stream(
            ["Temp ist 53", ".4", "°", "C."],
            [rule],
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Temp ist 53.4 Grad.")

    async def test_stream_preserves_split_provider_control_tags(self) -> None:
        rule = ReplacementRule("°C", "Grad")

        output = await _collect_stream(
            ["[whis", "pers] Temp 23", "°C"],
            [rule],
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "[whispers] Temp 23Grad")

    async def test_stream_flushes_final_text_without_punctuation(self) -> None:
        rule = ReplacementRule("kWh", "Kilowattstunden")

        output = await _collect_stream(["Heute 12 ", "kWh"], [rule])

        self.assertEqual("".join(output), "Heute 12 Kilowattstunden")

    async def test_decimal_punctuation_is_not_sentence_boundary(self) -> None:
        rule = ReplacementRule("°C", "Grad")

        output = await _collect_stream(
            ["Der Wert ist 53.4°C. Danach weiter. "],
            [rule],
            safety_tail_chars=5,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Der Wert ist 53.4Grad. Danach weiter. ")

    async def test_stream_uses_whitespace_fallback_after_buffer_limit(self) -> None:
        output = await _collect_stream(
            ["eins zwei drei vier fuenf sechs"],
            [],
            safety_tail_chars=5,
            max_buffer_chars=12,
        )

        self.assertGreater(len(output), 1)
        self.assertEqual("".join(output), "eins zwei drei vier fuenf sechs")


class ConfigTests(unittest.TestCase):
    """Proxy Configuration parsing."""

    def test_proxy_config_parses_rules_and_buffers(self) -> None:
        config = parse_proxy_config(
            {
                "name": "German proxy",
                CONF_FINAL_TTS_ENTITY: "tts.final",
                CONF_OUTPUT_LANGUAGE: "de-DE",
                CONF_REPLACEMENT_RULES: [
                    {
                        RULE_ENABLED: True,
                        RULE_MODE: RULE_MODE_LITERAL,
                        RULE_FIND: "kWh",
                        RULE_REPLACE: "Kilowattstunden",
                        RULE_IGNORE_CASE: False,
                    }
                ],
                CONF_SAFETY_TAIL_CHARS: 64,
                CONF_MAX_BUFFER_CHARS: 500,
            }
        )

        self.assertEqual(config.name, "German proxy")
        self.assertEqual(config.final_tts_entity, "tts.final")
        self.assertEqual(config.output_language, "de-DE")
        self.assertEqual(len(config.rules), 1)
        self.assertEqual(config.safety_tail_chars, 64)
        self.assertEqual(config.max_buffer_chars, 500)

    def test_buffer_limit_must_exceed_safety_tail(self) -> None:
        with self.assertRaises(ValueError):
            validate_streaming_buffer_config(64, 64)

    def test_missing_required_config_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_proxy_config(
                {
                    CONF_FINAL_TTS_ENTITY: None,
                    CONF_OUTPUT_LANGUAGE: "de-DE",
                }
            )


if __name__ == "__main__":
    unittest.main()
