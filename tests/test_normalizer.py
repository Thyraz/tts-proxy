"""Tests for TTS Proxy text normalization."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import unittest
from unittest.mock import patch

from custom_components.tts_proxy.config import (
    form_defaults,
    parse_proxy_config,
    serializable_config,
)
from custom_components.tts_proxy.const import (
    CONF_DATE_INPUT_FORMATS,
    CONF_DATE_LOCALE,
    CONF_DATE_NORMALIZER_ENABLED,
    CONF_DATE_RENDERER,
    CONF_EMOJI_HANDLING,
    CONF_EMOJI_LANGUAGE,
    CONF_EMOJI_NORMALIZER_ENABLED,
    CONF_TARGET_TTS_ENTITY,
    CONF_MARKDOWN_CLEANUP_ENABLED,
    CONF_MARKDOWN_REMOVE_CODE_BLOCKS,
    CONF_MARKDOWN_REMOVE_PLAIN_URLS,
    CONF_MARKDOWN_STRIP_EMPHASIS,
    CONF_MARKDOWN_STRIP_LINKS,
    CONF_MARKDOWN_STRIP_TABLES,
    CONF_MAX_BUFFER_CHARS,
    CONF_NUMBER_NORMALIZER_ENABLED,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_OUTPUT_LANGUAGE,
    CONF_PREVIEW_TEXT,
    CONF_REPLACEMENT_RULES,
    CONF_SAFETY_TAIL_CHARS,
    DATE_INPUT_FORMAT_DMY_DOT,
    DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
    DATE_INPUT_FORMAT_DMY_DOT_SPACED,
    DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,
    DATE_INPUT_FORMAT_DMY_MONTH_NAME,
    DATE_INPUT_FORMAT_DMY_SLASH,
    DATE_INPUT_FORMAT_MDY_MONTH_NAME,
    DATE_INPUT_FORMAT_MDY_SLASH,
    DATE_INPUT_FORMAT_YMD_DASH,
    DATE_RENDERER_CURATED,
    DATE_RENDERER_NUMERIC_FALLBACK,
    EMOJI_HANDLING_REMOVE,
    EMOJI_HANDLING_SPELLOUT,
    RULE_CASE_SENSITIVE,
    RULE_DISABLED,
    RULE_ENABLED,
    RULE_FIND,
    RULE_IGNORE_CASE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_NAME,
    RULE_REPLACE,
    SECTION_GENERAL,
    SECTION_EMOJI,
    SECTION_MARKDOWN,
    SECTION_NUMBERS,
)
from custom_components.tts_proxy.date_normalizer import (
    DateNormalizationError,
    DateNormalizer,
    default_date_input_formats,
    default_date_renderer,
    parse_date_normalizer,
)
from custom_components.tts_proxy.emoji_normalizer import (
    EmojiNormalizationError,
    EmojiNormalizer,
    default_emoji_language,
    parse_emoji_normalizer,
)
from custom_components.tts_proxy.markdown_normalizer import MarkdownCleanupNormalizer
from custom_components.tts_proxy.normalizer import (
    NumberNormalizationError,
    NumberNormalizer,
    ReplacementRule,
    RuleMode,
    RuleValidationError,
    normalize_stream,
    normalize_text,
    normalize_text_from_raw_config,
    parse_rules,
    validate_streaming_buffer_config,
)
from custom_components.tts_proxy.preview import preview_event_payload


async def _chunks(values: list[str]) -> AsyncGenerator[str]:
    """Yield test chunks."""
    for value in values:
        yield value


def _fake_german_number(value: int | str, language: str) -> str:
    """Return German spellout values used by normalizer tests."""
    if language != "de":
        raise ValueError(f"Unexpected language: {language}")

    return {
        -1: "minus eins",
        -5: "minus fünf",
        0: "null",
        1: "eins",
        2: "zwei",
        3: "drei",
        4: "vier",
        5: "fünf",
        6: "sechs",
        7: "sieben",
        8: "acht",
        9: "neun",
        12: "zwölf",
        13: "dreizehn",
        21: "einundzwanzig",
        30: "dreißig",
        53: "dreiundfünfzig",
        123: "einhundertdreiundzwanzig",
        2026: "zweitausendsechsundzwanzig",
        "0.5": "null Komma fünf",
        "0.7": "null Komma sieben",
        "53.4": "dreiundfünfzig Komma vier",
        "7.7": "sieben Komma sieben",
        "7.1234": "sieben Komma eins zwei drei vier",
    }[value]


def _fake_date_number(value: int, language: str, purpose: str) -> str:
    """Return spellout values used by Date Normalizer tests."""
    values = {
        ("de", "ordinal", 5): "fünfte",
        ("de", "ordinal", 14): "vierzehnte",
        ("de", "ordinal", 15): "fünfzehnte",
        ("de", "ordinal", 21): "einundzwanzigste",
        ("de", "ordinal", 23): "dreiundzwanzigste",
        ("de", "ordinal", 25): "fünfundzwanzigste",
        ("de", "ordinal", 27): "siebenundzwanzigste",
        ("de", "year", 1984): "neunzehnhundertvierundachtzig",
        ("de", "year", 2025): "zweitausendfünfundzwanzig",
        ("de", "year", 2026): "zweitausendsechsundzwanzig",
        ("en", "ordinal", 15): "fifteenth",
        ("en", "cardinal", 19): "nineteen",
        ("en", "cardinal", 20): "twenty",
        ("en", "cardinal", 25): "twenty-five",
        ("en", "cardinal", 26): "twenty-six",
        ("fr", "cardinal", 14): "quatorze",
        ("fr", "cardinal", 5): "cinq",
        ("fr", "year", 2026): "deux mille vingt-six",
    }
    return values[(language, purpose, value)]


def _fake_emoji_replacer(text, replace):
    """Replace fake emoji test tokens."""
    data = {
        "😀": {"de": ":grinsendes_gesicht:", "en": ":grinning_face:"},
        "🔥": {"de": ":feuer:", "en": ":fire:"},
        "👍": {"en": ":thumbs_up:"},
    }
    return "".join(replace(char, data[char]) if char in data else char for char in text)


class _FakeEmojiModule:
    """Fake emoji package that requires explicit language loading."""

    def __init__(self) -> None:
        """Initialize fake package state."""
        self.loaded_languages: list[str] = []
        self.config = self

    def load_language(self, language: str) -> None:
        """Record a loaded language."""
        self.loaded_languages.append(language)

    def replace_emoji(self, text, replace):
        """Replace one emoji using language data only after load_language."""
        data = {"en": ":grinning_face_with_smiling_eyes:"}
        if "de" in self.loaded_languages:
            data["de"] = ":grinsendes_gesicht_mit_lachenden_augen:"
        return text.replace("😄", replace("😄", data))


def _german_number_normalizer() -> NumberNormalizer:
    """Return an enabled fake German Number Normalizer."""
    return NumberNormalizer(
        enabled=True,
        language="de",
        converter=_fake_german_number,
    )


def _markdown_normalizer(**kwargs: bool) -> MarkdownCleanupNormalizer:
    """Return an enabled Markdown Cleanup Normalizer."""
    return MarkdownCleanupNormalizer(enabled=True, **kwargs)


def _emoji_normalizer(
    *,
    handling: str = EMOJI_HANDLING_SPELLOUT,
    language: str = "de",
) -> EmojiNormalizer:
    """Return an enabled fake Emoji Normalizer."""
    return EmojiNormalizer(
        enabled=True,
        handling=handling,
        language=language,
        replacer=_fake_emoji_replacer,
    )


def _date_normalizer(
    *,
    locale: str = "de-DE",
    renderer: str = DATE_RENDERER_CURATED,
    input_formats: tuple[str, ...] = (
        DATE_INPUT_FORMAT_DMY_DOT,
        DATE_INPUT_FORMAT_DMY_DOT_SPACED,
        DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
        DATE_INPUT_FORMAT_DMY_MONTH_NAME,
        DATE_INPUT_FORMAT_YMD_DASH,
    ),
) -> DateNormalizer:
    """Return an enabled fake Date Normalizer."""
    return DateNormalizer(
        enabled=True,
        locale=locale,
        renderer=renderer,
        input_formats=input_formats,
        converter=_fake_date_number,
    )


async def _collect_stream(
    values: list[str],
    rules: list[ReplacementRule],
    number_normalizer: NumberNormalizer | None = None,
    date_normalizer: DateNormalizer | None = None,
    markdown_normalizer: MarkdownCleanupNormalizer | None = None,
    **kwargs,
) -> list[str]:
    """Collect normalized stream chunks."""
    return [
        chunk
        async for chunk in normalize_stream(
            _chunks(values),
            rules,
            number_normalizer,
            date_normalizer,
            markdown_normalizer,
            **kwargs,
        )
    ]


class ReplacementRuleTests(unittest.TestCase):
    """Replacement Rule behavior."""

    def test_literal_rule_replaces_exact_text(self) -> None:
        rule = ReplacementRule("kWh", "Kilowattstunden")

        self.assertEqual(
            normalize_text("Heute 12 kWh verbraucht.", [rule]),
            "Heute 12 Kilowattstunden verbraucht.",
        )

    def test_rule_name_does_not_affect_matching(self) -> None:
        rule = ReplacementRule("kWh", "Kilowattstunden", name="Energy unit")

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

    def test_direct_rules_are_case_sensitive_by_default(self) -> None:
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


class MarkdownCleanupTests(unittest.TestCase):
    """Markdown Cleanup Normalizer behavior."""

    def test_disabled_normalizer_leaves_markdown_unchanged(self) -> None:
        normalizer = MarkdownCleanupNormalizer(enabled=False)

        self.assertEqual(
            normalize_text("**Wichtig**", [], markdown_normalizer=normalizer),
            "**Wichtig**",
        )

    def test_strips_common_inline_and_block_markers(self) -> None:
        text = "\n".join(
            [
                "# Wetter",
                "- [x] **Heute** ist `sensor.temp` aktiv",
                "1. ~~Morgen~~ prüfen",
                "> Hinweis",
                "---",
            ]
        )

        self.assertEqual(
            normalize_text(text, [], markdown_normalizer=_markdown_normalizer()),
            "\n".join(
                [
                    "Wetter",
                    "Heute ist sensor.temp aktiv",
                    "Morgen prüfen",
                    "Hinweis",
                ]
            ),
        )

    def test_strips_links_images_and_optionally_plain_urls(self) -> None:
        text = (
            "[Details](https://example.com/weather) "
            "![Karte](https://example.com/map.png) "
            "[whispers] https://example.com/raw"
        )

        self.assertEqual(
            normalize_text(text, [], markdown_normalizer=_markdown_normalizer()),
            "Details Karte [whispers] https://example.com/raw",
        )
        self.assertEqual(
            normalize_text(
                text,
                [],
                markdown_normalizer=_markdown_normalizer(remove_plain_urls=True),
            ),
            "Details Karte [whispers] ",
        )

    def test_markdown_link_cleanup_does_not_strip_provider_control_tags(self) -> None:
        self.assertEqual(
            normalize_text(
                "[whispers] [Details](https://example.com)",
                [],
                markdown_normalizer=_markdown_normalizer(),
            ),
            "[whispers] Details",
        )

    def test_markdown_cleanup_keeps_provider_control_tag_contents_opaque(self) -> None:
        text = '[very **quiet**] <break time="1s"/> **laut**'

        self.assertEqual(
            normalize_text(text, [], markdown_normalizer=_markdown_normalizer()),
            '[very **quiet**] <break time="1s"/> laut',
        )

    def test_strips_table_formatting_without_rendering_table_semantics(self) -> None:
        text = "\n".join(
            [
                "| Tag | Höchst | Tiefst |",
                "| --- | --- | --- |",
                "| 21. Juli | 22 °C | 17 °C |",
                "| 22. Juli | 24 °C | 11 °C |",
            ]
        )

        self.assertEqual(
            normalize_text(text, [], markdown_normalizer=_markdown_normalizer()),
            "\n".join(
                [
                    "Tag. Höchst. Tiefst.",
                    "21. Juli. 22 °C. 17 °C.",
                    "22. Juli. 24 °C. 11 °C.",
                ]
            ),
        )

    def test_code_blocks_are_protected_unless_removal_is_enabled(self) -> None:
        text = "Vorher\n```yaml\nsensor:\n  - platform: template\n```\nNachher"

        self.assertEqual(
            normalize_text(text, [], markdown_normalizer=_markdown_normalizer()),
            text,
        )
        self.assertEqual(
            normalize_text(
                text,
                [],
                markdown_normalizer=_markdown_normalizer(remove_code_blocks=True),
            ),
            "Vorher\nNachher",
        )

    def test_markdown_cleanup_runs_after_rules_and_before_date_and_number(self) -> None:
        rules = [ReplacementRule("morgen", "**21. Juli 2026**")]

        self.assertEqual(
            normalize_text(
                "Termin morgen mit 3 Punkten.",
                rules,
                _german_number_normalizer(),
                _date_normalizer(input_formats=(DATE_INPUT_FORMAT_DMY_MONTH_NAME,)),
                _markdown_normalizer(),
            ),
            "Termin einundzwanzigster Juli zweitausendsechsundzwanzig mit drei Punkten.",
        )


class EmojiNormalizerTests(unittest.TestCase):
    """Emoji Normalizer behavior."""

    def test_disabled_normalizer_leaves_emoji_unchanged(self) -> None:
        normalizer = EmojiNormalizer(
            enabled=False,
            language="de",
            replacer=_fake_emoji_replacer,
        )

        self.assertEqual(
            normalize_text("Gut 😀", [], emoji_normalizer=normalizer),
            "Gut 😀",
        )

    def test_enabled_normalizer_leaves_text_without_emoji_unchanged(self) -> None:
        text = "Hallo , Welt"

        self.assertEqual(
            normalize_text(text, [], emoji_normalizer=_emoji_normalizer()),
            text,
        )

    def test_spells_emoji_with_comma_separators(self) -> None:
        normalizer = _emoji_normalizer()

        self.assertEqual(
            normalize_text("Das ist gut 😀", [], emoji_normalizer=normalizer),
            "Das ist gut, grinsendes gesicht",
        )
        self.assertEqual(
            normalize_text("😀 Danke!", [], emoji_normalizer=normalizer),
            "grinsendes gesicht, Danke!",
        )
        self.assertEqual(
            normalize_text("Super 😀🔥", [], emoji_normalizer=normalizer),
            "Super, grinsendes gesicht, feuer",
        )

    def test_real_emoji_backend_loads_selected_language_before_replacement(
        self,
    ) -> None:
        fake_emoji = _FakeEmojiModule()
        normalizer = EmojiNormalizer(
            enabled=True,
            handling=EMOJI_HANDLING_SPELLOUT,
            language="de",
        )

        with patch.dict("sys.modules", {"emoji": fake_emoji}):
            self.assertEqual(
                normalize_text("Gut 😄", [], emoji_normalizer=normalizer),
                "Gut, grinsendes gesicht mit lachenden augen",
            )

    def test_spellout_falls_back_to_english_when_language_name_is_missing(self) -> None:
        normalizer = _emoji_normalizer(language="de")

        self.assertEqual(
            normalize_text("Gut 👍", [], emoji_normalizer=normalizer),
            "Gut, thumbs up",
        )

    def test_remove_emoji_without_adding_punctuation(self) -> None:
        normalizer = _emoji_normalizer(handling=EMOJI_HANDLING_REMOVE)

        self.assertEqual(
            normalize_text("Super 😀🔥!", [], emoji_normalizer=normalizer),
            "Super!",
        )
        self.assertEqual(
            normalize_text("A 😀 B", [], emoji_normalizer=normalizer),
            "A B",
        )

    def test_provider_control_tags_are_not_emoji_normalized(self) -> None:
        self.assertEqual(
            normalize_text(
                "[😀] Text 😀 <tag 😀/>",
                [],
                emoji_normalizer=_emoji_normalizer(),
            ),
            "[😀] Text, grinsendes gesicht <tag 😀/>",
        )

    def test_emoji_normalizer_runs_after_markdown_and_before_number_normalizer(
        self,
    ) -> None:
        self.assertEqual(
            normalize_text(
                "**😀 3**",
                [],
                _german_number_normalizer(),
                markdown_normalizer=_markdown_normalizer(),
                emoji_normalizer=_emoji_normalizer(),
            ),
            "grinsendes gesicht, drei",
        )

    def test_default_emoji_language_prefers_output_language_then_english(self) -> None:
        self.assertEqual(default_emoji_language("de-DE", ("de", "en")), "de")
        self.assertEqual(default_emoji_language("nl-NL", ("de", "en")), "en")

    def test_parse_emoji_normalizer_requires_supported_language_for_spellout(self) -> None:
        with patch(
            "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
            return_value=("de", "en"),
        ):
            normalizer = parse_emoji_normalizer(
                {
                    CONF_EMOJI_NORMALIZER_ENABLED: True,
                    CONF_EMOJI_HANDLING: EMOJI_HANDLING_SPELLOUT,
                    CONF_EMOJI_LANGUAGE: "de",
                }
            )

        self.assertTrue(normalizer.enabled)
        self.assertEqual(normalizer.handling, EMOJI_HANDLING_SPELLOUT)
        self.assertEqual(normalizer.language, "de")

    def test_parse_emoji_normalizer_allows_remove_without_language(self) -> None:
        with patch(
            "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
            return_value=("de", "en"),
        ):
            normalizer = parse_emoji_normalizer(
                {
                    CONF_EMOJI_NORMALIZER_ENABLED: True,
                    CONF_EMOJI_HANDLING: EMOJI_HANDLING_REMOVE,
                    CONF_EMOJI_LANGUAGE: "",
                }
            )

        self.assertTrue(normalizer.enabled)
        self.assertEqual(normalizer.handling, EMOJI_HANDLING_REMOVE)

    def test_parse_emoji_normalizer_rejects_unknown_language_when_enabled(
        self,
    ) -> None:
        with patch(
            "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
            return_value=("de", "en"),
        ):
            with self.assertRaises(EmojiNormalizationError):
                parse_emoji_normalizer(
                    {
                        CONF_EMOJI_NORMALIZER_ENABLED: True,
                        CONF_EMOJI_HANDLING: EMOJI_HANDLING_SPELLOUT,
                        CONF_EMOJI_LANGUAGE: "xx",
                    }
                )

    def test_normalizes_preview_text_from_unsaved_sectioned_emoji_config(self) -> None:
        raw_config = {
            SECTION_EMOJI: {
                CONF_EMOJI_NORMALIZER_ENABLED: True,
                CONF_EMOJI_HANDLING: EMOJI_HANDLING_SPELLOUT,
                CONF_EMOJI_LANGUAGE: "de",
            },
        }

        with (
            patch(
                "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
                return_value=("de", "en"),
            ),
            patch(
                "custom_components.tts_proxy.emoji_normalizer._replace_emoji",
                side_effect=_fake_emoji_replacer,
            ),
        ):
            self.assertEqual(
                normalize_text_from_raw_config("Gut 😀", raw_config),
                "Gut, grinsendes gesicht",
            )


class NumberNormalizerTests(unittest.TestCase):
    """Number Normalizer behavior."""

    def test_disabled_normalizer_leaves_numbers_unchanged(self) -> None:
        normalizer = NumberNormalizer(enabled=False, language="de")

        self.assertEqual(normalize_text("Wert 123.", [], normalizer), "Wert 123.")

    def test_spells_simple_integers(self) -> None:
        self.assertEqual(
            normalize_text("Wert 123 und -5.", [], _german_number_normalizer()),
            "Wert einhundertdreiundzwanzig und minus fünf.",
        )

    def test_spells_one_separator_decimals_with_point_or_comma(self) -> None:
        self.assertEqual(
            normalize_text("Temp 53.4 und 53,4.", [], _german_number_normalizer()),
            "Temp dreiundfünfzig Komma vier und dreiundfünfzig Komma vier.",
        )

    def test_decimal_formatting_zeroes_are_trimmed_before_spellout(self) -> None:
        self.assertEqual(
            normalize_text(
                "Werte 07.70, 0007.123400, 0007.000 und 0.70.",
                [],
                _german_number_normalizer(),
            ),
            (
                "Werte sieben Komma sieben, sieben Komma eins zwei drei vier, "
                "sieben und null Komma sieben."
            ),
        )

    def test_leading_zero_integers_are_spoken_as_digit_sequences(self) -> None:
        self.assertEqual(
            normalize_text("Codes 007, 000123 und -09.", [], _german_number_normalizer()),
            "Codes null null sieben, null null null eins zwei drei und minus null neun.",
        )

    def test_skips_structured_and_identifier_tokens(self) -> None:
        def fail_on_call(value: int | str, language: str) -> str:
            raise AssertionError(f"Unexpected conversion: {value} {language}")

        normalizer = NumberNormalizer(
            enabled=True,
            language="de",
            converter=fail_on_call,
        )
        text = (
            "IP 192.168.1.1, Version v1.2.3, Datum 20.07.2026, "
            "Zeit 12:30, ESP32, B12, B007, sensor_007."
        )

        self.assertEqual(normalize_text(text, [], normalizer), text)

    def test_replacement_rules_run_before_number_normalizer(self) -> None:
        rules = [
            ReplacementRule(r"(?<=\d):00\b", " Uhr", mode=RuleMode.REGEX),
            ReplacementRule(r"(?<=\d):(?=\d)", " Uhr ", mode=RuleMode.REGEX),
            ReplacementRule(
                r"(?<=\d)\s*[-–—]\s*(?=\d)",
                " bis ",
                mode=RuleMode.REGEX,
            ),
        ]

        self.assertEqual(
            normalize_text(
                "12:30-13:00",
                rules,
                _german_number_normalizer(),
            ),
            "zwölf Uhr dreißig bis dreizehn Uhr",
        )

    def test_provider_control_tags_are_not_number_normalized(self) -> None:
        self.assertEqual(
            normalize_text(
                "[123] Wert 123 <break time=\"1s\"/>",
                [],
                _german_number_normalizer(),
            ),
            "[123] Wert einhundertdreiundzwanzig <break time=\"1s\"/>",
        )

    def test_parse_number_normalizer_requires_supported_language_when_enabled(self) -> None:
        with patch(
            "custom_components.tts_proxy.normalizer.supported_number_spellout_languages",
            return_value=("de", "en"),
        ):
            config = parse_proxy_config(
                {
                    CONF_TARGET_TTS_ENTITY: "tts.target",
                    CONF_OUTPUT_LANGUAGE: "de-DE",
                    CONF_NUMBER_NORMALIZER_ENABLED: True,
                    CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
                }
            )

        self.assertTrue(config.number_normalizer.enabled)
        self.assertEqual(config.number_normalizer.language, "de")

    def test_parse_number_normalizer_rejects_unknown_language_when_enabled(self) -> None:
        with patch(
            "custom_components.tts_proxy.normalizer.supported_number_spellout_languages",
            return_value=("de", "en"),
        ):
            with self.assertRaises(NumberNormalizationError):
                parse_proxy_config(
                    {
                        CONF_TARGET_TTS_ENTITY: "tts.target",
                        CONF_OUTPUT_LANGUAGE: "de-DE",
                        CONF_NUMBER_NORMALIZER_ENABLED: True,
                        CONF_NUMBER_SPELLOUT_LANGUAGE: "xx",
                    }
                )

    def test_normalizes_preview_text_from_unsaved_raw_config(self) -> None:
        raw_config = {
            CONF_REPLACEMENT_RULES: [
                {
                    RULE_MODE: RULE_MODE_LITERAL,
                    RULE_FIND: "°C",
                    RULE_REPLACE: " Grad",
                }
            ],
            CONF_NUMBER_NORMALIZER_ENABLED: True,
            CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
        }

        with (
            patch(
                "custom_components.tts_proxy.normalizer.supported_number_spellout_languages",
                return_value=("de",),
            ),
            patch(
                "custom_components.tts_proxy.normalizer._spellout_number",
                side_effect=_fake_german_number,
            ),
        ):
            self.assertEqual(
                normalize_text_from_raw_config("Temp 53.4°C.", raw_config),
                "Temp dreiundfünfzig Komma vier Grad.",
            )

    def test_normalizes_preview_text_from_unsaved_sectioned_raw_config(self) -> None:
        raw_config = {
            SECTION_MARKDOWN: {
                CONF_MARKDOWN_CLEANUP_ENABLED: True,
            },
            SECTION_NUMBERS: {
                CONF_NUMBER_NORMALIZER_ENABLED: True,
                CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
            },
        }

        with (
            patch(
                "custom_components.tts_proxy.normalizer.supported_number_spellout_languages",
                return_value=("de",),
            ),
            patch(
                "custom_components.tts_proxy.normalizer._spellout_number",
                side_effect=_fake_german_number,
            ),
        ):
            self.assertEqual(
                normalize_text_from_raw_config("**3** Punkte", raw_config),
                "drei Punkte",
            )


class DateNormalizerTests(unittest.TestCase):
    """Date Normalizer behavior."""

    def test_german_numeric_dates_render_with_month_names(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Termin 14.05.2026."),
            "Termin vierzehnter Mai zweitausendsechsundzwanzig.",
        )
        self.assertEqual(
            normalizer.normalize("Termin 2026-05-14."),
            "Termin vierzehnter Mai zweitausendsechsundzwanzig.",
        )

    def test_german_spaced_dot_dates_render_with_month_names(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Termin 23. 05.2026."),
            "Termin dreiundzwanzigster Mai zweitausendsechsundzwanzig.",
        )
        self.assertEqual(
            normalizer.normalize("Termin 23. 05. 2026."),
            "Termin dreiundzwanzigster Mai zweitausendsechsundzwanzig.",
        )

    def test_german_dates_after_am_use_dative_ordinal(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Termin am 14.05. um 12 Uhr."),
            "Termin am vierzehnten Mai um 12 Uhr.",
        )

    def test_german_dates_after_der_use_weak_nominative_ordinal(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Der nächste Freitag ist der 14.05.2026."),
            (
                "Der nächste Freitag ist der vierzehnte Mai "
                "zweitausendsechsundzwanzig."
            ),
        )
        self.assertEqual(
            normalizer.normalize("Dieser 15. August 2025 ist frei."),
            "Dieser fünfzehnte August zweitausendfünfundzwanzig ist frei.",
        )

    def test_german_dates_after_oblique_context_use_en_ordinal(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Geplant für den 14.05.2026."),
            "Geplant für den vierzehnten Mai zweitausendsechsundzwanzig.",
        )
        self.assertEqual(
            normalizer.normalize("Seit dem 14.05. läuft es."),
            "Seit dem vierzehnten Mai läuft es.",
        )

    def test_german_dates_after_bare_dative_prepositions_use_em_ordinal(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Gültig ab 14.05."),
            "Gültig ab vierzehntem Mai.",
        )
        self.assertEqual(
            normalizer.normalize("Nach 15. August 2025 prüfen."),
            "Nach fünfzehntem August zweitausendfünfundzwanzig prüfen.",
        )

    def test_german_date_range_uses_context_for_each_date(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Zeitraum von 14.05. bis 15.05."),
            "Zeitraum von vierzehntem Mai bis fünfzehnten Mai.",
        )

    def test_spaced_no_year_dot_dates_are_separate_input_format(self) -> None:
        normalizer = _date_normalizer(
            input_formats=(DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,)
        )

        self.assertEqual(
            normalizer.normalize("Termin 23. 05. um 12 Uhr."),
            "Termin dreiundzwanzigster Mai um 12 Uhr.",
        )

    def test_adjacent_no_year_dot_dates_are_left_unchanged(self) -> None:
        normalizer = _date_normalizer(
            input_formats=(
                DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
                DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,
            )
        )

        text = "Termine 23.05. 27.05. und 23. 05. 27. 05."

        self.assertEqual(normalizer.normalize(text), text)

    def test_separated_no_year_dot_dates_are_normalized(self) -> None:
        normalizer = _date_normalizer(
            input_formats=(
                DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
                DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,
            )
        )

        self.assertEqual(
            normalizer.normalize("Zeitraum 23.05. - 27.05. und 23. 05. bis 27. 05."),
            (
                "Zeitraum dreiundzwanzigster Mai - siebenundzwanzigster Mai "
                "und dreiundzwanzigster Mai bis siebenundzwanzigsten Mai."
            ),
        )

    def test_no_year_dot_date_preserves_sentence_dot_at_line_end(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Termin 14.05.\nWeiter."),
            "Termin vierzehnter Mai.\nWeiter.",
        )

    def test_german_month_name_dates_are_supported(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(
            normalizer.normalize("Termin 15. August 2025."),
            "Termin fünfzehnter August zweitausendfünfundzwanzig.",
        )
        self.assertEqual(
            normalizer.normalize("Termin 15. August."),
            "Termin fünfzehnter August.",
        )

    def test_month_name_date_inside_markdown_bold_is_normalized_before_numbers(
        self,
    ) -> None:
        self.assertEqual(
            normalize_text(
                "**21.\u202fJuli\u202f2026**",
                [],
                _german_number_normalizer(),
                _date_normalizer(input_formats=(DATE_INPUT_FORMAT_DMY_MONTH_NAME,)),
            ),
            "**einundzwanzigster Juli zweitausendsechsundzwanzig**",
        )

    def test_english_us_dates_render_month_first(self) -> None:
        normalizer = _date_normalizer(
            locale="en-US",
            input_formats=(
                DATE_INPUT_FORMAT_MDY_SLASH,
                DATE_INPUT_FORMAT_MDY_MONTH_NAME,
            ),
        )

        self.assertEqual(
            normalizer.normalize("Due March 15, 2026."),
            "Due March fifteenth twenty twenty-six.",
        )
        self.assertEqual(
            normalizer.normalize("Due 03/15/2026."),
            "Due March fifteenth twenty twenty-six.",
        )

    def test_english_gb_dates_render_day_first(self) -> None:
        normalizer = _date_normalizer(
            locale="en-GB",
            input_formats=(
                DATE_INPUT_FORMAT_DMY_SLASH,
                DATE_INPUT_FORMAT_DMY_MONTH_NAME,
            ),
        )

        self.assertEqual(
            normalizer.normalize("Due 15 March 2026."),
            "Due fifteenth of March twenty twenty-six.",
        )
        self.assertEqual(
            normalizer.normalize("Due 15/03/2026."),
            "Due fifteenth of March twenty twenty-six.",
        )

    def test_date_boundaries_skip_decimals_units_versions_and_ips(self) -> None:
        normalizer = _date_normalizer()
        text = (
            "Temp 14.05°C, Preis 14.05 EUR, Version 1.2.3, "
            "IP 192.168.1.1, sensor_14.05."
        )

        self.assertEqual(normalizer.normalize(text), text)

    def test_numeric_fallback_renderer_is_explicit(self) -> None:
        normalizer = _date_normalizer(
            locale="fr-FR",
            renderer=DATE_RENDERER_NUMERIC_FALLBACK,
            input_formats=(DATE_INPUT_FORMAT_DMY_DOT,),
        )

        self.assertEqual(
            normalizer.normalize("Date 14.05.2026."),
            "Date quatorze cinq deux mille vingt-six.",
        )

    def test_defaults_follow_date_locale(self) -> None:
        self.assertEqual(default_date_renderer("de-DE"), DATE_RENDERER_CURATED)
        self.assertEqual(default_date_renderer("fr-FR"), DATE_RENDERER_NUMERIC_FALLBACK)
        self.assertIn(
            DATE_INPUT_FORMAT_DMY_DOT,
            default_date_input_formats("de-DE"),
        )
        self.assertIn(
            DATE_INPUT_FORMAT_DMY_DOT_SPACED,
            default_date_input_formats("de-DE"),
        )
        self.assertNotIn(
            DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,
            default_date_input_formats("de-DE"),
        )
        self.assertIn(
            DATE_INPUT_FORMAT_MDY_SLASH,
            default_date_input_formats("en-US"),
        )
        self.assertIn(
            DATE_INPUT_FORMAT_DMY_SLASH,
            default_date_input_formats("en-GB"),
        )

    def test_parse_date_normalizer_rejects_uncurated_locale_with_curated_renderer(self) -> None:
        with (
            patch(
                "custom_components.tts_proxy.date_normalizer._supported_spellout_languages",
                return_value=("de", "en", "fr"),
            ),
            self.assertRaises(DateNormalizationError),
        ):
            parse_date_normalizer(
                {
                    CONF_DATE_NORMALIZER_ENABLED: True,
                    CONF_DATE_LOCALE: "fr-FR",
                    CONF_DATE_RENDERER: DATE_RENDERER_CURATED,
                    CONF_DATE_INPUT_FORMATS: [DATE_INPUT_FORMAT_DMY_DOT],
                }
            )

    def test_replacement_rules_run_before_date_and_date_before_number_normalizer(self) -> None:
        date_normalizer = _date_normalizer()
        number_normalizer = NumberNormalizer(
            enabled=True,
            language="de",
            converter=lambda value, language: f"NUMBER({value})",
        )
        rules = [
            ReplacementRule("morgen", "14.05.2026"),
        ]

        self.assertEqual(
            normalize_text("Termin morgen um 12 Uhr.", rules, number_normalizer, date_normalizer),
            (
                "Termin vierzehnter Mai zweitausendsechsundzwanzig "
                "um NUMBER(12) Uhr."
            ),
        )


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

    async def test_stream_number_normalizer_can_span_chunks(self) -> None:
        rule = ReplacementRule(
            r"(\d+(?:[,.]\d+)?)\s*°C",
            r"\1 Grad",
            mode=RuleMode.REGEX,
        )

        output = await _collect_stream(
            ["Temp ist 5", "3.", "4", "°", "C."],
            [rule],
            _german_number_normalizer(),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Temp ist dreiundfünfzig Komma vier Grad.")

    async def test_stream_emoji_normalizer_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Super ", "😀", "🔥"],
            [],
            emoji_normalizer=_emoji_normalizer(),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Super, grinsendes gesicht, feuer")

    async def test_stream_date_normalizer_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Termin am 1", "4.0", "5. um 12 Uhr."],
            [],
            None,
            _date_normalizer(),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Termin am vierzehnten Mai um 12 Uhr.")

    async def test_stream_does_not_flush_no_year_date_as_sentence_boundary(self) -> None:
        output = await _collect_stream(
            ["Termin am 14.05. um 12 Uhr."],
            [],
            None,
            _date_normalizer(),
            safety_tail_chars=5,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Termin am vierzehnten Mai um 12 Uhr.")

    async def test_stream_does_not_flush_inside_month_name_date(self) -> None:
        output = await _collect_stream(
            ["Termin am 15. August 2025 um 12 Uhr."],
            [],
            None,
            _date_normalizer(),
            safety_tail_chars=5,
            max_buffer_chars=500,
        )

        self.assertEqual(
            "".join(output),
            "Termin am fünfzehnten August zweitausendfünfundzwanzig um 12 Uhr.",
        )

    async def test_stream_does_not_flush_inside_markdown_wrapped_month_name_date(
        self,
    ) -> None:
        output = await _collect_stream(
            ["**Samstag,\u202f25.\u202fJuli** - **Bedingung:** sonnig."],
            [],
            None,
            _date_normalizer(input_formats=(DATE_INPUT_FORMAT_DMY_MONTH_NAME,)),
            _markdown_normalizer(),
            safety_tail_chars=5,
            max_buffer_chars=500,
        )

        self.assertEqual(
            "".join(output),
            "Samstag,\u202ffünfundzwanzigster Juli - Bedingung: sonnig.",
        )

    async def test_stream_does_not_flush_inside_spaced_dot_date(self) -> None:
        output = await _collect_stream(
            ["Termin am 14. 05. um 12 Uhr."],
            [],
            None,
            _date_normalizer(input_formats=(DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,)),
            safety_tail_chars=5,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Termin am vierzehnten Mai um 12 Uhr.")


class ConfigTests(unittest.TestCase):
    """Proxy Configuration parsing."""

    def test_proxy_config_parses_rules_and_buffers(self) -> None:
        with patch(
            "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
            return_value=("de", "en"),
        ):
            config = parse_proxy_config(
                {
                    "name": "German proxy",
                    CONF_TARGET_TTS_ENTITY: "tts.target",
                    CONF_OUTPUT_LANGUAGE: "de-DE",
                    CONF_REPLACEMENT_RULES: [
                        {
                            RULE_NAME: "Energy unit",
                            RULE_ENABLED: True,
                            RULE_MODE: RULE_MODE_LITERAL,
                            RULE_FIND: "kWh",
                            RULE_REPLACE: "Kilowattstunden",
                            RULE_IGNORE_CASE: False,
                        }
                    ],
                    CONF_EMOJI_NORMALIZER_ENABLED: True,
                    CONF_EMOJI_HANDLING: EMOJI_HANDLING_SPELLOUT,
                    CONF_EMOJI_LANGUAGE: "de",
                    CONF_NUMBER_NORMALIZER_ENABLED: False,
                    CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
                    CONF_SAFETY_TAIL_CHARS: 64,
                    CONF_MAX_BUFFER_CHARS: 500,
                }
            )

        self.assertEqual(config.name, "German proxy")
        self.assertEqual(config.target_tts_entity, "tts.target")
        self.assertEqual(config.output_language, "de-DE")
        self.assertEqual(len(config.rules), 1)
        self.assertEqual(config.rules[0].name, "Energy unit")
        self.assertFalse(config.markdown_normalizer.enabled)
        self.assertTrue(config.emoji_normalizer.enabled)
        self.assertEqual(config.emoji_normalizer.handling, EMOJI_HANDLING_SPELLOUT)
        self.assertEqual(config.emoji_normalizer.language, "de")
        self.assertFalse(config.number_normalizer.enabled)
        self.assertEqual(config.number_normalizer.language, "de")
        self.assertEqual(config.safety_tail_chars, 64)
        self.assertEqual(config.max_buffer_chars, 500)

    def test_buffer_limit_must_exceed_safety_tail(self) -> None:
        with self.assertRaises(ValueError):
            validate_streaming_buffer_config(64, 64)

    def test_missing_required_config_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_proxy_config(
                {
                    CONF_TARGET_TTS_ENTITY: None,
                    CONF_OUTPUT_LANGUAGE: "de-DE",
                }
            )

    def test_preview_text_is_not_serialized(self) -> None:
        config = serializable_config(
            {
                "name": "German proxy",
                CONF_TARGET_TTS_ENTITY: "tts.target",
                CONF_OUTPUT_LANGUAGE: "de-DE",
                CONF_PREVIEW_TEXT: "Temp 53.4°C.",
            }
        )

        self.assertNotIn(CONF_PREVIEW_TEXT, config)

    def test_serializable_config_flattens_form_sections(self) -> None:
        with patch(
            "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
            return_value=("de", "en"),
        ):
            config = serializable_config(
                {
                    "name": "German proxy",
                    CONF_TARGET_TTS_ENTITY: "tts.target",
                    SECTION_GENERAL: {
                        CONF_OUTPUT_LANGUAGE: "de-DE",
                    },
                    SECTION_MARKDOWN: {
                        CONF_MARKDOWN_CLEANUP_ENABLED: True,
                        CONF_MARKDOWN_STRIP_EMPHASIS: True,
                        CONF_MARKDOWN_STRIP_LINKS: True,
                        CONF_MARKDOWN_STRIP_TABLES: False,
                    },
                    SECTION_EMOJI: {
                        CONF_EMOJI_NORMALIZER_ENABLED: True,
                        CONF_EMOJI_HANDLING: EMOJI_HANDLING_REMOVE,
                        CONF_EMOJI_LANGUAGE: "",
                    },
                    SECTION_NUMBERS: {
                        CONF_NUMBER_NORMALIZER_ENABLED: False,
                        CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
                    },
                }
            )

        self.assertEqual(config[CONF_OUTPUT_LANGUAGE], "de-DE")
        self.assertTrue(config[CONF_MARKDOWN_CLEANUP_ENABLED])
        self.assertTrue(config[CONF_MARKDOWN_STRIP_EMPHASIS])
        self.assertTrue(config[CONF_MARKDOWN_STRIP_LINKS])
        self.assertFalse(config[CONF_MARKDOWN_STRIP_TABLES])
        self.assertTrue(config[CONF_EMOJI_NORMALIZER_ENABLED])
        self.assertEqual(config[CONF_EMOJI_HANDLING], EMOJI_HANDLING_REMOVE)
        self.assertNotIn(SECTION_GENERAL, config)
        self.assertNotIn(SECTION_MARKDOWN, config)
        self.assertNotIn(SECTION_EMOJI, config)
        self.assertNotIn(SECTION_NUMBERS, config)

    def test_serializable_config_converts_legacy_rule_fields(self) -> None:
        config = serializable_config(
            {
                "name": "German proxy",
                CONF_TARGET_TTS_ENTITY: "tts.target",
                CONF_OUTPUT_LANGUAGE: "de-DE",
                CONF_REPLACEMENT_RULES: [
                    {
                        RULE_NAME: "Energy unit",
                        RULE_ENABLED: False,
                        RULE_MODE: RULE_MODE_LITERAL,
                        RULE_FIND: "kwh",
                        RULE_REPLACE: "Kilowattstunden",
                        RULE_IGNORE_CASE: False,
                    }
                ],
            }
        )

        [rule] = config[CONF_REPLACEMENT_RULES]
        self.assertEqual(rule[RULE_NAME], "Energy unit")
        self.assertNotIn(RULE_ENABLED, rule)
        self.assertNotIn(RULE_IGNORE_CASE, rule)
        self.assertTrue(rule[RULE_DISABLED])
        self.assertTrue(rule[RULE_CASE_SENSITIVE])

    def test_form_defaults_converts_legacy_rule_fields_without_validation(self) -> None:
        defaults = form_defaults(
            {
                CONF_PREVIEW_TEXT: "Temp 53.4°C.",
                CONF_REPLACEMENT_RULES: [
                    {
                        RULE_NAME: "Broken regex",
                        RULE_ENABLED: False,
                        RULE_MODE: RULE_MODE_REGEX,
                        RULE_FIND: "(",
                        RULE_REPLACE: "",
                        RULE_IGNORE_CASE: False,
                    }
                ],
            }
        )

        [rule] = defaults[CONF_REPLACEMENT_RULES]
        self.assertNotIn(CONF_PREVIEW_TEXT, defaults)
        self.assertEqual(rule[RULE_NAME], "Broken regex")
        self.assertNotIn(RULE_ENABLED, rule)
        self.assertNotIn(RULE_IGNORE_CASE, rule)
        self.assertEqual(rule[RULE_FIND], "(")
        self.assertTrue(rule[RULE_DISABLED])
        self.assertTrue(rule[RULE_CASE_SENSITIVE])


class PreviewTests(unittest.TestCase):
    """Normalization Preview payload behavior."""

    def test_successful_preview_payload_is_not_an_error(self) -> None:
        payload = preview_event_payload(
            "Dies ist ein Test mit 34.54°C",
            "Dies ist ein Test mit vierunddreißig Komma fünf vier Grad",
        )

        self.assertNotIn("error", payload)
        self.assertEqual(payload["domain"], "sensor")
        self.assertEqual(
            payload["state"],
            "Dies ist ein Test mit vierunddreißig Komma fünf vier Grad",
        )


if __name__ == "__main__":
    unittest.main()
