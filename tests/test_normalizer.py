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
    CONF_DATE_STANDALONE_YEAR_MAX,
    CONF_DATE_STANDALONE_YEAR_MIN,
    CONF_DATE_STANDALONE_YEARS_ENABLED,
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
    CONF_NUMBER_ALLOW_GROUPED_NUMBERS,
    CONF_NUMBER_NORMALIZER_ENABLED,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_OUTPUT_LANGUAGE,
    CONF_PREVIEW_TEXT,
    CONF_REPLACEMENT_RULES,
    CONF_SAFETY_TAIL_CHARS,
    CONF_TEXT_CLEANUP_REPLACE_LINE_BREAKS,
    CONF_TIME_CLOCK_TIMES_ENABLED,
    CONF_TIME_DURATIONS_ENABLED,
    CONF_TIME_LOCALE,
    CONF_TIME_NORMALIZER_ENABLED,
    CONF_TIME_RANGES_ENABLED,
    CONF_UNIT_LOCALE,
    CONF_UNIT_NORMALIZER_ENABLED,
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
    SECTION_DATES,
    SECTION_EMOJI,
    SECTION_MARKDOWN,
    SECTION_NUMBERS,
    SECTION_TEXT_CLEANUP,
    SECTION_TIME,
    SECTION_UNITS,
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
    async_prepare_emoji_config,
    async_prepare_emoji_normalizer,
    async_supported_emoji_languages,
    default_emoji_language,
    parse_emoji_normalizer,
)
from custom_components.tts_proxy.markdown_normalizer import MarkdownCleanupNormalizer
from custom_components.tts_proxy.text_cleanup_normalizer import TextCleanupNormalizer
from custom_components.tts_proxy.time_normalizer import (
    TimeNormalizationError,
    TimeNormalizer,
    default_time_locale,
    parse_time_normalizer,
    supported_time_locales,
)
from custom_components.tts_proxy.unit_normalizer import (
    UnitNormalizationError,
    UnitNormalizer,
    default_unit_locale,
    parse_unit_normalizer,
    supported_unit_locales,
)
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
        -6: "minus sechs",
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
        1342: "eintausenddreihundertzweiundvierzig",
        2026: "zweitausendsechsundzwanzig",
        "0.5": "null Komma fünf",
        "0.7": "null Komma sieben",
        "0.9": "null Komma neun",
        "53.4": "dreiundfünfzig Komma vier",
        "20222.2": "zwanzigtausendzweihundertzweiundzwanzig Komma zwei",
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
        ("de", "year", 1942): "neunzehnhundertzweiundvierzig",
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


def _fake_time_number(value: int, language: str, purpose: str) -> str:
    """Return spellout values used by Time Normalizer tests."""
    values = {
        ("de", "cardinal", 0): "null",
        ("de", "cardinal", 1): "eins",
        ("de", "cardinal", 2): "zwei",
        ("de", "cardinal", 5): "fünf",
        ("de", "cardinal", 8): "acht",
        ("de", "cardinal", 12): "zwölf",
        ("de", "cardinal", 13): "dreizehn",
        ("de", "cardinal", 14): "vierzehn",
        ("de", "cardinal", 15): "fünfzehn",
        ("de", "cardinal", 24): "vierundzwanzig",
        ("de", "cardinal", 30): "dreißig",
        ("de", "cardinal", 40): "vierzig",
        ("de", "cardinal", 59): "neunundfünfzig",
        ("en", "cardinal", 0): "zero",
        ("en", "cardinal", 1): "one",
        ("en", "cardinal", 2): "two",
        ("en", "cardinal", 3): "three",
        ("en", "cardinal", 5): "five",
        ("en", "cardinal", 8): "eight",
        ("en", "cardinal", 12): "twelve",
        ("en", "cardinal", 13): "thirteen",
        ("en", "cardinal", 14): "fourteen",
        ("en", "cardinal", 15): "fifteen",
        ("en", "cardinal", 30): "thirty",
        ("en", "cardinal", 40): "forty",
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


class _FakeHass:
    """Fake Home Assistant object with executor-job tracking."""

    def __init__(self) -> None:
        """Initialize job tracking."""
        self.executor_jobs: list[tuple[object, tuple[object, ...]]] = []

    async def async_add_executor_job(self, target, *args):
        """Run and record an executor job synchronously for tests."""
        self.executor_jobs.append((target, args))
        return target(*args)


def _german_number_normalizer(
    *,
    allow_grouped_numbers: bool = False,
    locale_hint: str = "de",
) -> NumberNormalizer:
    """Return an enabled fake German Number Normalizer."""
    return NumberNormalizer(
        enabled=True,
        language="de",
        converter=_fake_german_number,
        allow_grouped_numbers=allow_grouped_numbers,
        locale_hint=locale_hint,
    )


def _markdown_normalizer(**kwargs: bool) -> MarkdownCleanupNormalizer:
    """Return an enabled Markdown Cleanup Normalizer."""
    return MarkdownCleanupNormalizer(enabled=True, **kwargs)


def _text_cleanup_normalizer(**kwargs: bool) -> TextCleanupNormalizer:
    """Return a Text Cleanup Normalizer."""
    return TextCleanupNormalizer(**kwargs)


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
    standalone_years_enabled: bool = False,
    standalone_year_min: int = 1900,
    standalone_year_max: int = 2099,
) -> DateNormalizer:
    """Return an enabled fake Date Normalizer."""
    return DateNormalizer(
        enabled=True,
        locale=locale,
        renderer=renderer,
        input_formats=input_formats,
        standalone_years_enabled=standalone_years_enabled,
        standalone_year_min=standalone_year_min,
        standalone_year_max=standalone_year_max,
        converter=_fake_date_number,
    )


def _unit_normalizer(
    *,
    locale: str = "de-DE",
    allow_grouped_numbers: bool = False,
    number_locale_hint: str = "",
) -> UnitNormalizer:
    """Return an enabled Unit Normalizer."""
    return UnitNormalizer(
        enabled=True,
        locale=locale,
        allow_grouped_numbers=allow_grouped_numbers,
        number_locale_hint=number_locale_hint,
    )


def _time_normalizer(
    *,
    locale: str = "de-DE",
    clock_times_enabled: bool = True,
    time_ranges_enabled: bool = True,
    durations_enabled: bool = False,
) -> TimeNormalizer:
    """Return an enabled fake Time Normalizer."""
    return TimeNormalizer(
        enabled=True,
        locale=locale,
        clock_times_enabled=clock_times_enabled,
        time_ranges_enabled=time_ranges_enabled,
        durations_enabled=durations_enabled,
        converter=_fake_time_number,
    )


async def _collect_stream(
    values: list[str],
    rules: list[ReplacementRule],
    number_normalizer: NumberNormalizer | None = None,
    date_normalizer: DateNormalizer | None = None,
    markdown_normalizer: MarkdownCleanupNormalizer | None = None,
    text_cleanup_normalizer: TextCleanupNormalizer | None = None,
    time_normalizer: TimeNormalizer | None = None,
    unit_normalizer: UnitNormalizer | None = None,
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
            text_cleanup_normalizer=text_cleanup_normalizer,
            time_normalizer=time_normalizer,
            unit_normalizer=unit_normalizer,
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


class TextCleanupTests(unittest.TestCase):
    """Text Cleanup Normalizer behavior."""

    def test_optionally_replaces_line_breaks_with_spaces(self) -> None:
        text = "Heute\nMorgen\r\n\tÜbermorgen\rFertig"

        self.assertEqual(
            normalize_text(
                text,
                [],
                text_cleanup_normalizer=_text_cleanup_normalizer(
                    replace_line_breaks=True,
                ),
            ),
            "Heute Morgen Übermorgen Fertig",
        )

    def test_line_break_replacement_runs_after_markdown_cleanup(self) -> None:
        text = "\n".join(
            [
                "- **Heute**",
                "- Morgen",
                "| Tag | Höchst |",
                "| --- | --- |",
                "| 21. Juli | 22 °C |",
            ]
        )

        self.assertEqual(
            normalize_text(
                text,
                [],
                markdown_normalizer=_markdown_normalizer(),
                text_cleanup_normalizer=_text_cleanup_normalizer(
                    replace_line_breaks=True,
                ),
            ),
            "Heute Morgen Tag. Höchst. 21. Juli. 22 °C.",
        )

    def test_text_cleanup_runs_without_markdown_cleanup(self) -> None:
        self.assertEqual(
            normalize_text(
                "**Heute**\nMorgen",
                [],
                text_cleanup_normalizer=_text_cleanup_normalizer(
                    replace_line_breaks=True,
                ),
            ),
            "**Heute** Morgen",
        )

    def test_text_cleanup_preserves_provider_control_tags(self) -> None:
        self.assertEqual(
            normalize_text(
                "[very\nquiet]\nText <tag\nvalue=\"1\"/>",
                [],
                text_cleanup_normalizer=_text_cleanup_normalizer(
                    replace_line_breaks=True,
                ),
            ),
            "[very\nquiet] Text <tag\nvalue=\"1\"/>",
        )

    def test_normalizes_preview_text_from_unsaved_sectioned_text_cleanup_config(
        self,
    ) -> None:
        raw_config = {
            SECTION_TEXT_CLEANUP: {
                CONF_TEXT_CLEANUP_REPLACE_LINE_BREAKS: True,
            },
        }

        self.assertEqual(
            normalize_text_from_raw_config("Heute\nMorgen", raw_config),
            "Heute Morgen",
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


class AsyncEmojiPreparationTests(unittest.IsolatedAsyncioTestCase):
    """Emoji backend preparation behavior."""

    async def test_supported_emoji_languages_runs_in_executor(self) -> None:
        hass = _FakeHass()

        with patch(
            "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
            return_value=("de", "en"),
        ) as supported:
            self.assertEqual(
                await async_supported_emoji_languages(hass),
                ("de", "en"),
            )

        self.assertEqual(hass.executor_jobs, [(supported, ())])

    async def test_prepare_spellout_config_runs_backend_load_in_executor(self) -> None:
        hass = _FakeHass()
        raw_config = {
            CONF_EMOJI_NORMALIZER_ENABLED: True,
            CONF_EMOJI_HANDLING: EMOJI_HANDLING_SPELLOUT,
            CONF_EMOJI_LANGUAGE: "de",
        }

        with patch(
            "custom_components.tts_proxy.emoji_normalizer._prepare_emoji_backend",
        ) as prepare:
            await async_prepare_emoji_config(hass, raw_config)

        prepare.assert_called_once_with(("de", "en"))
        self.assertEqual(hass.executor_jobs, [(prepare, (("de", "en"),))])

    async def test_prepare_remove_config_imports_backend_in_executor(self) -> None:
        hass = _FakeHass()
        raw_config = {
            CONF_EMOJI_NORMALIZER_ENABLED: True,
            CONF_EMOJI_HANDLING: EMOJI_HANDLING_REMOVE,
            CONF_EMOJI_LANGUAGE: "",
        }

        with patch(
            "custom_components.tts_proxy.emoji_normalizer._prepare_emoji_backend",
        ) as prepare:
            await async_prepare_emoji_config(hass, raw_config)

        prepare.assert_called_once_with(())
        self.assertEqual(hass.executor_jobs, [(prepare, ((),))])

    async def test_prepare_disabled_config_does_not_use_executor(self) -> None:
        hass = _FakeHass()

        await async_prepare_emoji_config(
            hass,
            {CONF_EMOJI_NORMALIZER_ENABLED: False},
        )

        self.assertEqual(hass.executor_jobs, [])

    async def test_prepare_parsed_normalizer_runs_backend_load_in_executor(self) -> None:
        hass = _FakeHass()
        normalizer = EmojiNormalizer(
            enabled=True,
            handling=EMOJI_HANDLING_SPELLOUT,
            language="de",
        )

        with patch(
            "custom_components.tts_proxy.emoji_normalizer._prepare_emoji_backend",
        ) as prepare:
            await async_prepare_emoji_normalizer(hass, normalizer)

        prepare.assert_called_once_with(("de", "en"))
        self.assertEqual(hass.executor_jobs, [(prepare, (("de", "en"),))])


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

    def test_spells_numbers_with_unicode_minus_signs(self) -> None:
        self.assertEqual(
            normalize_text(
                "Werte –6, −5 und —1.",
                [],
                _german_number_normalizer(),
            ),
            "Werte minus sechs, minus fünf und minus eins.",
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

    def test_spells_grouped_numbers_when_enabled(self) -> None:
        def show_value(value: int | str, language: str) -> str:
            return f"{language}:{value}"

        normalizer = NumberNormalizer(
            enabled=True,
            language="de",
            converter=show_value,
            allow_grouped_numbers=True,
            locale_hint="de",
        )

        self.assertEqual(
            normalize_text(
                "Werte 20\u202f222,2, 20.222,2, 20,222.2 und 1 234.",
                [],
                normalizer,
            ),
            "Werte de:20222.2, de:20222.2, de:20222.2 und de:1234.",
        )

    def test_ambiguous_grouped_numbers_use_locale_hint(self) -> None:
        def show_value(value: int | str, language: str) -> str:
            return f"{language}:{value}"

        german = NumberNormalizer(
            enabled=True,
            language="de",
            converter=show_value,
            allow_grouped_numbers=True,
            locale_hint="de",
        )
        english = NumberNormalizer(
            enabled=True,
            language="en",
            converter=show_value,
            allow_grouped_numbers=True,
            locale_hint="en",
        )

        self.assertEqual(
            normalize_text("Werte 1.342 und 1,342.", [], german),
            "Werte de:1342 und de:1.342.",
        )
        self.assertEqual(
            normalize_text("Values 1.342 and 1,342.", [], english),
            "Values en:1.342 and en:1342.",
        )

    def test_invalid_grouped_numbers_and_ipv4_are_not_partially_spelled(self) -> None:
        def show_value(value: int | str, language: str) -> str:
            return f"<{value}>"

        normalizer = NumberNormalizer(
            enabled=True,
            language="de",
            converter=show_value,
            allow_grouped_numbers=True,
            locale_hint="de",
        )
        text = (
            "IP 192.168.1.1, Version 1.2.3, "
            "Mixed 1 234\u202f567 und Decimal 0.001."
        )

        self.assertEqual(
            normalize_text(text, [], normalizer),
            (
                "IP 192.168.1.1, Version 1.2.3, "
                "Mixed 1 234\u202f567 und Decimal <0.001>."
            ),
        )

    def test_adjacent_plain_numbers_stay_separate_with_grouping_enabled(self) -> None:
        def show_value(value: int | str, language: str) -> str:
            return f"<{value}>"

        normalizer = NumberNormalizer(
            enabled=True,
            language="de",
            converter=show_value,
            allow_grouped_numbers=True,
            locale_hint="de",
        )

        self.assertEqual(
            normalize_text("Werte 12 34 und 2026 13.", [], normalizer),
            "Werte <12> <34> und <2026> <13>.",
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


class UnitNormalizerTests(unittest.TestCase):
    """Unit Normalizer behavior."""

    def test_disabled_normalizer_leaves_units_unchanged(self) -> None:
        normalizer = UnitNormalizer(enabled=False, locale="de-DE")

        self.assertEqual(normalizer.normalize("Temp 30°C."), "Temp 30°C.")

    def test_german_units_run_before_number_normalizer(self) -> None:
        self.assertEqual(
            normalize_text(
                "Temp 30°C.",
                [],
                _german_number_normalizer(),
                unit_normalizer=_unit_normalizer(locale="de-DE"),
            ),
            "Temp dreißig Grad.",
        )

    def test_german_temperature_and_percent_units(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Temp 25°C und -5°F, Wolken 92%."),
            "Temp 25 Grad und -5 Grad Fahrenheit, Wolken 92 Prozent.",
        )

    def test_units_support_unicode_minus_signs(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("(–6 W), (−1 kWh), (—2°F)"),
            "(–6 Watt), (−1 Kilowattstunde), (—2 Grad Fahrenheit)",
        )

    def test_unicode_minus_units_run_before_number_normalizer(self) -> None:
        self.assertEqual(
            normalize_text(
                "(–6 W), (0,9 kWh)",
                [],
                _german_number_normalizer(),
                unit_normalizer=_unit_normalizer(locale="de-DE"),
            ),
            "(minus sechs Watt), (null Komma neun Kilowattstunden)",
        )

    def test_german_power_and_energy_units_with_common_aliases(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Verbrauch 1kWh, 2 KWh, 3kwH, 30w und 4 kW."),
            (
                "Verbrauch 1 Kilowattstunde, 2 Kilowattstunden, "
                "3 Kilowattstunden, 30 Watt und 4 Kilowatt."
            ),
        )

    def test_german_smart_home_unit_catalog(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize(
                "Wind 12km/h, 14kmh, 3m/s; Druck 990hPa, 1000mbar, "
                "1bar; Licht 20lx, 300lm; Daten 4MB, 1GB, 2Mbit/s."
            ),
            (
                "Wind 12 Kilometer pro Stunde, 14 Kilometer pro Stunde, "
                "3 Meter pro Sekunde; Druck 990 Hektopascal, 1000 Millibar, "
                "1 Bar; Licht 20 Lux, 300 Lumen; Daten 4 Megabyte, "
                "1 Gigabyte, 2 Megabit pro Sekunde."
            ),
        )

    def test_english_temperature_uses_locale_normal_scale(self) -> None:
        us = _unit_normalizer(locale="en-US")
        gb = _unit_normalizer(locale="en-GB")

        self.assertEqual(
            us.normalize("Temp 1°F, 2°F, 1°C, 2°C."),
            "Temp 1 degree, 2 degrees, 1 degree Celsius, 2 degrees Celsius.",
        )
        self.assertEqual(
            gb.normalize("Temp 1°C, 2°C, 1°F, 2°F."),
            "Temp 1 degree, 2 degrees, 1 degree Fahrenheit, 2 degrees Fahrenheit.",
        )

    def test_english_units_use_singular_and_plural_forms(self) -> None:
        normalizer = _unit_normalizer(locale="en-GB")

        self.assertEqual(
            normalizer.normalize("Energy 1kWh, 2kWh; Power -1W, 2W."),
            "Energy 1 kilowatt hour, 2 kilowatt hours; Power -1 watt, 2 watts.",
        )

    def test_generic_fallback_keeps_temperature_scale_explicit(self) -> None:
        normalizer = _unit_normalizer(locale="fr-FR")

        self.assertEqual(
            normalizer.normalize("Temp 1°C, 2°F, 3kWh."),
            "Temp 1 degree Celsius, 2 degrees Fahrenheit, 3 kilowatt hours.",
        )

    def test_unit_detection_uses_strict_boundaries(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")
        text = "Weg 5m, Temp 25C, sensor_30W, abc30W, 30Wert, IP 192.168.1.1W."

        self.assertEqual(normalizer.normalize(text), text)

    def test_unit_detection_skips_structured_numbers(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")
        text = "Version 1.2.3W, IP 192.168.1.1W, Wert 1,2,3kWh."

        self.assertEqual(normalizer.normalize(text), text)

    def test_unit_detection_skips_grouped_numbers(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Leistung 1.000W, 1,000kWh und 0.001W."),
            "Leistung 1.000W, 1,000kWh und 0.001 Watt.",
        )

    def test_unit_detection_uses_grouped_number_setting(self) -> None:
        normalizer = _unit_normalizer(
            locale="de-DE",
            allow_grouped_numbers=True,
            number_locale_hint="de",
        )

        self.assertEqual(
            normalizer.normalize(
                "Energie 20\u202f222,2\u202fkWh, 1.342kWh und 1,000kWh."
            ),
            (
                "Energie 20\u202f222,2 Kilowattstunden, "
                "1.342 Kilowattstunden und 1,000 Kilowattstunde."
            ),
        )

    def test_unit_normalizer_keeps_leading_zero_number_text(self) -> None:
        normalizer = _unit_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Werte 007W und 0007.1234W."),
            "Werte 007 Watt und 0007.1234 Watt.",
        )

    def test_date_normalizer_runs_before_unit_normalizer(self) -> None:
        self.assertEqual(
            normalize_text(
                "Termin 14.05.2026, Messung 14.05°C.",
                [],
                date_normalizer=_date_normalizer(),
                unit_normalizer=_unit_normalizer(locale="de-DE"),
            ),
            (
                "Termin vierzehnter Mai zweitausendsechsundzwanzig, "
                "Messung 14.05 Grad."
            ),
        )

    def test_provider_control_tags_are_not_unit_normalized(self) -> None:
        self.assertEqual(
            normalize_text(
                "[30°C] Temp 30°C <say-as value=\"30°C\"/>",
                [],
                unit_normalizer=_unit_normalizer(locale="de-DE"),
            ),
            "[30°C] Temp 30 Grad <say-as value=\"30°C\"/>",
        )

    def test_parse_unit_normalizer_defaults_locale_from_output_language(self) -> None:
        normalizer = parse_unit_normalizer(
            {
                CONF_OUTPUT_LANGUAGE: "de-DE",
                CONF_UNIT_NORMALIZER_ENABLED: True,
            }
        )

        self.assertTrue(normalizer.enabled)
        self.assertEqual(normalizer.locale, "de-DE")

    def test_parse_unit_normalizer_rejects_missing_locale_when_enabled(self) -> None:
        with self.assertRaises(UnitNormalizationError):
            parse_unit_normalizer({CONF_UNIT_NORMALIZER_ENABLED: True})

    def test_default_unit_locale_normalizes_output_language(self) -> None:
        self.assertEqual(default_unit_locale("en_us"), "en-US")

    def test_supported_unit_locales_include_output_languages(self) -> None:
        self.assertIn("sv-SE", supported_unit_locales(("sv-SE",)))

    def test_normalizes_preview_text_from_unsaved_sectioned_unit_config(self) -> None:
        raw_config = {
            SECTION_UNITS: {
                CONF_UNIT_NORMALIZER_ENABLED: True,
                CONF_UNIT_LOCALE: "de-DE",
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
                normalize_text_from_raw_config("Temp 30°C.", raw_config),
                "Temp dreißig Grad.",
            )

    def test_normalizes_grouped_number_units_from_unsaved_config(self) -> None:
        raw_config = {
            SECTION_UNITS: {
                CONF_UNIT_NORMALIZER_ENABLED: True,
                CONF_UNIT_LOCALE: "de-DE",
            },
            SECTION_NUMBERS: {
                CONF_NUMBER_NORMALIZER_ENABLED: True,
                CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
                CONF_NUMBER_ALLOW_GROUPED_NUMBERS: True,
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
                normalize_text_from_raw_config("Hausverbrauch 20\u202f222,2\u202fkWh.", raw_config),
                (
                    "Hausverbrauch "
                    "zwanzigtausendzweihundertzweiundzwanzig Komma zwei "
                    "Kilowattstunden."
                ),
            )


class TimeNormalizerTests(unittest.TestCase):
    """Time Normalizer behavior."""

    def test_disabled_normalizer_leaves_times_unchanged(self) -> None:
        normalizer = TimeNormalizer(enabled=False, locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Termin 13:40 Uhr."),
            "Termin 13:40 Uhr.",
        )

    def test_german_clock_times_render_with_uhr(self) -> None:
        normalizer = _time_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Termine 13:40, 13:40 Uhr, 13:40Uhr."),
            "Termine dreizehn Uhr vierzig, dreizehn Uhr vierzig, dreizehn Uhr vierzig.",
        )
        self.assertEqual(
            normalizer.normalize("Start 08:05, Ende 12:00, Wecker 1:05 Uhr."),
            "Start acht Uhr fünf, Ende zwölf Uhr, Wecker ein Uhr fünf.",
        )

    def test_duration_detection_is_disabled_by_default(self) -> None:
        normalizer = _time_normalizer(locale="de-DE")

        self.assertEqual(
            normalizer.normalize("Dauer 1:30h und 01:30:00."),
            "Dauer 1:30h und 01:30:00.",
        )

    def test_english_clock_times_render_with_optional_ampm(self) -> None:
        normalizer = _time_normalizer(locale="en-US")

        self.assertEqual(
            normalizer.normalize("Times 13:40, 08:05, 12:00."),
            "Times thirteen forty, eight oh five, twelve.",
        )
        self.assertEqual(
            normalizer.normalize("Times 01:40pm, 1:05 a.m., 12:00 PM."),
            "Times one forty PM, one oh five AM, twelve PM.",
        )

    def test_german_durations_render_components(self) -> None:
        normalizer = _time_normalizer(locale="de-DE", durations_enabled=True)

        self.assertEqual(
            normalizer.normalize("Dauer 01:30:00, 00:05:00 und 00:00:30."),
            "Dauer eine Stunde dreißig Minuten, fünf Minuten und dreißig Sekunden.",
        )
        self.assertEqual(
            normalizer.normalize("Dauer 02:01:05, 24:00h und 01:00h."),
            (
                "Dauer zwei Stunden eine Minute fünf Sekunden, "
                "vierundzwanzig Stunden und eine Stunde."
            ),
        )

    def test_english_durations_render_components(self) -> None:
        normalizer = _time_normalizer(locale="en-GB", durations_enabled=True)

        self.assertEqual(
            normalizer.normalize("Duration 1:30h and 02:01:05."),
            "Duration one hour thirty minutes and two hours one minute five seconds.",
        )

    def test_time_ranges_render_between_clock_times(self) -> None:
        german = _time_normalizer(locale="de-DE")
        english = _time_normalizer(locale="en-US")

        self.assertEqual(
            german.normalize("Termin 14:30-15:30, 14:30 - 15:30 Uhr."),
            (
                "Termin vierzehn Uhr dreißig bis fünfzehn Uhr dreißig, "
                "vierzehn Uhr dreißig bis fünfzehn Uhr dreißig."
            ),
        )
        self.assertEqual(
            english.normalize("Times 2:30-3:30pm, 2:30pm-3:30pm."),
            "Times two thirty to three thirty PM, two thirty PM to three thirty PM.",
        )

    def test_range_detection_can_be_disabled_independently(self) -> None:
        normalizer = _time_normalizer(locale="de-DE", time_ranges_enabled=False)

        self.assertEqual(
            normalizer.normalize("Termin 14:30-15:30."),
            "Termin vierzehn Uhr dreißig-fünfzehn Uhr dreißig.",
        )

    def test_duration_and_clock_detection_use_strict_boundaries(self) -> None:
        def fail_on_call(value: int, language: str, purpose: str) -> str:
            raise AssertionError(f"Unexpected conversion: {value} {language} {purpose}")

        normalizer = TimeNormalizer(
            enabled=True,
            locale="de-DE",
            durations_enabled=True,
            converter=fail_on_call,
        )
        text = (
            "Ungültig 24:00 Uhr, 13:40:05 Uhr, 16:9, sensor_13:40, "
            "ID13:40, 01:30:00 Uhr, 192.168.1.1:8123."
        )

        self.assertEqual(normalizer.normalize(text), text)

    def test_time_normalizer_runs_after_date_and_before_unit_and_number(self) -> None:
        self.assertEqual(
            normalize_text(
                "Termin 14.05.2026 um 13:40 Uhr mit 30W.",
                [],
                _german_number_normalizer(),
                _date_normalizer(),
                time_normalizer=_time_normalizer(locale="de-DE"),
                unit_normalizer=_unit_normalizer(locale="de-DE"),
            ),
            (
                "Termin vierzehnter Mai zweitausendsechsundzwanzig "
                "um dreizehn Uhr vierzig mit dreißig Watt."
            ),
        )

    def test_provider_control_tags_are_not_time_normalized(self) -> None:
        self.assertEqual(
            normalize_text(
                "[13:40] Start 13:40 <break time=\"13:40\"/>",
                [],
                time_normalizer=_time_normalizer(locale="de-DE"),
            ),
            "[13:40] Start dreizehn Uhr vierzig <break time=\"13:40\"/>",
        )

    def test_parse_time_normalizer_defaults_locale_from_output_language(self) -> None:
        normalizer = parse_time_normalizer(
            {
                CONF_OUTPUT_LANGUAGE: "en_us",
                CONF_TIME_NORMALIZER_ENABLED: True,
            }
        )

        self.assertTrue(normalizer.enabled)
        self.assertEqual(normalizer.locale, "en-US")

    def test_parse_time_normalizer_rejects_unknown_locale_when_enabled(self) -> None:
        with self.assertRaises(TimeNormalizationError):
            parse_time_normalizer(
                {
                    CONF_TIME_NORMALIZER_ENABLED: True,
                    CONF_TIME_LOCALE: "fr-FR",
                }
            )

    def test_time_locale_defaults_are_curated(self) -> None:
        self.assertEqual(default_time_locale("de_DE"), "de-DE")
        self.assertEqual(default_time_locale("fr-FR"), "")
        self.assertIn("de-DE", supported_time_locales())
        self.assertIn("en-US", supported_time_locales())

    def test_normalizes_preview_text_from_unsaved_sectioned_time_config(self) -> None:
        raw_config = {
            SECTION_TIME: {
                CONF_TIME_NORMALIZER_ENABLED: True,
                CONF_TIME_LOCALE: "de-DE",
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
            patch(
                "custom_components.tts_proxy.time_normalizer._spellout_number_as",
                side_effect=_fake_time_number,
            ),
        ):
            self.assertEqual(
                normalize_text_from_raw_config("Start 13:40 Uhr und 30W.", raw_config),
                "Start dreizehn Uhr vierzig und 30W.",
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

    def test_standalone_years_can_be_rendered_as_dates(self) -> None:
        german = _date_normalizer(
            standalone_years_enabled=True,
            standalone_year_min=1900,
            standalone_year_max=1999,
        )
        english = _date_normalizer(
            locale="en-US",
            input_formats=(DATE_INPUT_FORMAT_MDY_MONTH_NAME,),
            standalone_years_enabled=True,
            standalone_year_min=1900,
            standalone_year_max=2050,
        )

        self.assertEqual(
            german.normalize("Das Haus wurde 1942 gebaut."),
            "Das Haus wurde neunzehnhundertzweiundvierzig gebaut.",
        )
        self.assertEqual(
            english.normalize("The forecast starts in 2025."),
            "The forecast starts in twenty twenty-five.",
        )

    def test_standalone_year_detection_is_disabled_by_default(self) -> None:
        normalizer = _date_normalizer()

        self.assertEqual(normalizer.normalize("Seit 1942 aktiv."), "Seit 1942 aktiv.")

    def test_standalone_year_detection_respects_configured_range(self) -> None:
        normalizer = _date_normalizer(
            standalone_years_enabled=True,
            standalone_year_min=1900,
            standalone_year_max=1999,
        )

        self.assertEqual(
            normalizer.normalize("Jahre 1942 und 2025."),
            "Jahre neunzehnhundertzweiundvierzig und 2025.",
        )

    def test_standalone_year_detection_skips_measurements_codes_and_structures(
        self,
    ) -> None:
        normalizer = _date_normalizer(
            input_formats=(),
            standalone_years_enabled=True,
            standalone_year_min=1900,
            standalone_year_max=2099,
        )
        text = (
            "Leistung 1942 W, Leistung 1942 Watt, Energie 1942 kWh, "
            "Temperatur 2025 Grad, Anteil 2025 Prozent, Fehlercode 1942, "
            "Wind 2025 kmh, Netzwerk 2025 Mbit/s, Speicher 2025 MB, "
            "Druck 2025 bar, PIN 1942, Version v2025.1, Datum 2026-07-25, "
            "IP 192.168.1.1, sensor_2025."
        )

        self.assertEqual(normalizer.normalize(text), text)

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

    def test_parse_date_normalizer_allows_standalone_years_without_input_formats(
        self,
    ) -> None:
        with patch(
            "custom_components.tts_proxy.date_normalizer._supported_spellout_languages",
            return_value=("de", "en"),
        ):
            normalizer = parse_date_normalizer(
                {
                    CONF_DATE_NORMALIZER_ENABLED: True,
                    CONF_DATE_LOCALE: "de-DE",
                    CONF_DATE_RENDERER: DATE_RENDERER_CURATED,
                    CONF_DATE_INPUT_FORMATS: [],
                    CONF_DATE_STANDALONE_YEARS_ENABLED: True,
                    CONF_DATE_STANDALONE_YEAR_MIN: 1900,
                    CONF_DATE_STANDALONE_YEAR_MAX: 1999,
                }
            )

        self.assertTrue(normalizer.standalone_years_enabled)
        self.assertEqual(normalizer.input_formats, ())

    def test_parse_date_normalizer_rejects_invalid_standalone_year_range(self) -> None:
        with (
            patch(
                "custom_components.tts_proxy.date_normalizer._supported_spellout_languages",
                return_value=("de", "en"),
            ),
            self.assertRaises(DateNormalizationError),
        ):
            parse_date_normalizer(
                {
                    CONF_DATE_NORMALIZER_ENABLED: True,
                    CONF_DATE_LOCALE: "de-DE",
                    CONF_DATE_RENDERER: DATE_RENDERER_CURATED,
                    CONF_DATE_INPUT_FORMATS: [DATE_INPUT_FORMAT_DMY_DOT],
                    CONF_DATE_STANDALONE_YEARS_ENABLED: True,
                    CONF_DATE_STANDALONE_YEAR_MIN: 2050,
                    CONF_DATE_STANDALONE_YEAR_MAX: 1900,
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

    async def test_stream_text_cleanup_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Heute\n", "\tMorgen\r", "\nFertig"],
            [],
            text_cleanup_normalizer=_text_cleanup_normalizer(
                replace_line_breaks=True,
            ),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Heute Morgen Fertig")

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

    async def test_stream_standalone_year_normalizer_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Seit 19", "42 aktiv."],
            [],
            None,
            _date_normalizer(
                standalone_years_enabled=True,
                standalone_year_min=1900,
                standalone_year_max=1999,
            ),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual(
            "".join(output),
            "Seit neunzehnhundertzweiundvierzig aktiv.",
        )

    async def test_stream_unit_normalizer_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Temp 3", "0", "°", "C."],
            [],
            _german_number_normalizer(),
            unit_normalizer=_unit_normalizer(locale="de-DE"),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Temp dreißig Grad.")

    async def test_stream_grouped_number_unit_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Haus 20", "\u202f222,2", "\u202fkWh."],
            [],
            _german_number_normalizer(allow_grouped_numbers=True),
            unit_normalizer=_unit_normalizer(
                locale="de-DE",
                allow_grouped_numbers=True,
                number_locale_hint="de",
            ),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual(
            "".join(output),
            "Haus zwanzigtausendzweihundertzweiundzwanzig Komma zwei Kilowattstunden.",
        )

    async def test_stream_time_normalizer_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Start 1", "3:4", "0 Uhr."],
            [],
            time_normalizer=_time_normalizer(locale="de-DE"),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual("".join(output), "Start dreizehn Uhr vierzig.")

    async def test_stream_time_range_normalizer_can_span_chunks(self) -> None:
        output = await _collect_stream(
            ["Termin 14", ":30 - 15", ":30 Uhr."],
            [],
            time_normalizer=_time_normalizer(locale="de-DE"),
            safety_tail_chars=64,
            max_buffer_chars=500,
        )

        self.assertEqual(
            "".join(output),
            "Termin vierzehn Uhr dreißig bis fünfzehn Uhr dreißig.",
        )

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
                    CONF_TIME_NORMALIZER_ENABLED: True,
                    CONF_TIME_LOCALE: "de-DE",
                    CONF_TIME_RANGES_ENABLED: True,
                    CONF_TIME_CLOCK_TIMES_ENABLED: True,
                    CONF_TIME_DURATIONS_ENABLED: False,
                    CONF_UNIT_NORMALIZER_ENABLED: True,
                    CONF_UNIT_LOCALE: "de-DE",
                    CONF_NUMBER_NORMALIZER_ENABLED: False,
                    CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
                    CONF_NUMBER_ALLOW_GROUPED_NUMBERS: True,
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
        self.assertTrue(config.time_normalizer.enabled)
        self.assertEqual(config.time_normalizer.locale, "de-DE")
        self.assertTrue(config.time_normalizer.time_ranges_enabled)
        self.assertTrue(config.time_normalizer.clock_times_enabled)
        self.assertFalse(config.time_normalizer.durations_enabled)
        self.assertTrue(config.unit_normalizer.enabled)
        self.assertEqual(config.unit_normalizer.locale, "de-DE")
        self.assertTrue(config.unit_normalizer.allow_grouped_numbers)
        self.assertFalse(config.number_normalizer.enabled)
        self.assertEqual(config.number_normalizer.language, "de")
        self.assertTrue(config.number_normalizer.allow_grouped_numbers)
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
        with (
            patch(
                "custom_components.tts_proxy.emoji_normalizer.supported_emoji_languages",
                return_value=("de", "en"),
            ),
            patch(
                "custom_components.tts_proxy.date_normalizer._supported_spellout_languages",
                return_value=("de", "en"),
            ),
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
                    SECTION_TEXT_CLEANUP: {
                        CONF_TEXT_CLEANUP_REPLACE_LINE_BREAKS: True,
                    },
                    SECTION_EMOJI: {
                        CONF_EMOJI_NORMALIZER_ENABLED: True,
                        CONF_EMOJI_HANDLING: EMOJI_HANDLING_REMOVE,
                        CONF_EMOJI_LANGUAGE: "",
                    },
                    SECTION_DATES: {
                        CONF_DATE_NORMALIZER_ENABLED: True,
                        CONF_DATE_LOCALE: "de-DE",
                        CONF_DATE_RENDERER: DATE_RENDERER_CURATED,
                        CONF_DATE_INPUT_FORMATS: [DATE_INPUT_FORMAT_DMY_DOT],
                        CONF_DATE_STANDALONE_YEARS_ENABLED: True,
                        CONF_DATE_STANDALONE_YEAR_MIN: 1900,
                        CONF_DATE_STANDALONE_YEAR_MAX: 1999,
                    },
                    SECTION_TIME: {
                        CONF_TIME_NORMALIZER_ENABLED: True,
                        CONF_TIME_LOCALE: "en_us",
                        CONF_TIME_RANGES_ENABLED: True,
                        CONF_TIME_CLOCK_TIMES_ENABLED: False,
                        CONF_TIME_DURATIONS_ENABLED: True,
                    },
                    SECTION_UNITS: {
                        CONF_UNIT_NORMALIZER_ENABLED: True,
                        CONF_UNIT_LOCALE: "en_us",
                    },
                    SECTION_NUMBERS: {
                        CONF_NUMBER_NORMALIZER_ENABLED: False,
                        CONF_NUMBER_SPELLOUT_LANGUAGE: "de",
                        CONF_NUMBER_ALLOW_GROUPED_NUMBERS: True,
                    },
                }
            )

        self.assertEqual(config[CONF_OUTPUT_LANGUAGE], "de-DE")
        self.assertTrue(config[CONF_MARKDOWN_CLEANUP_ENABLED])
        self.assertTrue(config[CONF_MARKDOWN_STRIP_EMPHASIS])
        self.assertTrue(config[CONF_MARKDOWN_STRIP_LINKS])
        self.assertFalse(config[CONF_MARKDOWN_STRIP_TABLES])
        self.assertTrue(config[CONF_TEXT_CLEANUP_REPLACE_LINE_BREAKS])
        self.assertTrue(config[CONF_EMOJI_NORMALIZER_ENABLED])
        self.assertEqual(config[CONF_EMOJI_HANDLING], EMOJI_HANDLING_REMOVE)
        self.assertTrue(config[CONF_DATE_STANDALONE_YEARS_ENABLED])
        self.assertEqual(config[CONF_DATE_STANDALONE_YEAR_MIN], 1900)
        self.assertEqual(config[CONF_DATE_STANDALONE_YEAR_MAX], 1999)
        self.assertTrue(config[CONF_TIME_NORMALIZER_ENABLED])
        self.assertEqual(config[CONF_TIME_LOCALE], "en-US")
        self.assertTrue(config[CONF_TIME_RANGES_ENABLED])
        self.assertFalse(config[CONF_TIME_CLOCK_TIMES_ENABLED])
        self.assertTrue(config[CONF_TIME_DURATIONS_ENABLED])
        self.assertTrue(config[CONF_UNIT_NORMALIZER_ENABLED])
        self.assertEqual(config[CONF_UNIT_LOCALE], "en-US")
        self.assertTrue(config[CONF_NUMBER_ALLOW_GROUPED_NUMBERS])
        self.assertNotIn(SECTION_GENERAL, config)
        self.assertNotIn(SECTION_MARKDOWN, config)
        self.assertNotIn(SECTION_TEXT_CLEANUP, config)
        self.assertNotIn(SECTION_EMOJI, config)
        self.assertNotIn(SECTION_DATES, config)
        self.assertNotIn(SECTION_TIME, config)
        self.assertNotIn(SECTION_UNITS, config)
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
