"""Date normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
import re
from typing import Any

from .const import (
    CONF_DATE_INPUT_FORMATS,
    CONF_DATE_LOCALE,
    CONF_DATE_NORMALIZER_ENABLED,
    CONF_DATE_RENDERER,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_OUTPUT_LANGUAGE,
    DATE_INPUT_FORMAT_DMY_DOT,
    DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
    DATE_INPUT_FORMAT_DMY_DOT_SPACED,
    DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,
    DATE_INPUT_FORMAT_DMY_MONTH_NAME,
    DATE_INPUT_FORMAT_DMY_SLASH,
    DATE_INPUT_FORMAT_DMY_SLASH_NO_YEAR,
    DATE_INPUT_FORMAT_MDY_MONTH_NAME,
    DATE_INPUT_FORMAT_MDY_SLASH,
    DATE_INPUT_FORMAT_MDY_SLASH_NO_YEAR,
    DATE_INPUT_FORMAT_YMD_DASH,
    DATE_RENDERER_CURATED,
    DATE_RENDERER_NUMERIC_FALLBACK,
)

DateNumberConverter = Callable[[int, str, str], str]

_FULL_YEAR_RE = r"(?:19|20)\d{2}"
_DAY_RE = r"(?:[12]\d|3[01]|0?[1-9])"
_MONTH_RE = r"(?:1[0-2]|0?[1-9])"
_SUPPORTED_INPUT_FORMATS = (
    DATE_INPUT_FORMAT_DMY_DOT,
    DATE_INPUT_FORMAT_DMY_DOT_SPACED,
    DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
    DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR,
    DATE_INPUT_FORMAT_DMY_MONTH_NAME,
    DATE_INPUT_FORMAT_DMY_SLASH,
    DATE_INPUT_FORMAT_DMY_SLASH_NO_YEAR,
    DATE_INPUT_FORMAT_MDY_MONTH_NAME,
    DATE_INPUT_FORMAT_MDY_SLASH,
    DATE_INPUT_FORMAT_MDY_SLASH_NO_YEAR,
    DATE_INPUT_FORMAT_YMD_DASH,
)
_SUPPORTED_RENDERERS = (
    DATE_RENDERER_CURATED,
    DATE_RENDERER_NUMERIC_FALLBACK,
)

_DASH_YMD_RE = re.compile(
    rf"(?P<year>{_FULL_YEAR_RE})-(?P<month>{_MONTH_RE})-(?P<day>{_DAY_RE})"
)
_DOT_DMY_RE = re.compile(
    rf"(?P<day>{_DAY_RE})\.(?P<month>{_MONTH_RE})\.(?P<year>{_FULL_YEAR_RE})"
)
_DOT_DMY_NO_YEAR_RE = re.compile(rf"(?P<day>{_DAY_RE})\.(?P<month>{_MONTH_RE})\.")
_DOT_DMY_SPACED_RE = re.compile(
    rf"(?P<day>{_DAY_RE})\.\s+(?P<month>{_MONTH_RE})\.\s*(?P<year>{_FULL_YEAR_RE})"
)
_DOT_DMY_SPACED_NO_YEAR_RE = re.compile(
    rf"(?P<day>{_DAY_RE})\.\s+(?P<month>{_MONTH_RE})\."
)
_DOT_DMY_NO_YEAR_CANDIDATE_RE = re.compile(
    rf"(?P<day>{_DAY_RE})\.\s*(?P<month>{_MONTH_RE})\."
)
_SLASH_DMY_RE = re.compile(
    rf"(?P<day>{_DAY_RE})/(?P<month>{_MONTH_RE})/(?P<year>{_FULL_YEAR_RE})"
)
_SLASH_MDY_RE = re.compile(
    rf"(?P<month>{_MONTH_RE})/(?P<day>{_DAY_RE})/(?P<year>{_FULL_YEAR_RE})"
)
_SLASH_DMY_NO_YEAR_RE = re.compile(rf"(?P<day>{_DAY_RE})/(?P<month>{_MONTH_RE})")
_SLASH_MDY_NO_YEAR_RE = re.compile(rf"(?P<month>{_MONTH_RE})/(?P<day>{_DAY_RE})")

_DE_MONTHS = {
    "januar": (1, "Januar"),
    "februar": (2, "Februar"),
    "märz": (3, "März"),
    "maerz": (3, "März"),
    "april": (4, "April"),
    "mai": (5, "Mai"),
    "juni": (6, "Juni"),
    "juli": (7, "Juli"),
    "august": (8, "August"),
    "september": (9, "September"),
    "oktober": (10, "Oktober"),
    "november": (11, "November"),
    "dezember": (12, "Dezember"),
}
_EN_MONTHS = {
    "january": (1, "January"),
    "february": (2, "February"),
    "march": (3, "March"),
    "april": (4, "April"),
    "may": (5, "May"),
    "june": (6, "June"),
    "july": (7, "July"),
    "august": (8, "August"),
    "september": (9, "September"),
    "october": (10, "October"),
    "november": (11, "November"),
    "december": (12, "December"),
}
_MONTH_NAME_RE = re.compile(
    "|".join(
        re.escape(month)
        for month in sorted({*_DE_MONTHS, *_EN_MONTHS}, key=len, reverse=True)
    ),
    re.IGNORECASE,
)
_DMY_MONTH_NAME_RE = re.compile(
    rf"(?P<day>{_DAY_RE})\.?\s+"
    rf"(?P<month>{_MONTH_NAME_RE.pattern})"
    rf"(?:\s+(?P<year>{_FULL_YEAR_RE}))?",
    re.IGNORECASE,
)
_MDY_MONTH_NAME_RE = re.compile(
    rf"(?P<month>{_MONTH_NAME_RE.pattern})\s+"
    rf"(?P<day>{_DAY_RE})"
    rf"(?:,?\s+(?P<year>{_FULL_YEAR_RE}))?",
    re.IGNORECASE,
)

_OPENING_BOUNDARY_CHARS = "([{\"\u201e\u201c'"
_CLOSING_BOUNDARY_CHARS = ")]}\"'\u201c\u201d"
_SENTENCE_BOUNDARY_CHARS = ".,;:!?"
_MARKDOWN_EMPHASIS_CHARS = "*_"
_GERMAN_WEAK_NOMINATIVE_DATE_CONTEXT = {"der", "dieser", "jener", "welcher"}
_GERMAN_WEAK_OBLIQUE_DATE_CONTEXT = {
    "am",
    "bis",
    "dem",
    "den",
    "des",
    "diesem",
    "diesen",
    "jenem",
    "jenen",
    "vom",
    "welchem",
    "welchen",
    "zum",
}
_GERMAN_STRONG_DATIVE_DATE_CONTEXT = {"ab", "nach", "seit", "von", "vor"}
_NUMERIC_FALLBACK_DATE_LOCALES = (
    "fr",
    "fr-FR",
    "es",
    "es-ES",
    "it",
    "it-IT",
    "nl",
    "nl-NL",
    "pl",
    "pl-PL",
    "pt",
    "pt-BR",
    "pt-PT",
    "ru",
    "ru-RU",
    "tr",
    "tr-TR",
)
_CURATED_DATE_LOCALES = (
    "de",
    "de-AT",
    "de-CH",
    "de-DE",
    "en",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-IE",
    "en-NZ",
    "en-US",
    "en-ZA",
)


class DateNormalizationError(ValueError):
    """Raised when Date Normalizer configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ParsedDate:
    """A parsed date token."""

    day: int
    month: int
    year: int | None = None


@dataclass(frozen=True, slots=True)
class DateNormalizer:
    """A configured Date Normalizer."""

    enabled: bool = False
    locale: str = ""
    renderer: str = DATE_RENDERER_CURATED
    input_formats: tuple[str, ...] = ()
    converter: DateNumberConverter | None = None

    def normalize(self, text: str) -> str:
        """Replace configured date strings with spoken date text."""
        if not self.enabled:
            return text

        normalized = text
        for input_format in self.input_formats:
            normalized = self._normalize_format(normalized, input_format)
        return normalized

    def _normalize_format(self, text: str, input_format: str) -> str:
        """Normalize one configured Date Input Format."""
        if input_format == DATE_INPUT_FORMAT_YMD_DASH:
            return _DASH_YMD_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_DMY_DOT:
            return _DOT_DMY_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_DMY_DOT_SPACED:
            return _DOT_DMY_SPACED_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR:
            return _DOT_DMY_NO_YEAR_RE.sub(self._replace_no_year_dot_match, text)
        if input_format == DATE_INPUT_FORMAT_DMY_DOT_SPACED_NO_YEAR:
            return _DOT_DMY_SPACED_NO_YEAR_RE.sub(
                self._replace_no_year_dot_match,
                text,
            )
        if input_format == DATE_INPUT_FORMAT_DMY_SLASH:
            return _SLASH_DMY_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_MDY_SLASH:
            return _SLASH_MDY_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_DMY_SLASH_NO_YEAR:
            return _SLASH_DMY_NO_YEAR_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_MDY_SLASH_NO_YEAR:
            return _SLASH_MDY_NO_YEAR_RE.sub(self._replace_numeric_match, text)
        if input_format == DATE_INPUT_FORMAT_DMY_MONTH_NAME:
            return _DMY_MONTH_NAME_RE.sub(self._replace_month_name_match, text)
        if input_format == DATE_INPUT_FORMAT_MDY_MONTH_NAME:
            return _MDY_MONTH_NAME_RE.sub(self._replace_month_name_match, text)
        return text

    def _replace_numeric_match(self, match: re.Match[str]) -> str:
        """Replace one numeric date match."""
        if not _has_date_boundaries(match):
            return match.group(0)

        parsed = _validated_date(
            int(match.group("day")),
            int(match.group("month")),
            int(match.group("year")) if "year" in match.groupdict() else None,
        )
        if parsed is None:
            return match.group(0)

        return self._render(parsed, match.string, match.start())

    def _replace_no_year_dot_match(self, match: re.Match[str]) -> str:
        """Replace one `DD.MM.` date match."""
        if not _has_date_boundaries(match):
            return match.group(0)

        parsed = _validated_date(int(match.group("day")), int(match.group("month")))
        if parsed is None:
            return match.group(0)
        if _has_adjacent_no_year_dot_date(match):
            return match.group(0)

        rendered = self._render(parsed, match.string, match.start())
        if _should_preserve_no_year_date_dot(match.string, match.end()):
            rendered += "."
        return rendered

    def _replace_month_name_match(self, match: re.Match[str]) -> str:
        """Replace one month-name date match."""
        if not _has_date_boundaries(match):
            return match.group(0)

        month = _month_name_value(match.group("month"), _language_from_locale(self.locale))
        if month is None:
            return match.group(0)

        parsed = _validated_date(
            int(match.group("day")),
            month[0],
            int(match.group("year")) if match.group("year") else None,
        )
        if parsed is None:
            return match.group(0)

        return self._render(parsed, match.string, match.start())

    def _render(self, parsed: ParsedDate, text: str, start: int) -> str:
        """Render one parsed date for the configured Date Renderer."""
        language = _language_from_locale(self.locale)
        if self.renderer == DATE_RENDERER_NUMERIC_FALLBACK:
            return _render_numeric_fallback_date(parsed, language, self._converter)
        if language == "de":
            return _render_german_date(parsed, text, start, self._converter)
        if language == "en":
            return _render_english_date(parsed, self.locale, self._converter)
        return _render_numeric_fallback_date(parsed, language, self._converter)

    @property
    def _converter(self) -> DateNumberConverter:
        """Return the configured converter or the num2words-backed converter."""
        return self.converter or _spellout_number_as


def parse_date_normalizer(raw_config: Mapping[str, Any]) -> DateNormalizer:
    """Parse and validate Date Normalizer configuration."""
    output_language = str(raw_config.get(CONF_OUTPUT_LANGUAGE, "") or "")
    number_language = str(raw_config.get(CONF_NUMBER_SPELLOUT_LANGUAGE, "") or "")
    locale = normalize_date_locale(
        str(
            raw_config.get(CONF_DATE_LOCALE)
            or default_date_locale(output_language, number_language)
        )
    )
    renderer = str(raw_config.get(CONF_DATE_RENDERER) or default_date_renderer(locale))
    input_formats = _parse_input_formats(raw_config.get(CONF_DATE_INPUT_FORMATS), locale)
    enabled = bool(raw_config.get(CONF_DATE_NORMALIZER_ENABLED, False))

    if not enabled:
        return DateNormalizer(
            enabled=False,
            locale=locale,
            renderer=renderer,
            input_formats=input_formats,
        )

    if not locale:
        raise DateNormalizationError("Date Locale is required")
    if renderer not in _SUPPORTED_RENDERERS:
        raise DateNormalizationError(f"Unsupported Date Renderer: {renderer}")
    if renderer == DATE_RENDERER_CURATED and _language_from_locale(locale) not in {
        "de",
        "en",
    }:
        raise DateNormalizationError(
            f"Curated Date Renderer is not available for {locale}"
        )
    if not input_formats:
        raise DateNormalizationError("At least one Date Input Format is required")
    unsupported_formats = set(input_formats) - set(_SUPPORTED_INPUT_FORMATS)
    if unsupported_formats:
        raise DateNormalizationError(
            f"Unsupported Date Input Format: {sorted(unsupported_formats)[0]}"
        )
    if _language_from_locale(locale) not in _supported_spellout_languages():
        raise DateNormalizationError(f"Unsupported Date Locale: {locale}")

    return DateNormalizer(
        enabled=True,
        locale=locale,
        renderer=renderer,
        input_formats=input_formats,
    )


def default_date_locale(output_language: str = "", number_language: str = "") -> str:
    """Return the best Date Locale default."""
    if output_language:
        return normalize_date_locale(output_language)
    if number_language:
        return normalize_date_locale(number_language)
    return ""


def default_date_renderer(locale: str) -> str:
    """Return the default Date Renderer for a Date Locale."""
    return (
        DATE_RENDERER_CURATED
        if _language_from_locale(locale) in {"de", "en"}
        else DATE_RENDERER_NUMERIC_FALLBACK
    )


def default_date_input_formats(locale: str) -> tuple[str, ...]:
    """Return default Date Input Formats for a Date Locale."""
    language = _language_from_locale(locale)
    region = _region_from_locale(locale)

    if language == "de":
        return (
            DATE_INPUT_FORMAT_DMY_DOT,
            DATE_INPUT_FORMAT_DMY_DOT_SPACED,
            DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR,
            DATE_INPUT_FORMAT_DMY_MONTH_NAME,
            DATE_INPUT_FORMAT_YMD_DASH,
        )

    if language == "en":
        if region in {"GB", "AU", "IE", "NZ", "ZA"}:
            return (
                DATE_INPUT_FORMAT_DMY_SLASH,
                DATE_INPUT_FORMAT_DMY_SLASH_NO_YEAR,
                DATE_INPUT_FORMAT_DMY_MONTH_NAME,
                DATE_INPUT_FORMAT_YMD_DASH,
            )
        if region == "CA":
            return (
                DATE_INPUT_FORMAT_YMD_DASH,
                DATE_INPUT_FORMAT_MDY_MONTH_NAME,
            )
        return (
            DATE_INPUT_FORMAT_MDY_SLASH,
            DATE_INPUT_FORMAT_MDY_SLASH_NO_YEAR,
            DATE_INPUT_FORMAT_MDY_MONTH_NAME,
            DATE_INPUT_FORMAT_YMD_DASH,
        )

    return (DATE_INPUT_FORMAT_YMD_DASH,)


def supported_date_locales() -> tuple[str, ...]:
    """Return Date Locales offered in the config flow."""
    spellout_locales = tuple(
        normalize_date_locale(language) for language in _supported_spellout_languages()
    )
    return tuple(
        sorted(
            {
                *_CURATED_DATE_LOCALES,
                *_NUMERIC_FALLBACK_DATE_LOCALES,
                *spellout_locales,
            }
        )
    )


def supported_date_input_formats() -> tuple[str, ...]:
    """Return supported Date Input Formats."""
    return _SUPPORTED_INPUT_FORMATS


def supported_date_renderers() -> tuple[str, ...]:
    """Return supported Date Renderers."""
    return _SUPPORTED_RENDERERS


def is_date_token_punctuation(text: str, index: int) -> bool:
    """Return if punctuation at index is part of a likely date token."""
    if index < 0 or index >= len(text) or text[index] != ".":
        return False
    return (
        _is_no_year_date_dot(text, index)
        or _is_spaced_dot_date_dot(text, index)
        or _is_day_month_name_dot(text, index)
    )


def normalize_date_locale(locale: str) -> str:
    """Return a normalized Date Locale string."""
    parts = [part for part in str(locale or "").replace("_", "-").split("-") if part]
    if not parts:
        return ""
    language = parts[0].lower()
    if len(parts) == 1:
        return language
    return "-".join([language, *(part.upper() if len(part) == 2 else part for part in parts[1:])])


def _parse_input_formats(raw_value: Any, locale: str) -> tuple[str, ...]:
    """Parse Date Input Formats from raw config-flow data."""
    if raw_value in (None, ""):
        return default_date_input_formats(locale)
    if isinstance(raw_value, str):
        return (raw_value,)
    if not isinstance(raw_value, list):
        raise DateNormalizationError("Date Input Formats must be a list")
    return tuple(str(value) for value in raw_value)


def _validated_date(day: int, month: int, year: int | None = None) -> ParsedDate | None:
    """Return a validated date or None."""
    try:
        date(year or 2000, month, day)
    except ValueError:
        return None
    return ParsedDate(day=day, month=month, year=year)


def _has_date_boundaries(match: re.Match[str]) -> bool:
    """Return if a date candidate has safe text boundaries."""
    return _has_start_boundary(match.string, match.start()) and _has_end_boundary(
        match.string,
        match.end(),
    )


def _has_start_boundary(text: str, start: int) -> bool:
    """Return if the character before start is outside a date token."""
    if start == 0:
        return True
    previous = text[start - 1]
    if previous.isspace() or previous in _OPENING_BOUNDARY_CHARS:
        return True
    return _has_markdown_emphasis_start_boundary(text, start)


def _has_end_boundary(text: str, end: int) -> bool:
    """Return if the character after end is outside a date token."""
    if end >= len(text):
        return True
    next_char = text[end]
    if (
        next_char.isspace()
        or next_char in _CLOSING_BOUNDARY_CHARS
        or next_char in _SENTENCE_BOUNDARY_CHARS
    ):
        return True
    return _has_markdown_emphasis_end_boundary(text, end)


def _has_markdown_emphasis_start_boundary(text: str, start: int) -> bool:
    """Return if a date starts after Markdown emphasis at a token boundary."""
    cursor = start
    while cursor > 0 and text[cursor - 1] in _MARKDOWN_EMPHASIS_CHARS:
        cursor -= 1

    if cursor == start:
        return False
    if cursor == 0:
        return True

    previous = text[cursor - 1]
    return (
        previous.isspace()
        or previous in _OPENING_BOUNDARY_CHARS
        or previous in _SENTENCE_BOUNDARY_CHARS
    )


def _has_markdown_emphasis_end_boundary(text: str, end: int) -> bool:
    """Return if a date ends before Markdown emphasis at a token boundary."""
    cursor = end
    while cursor < len(text) and text[cursor] in _MARKDOWN_EMPHASIS_CHARS:
        cursor += 1

    if cursor == end:
        return False
    if cursor >= len(text):
        return True

    next_char = text[cursor]
    return (
        next_char.isspace()
        or next_char in _CLOSING_BOUNDARY_CHARS
        or next_char in _SENTENCE_BOUNDARY_CHARS
    )


def _should_preserve_no_year_date_dot(text: str, end: int) -> bool:
    """Return if `DD.MM.` should keep the final dot as sentence punctuation."""
    cursor = end
    while cursor < len(text) and text[cursor] in " \t":
        cursor += 1

    if cursor >= len(text):
        return True
    if text[cursor] in "\r\n":
        return True
    return text[cursor].isupper()


def _has_adjacent_no_year_dot_date(match: re.Match[str]) -> bool:
    """Return if a no-year dot date is directly adjacent to another one."""
    return _has_previous_adjacent_no_year_dot_date(
        match.string,
        match.start(),
    ) or _has_next_adjacent_no_year_dot_date(match.string, match.end())


def _has_previous_adjacent_no_year_dot_date(text: str, start: int) -> bool:
    """Return if another no-year dot date ends before whitespace at start."""
    cursor = start
    while cursor > 0 and text[cursor - 1].isspace():
        cursor -= 1

    if cursor == start:
        return False

    for candidate in _DOT_DMY_NO_YEAR_CANDIDATE_RE.finditer(text, 0, cursor):
        if candidate.end() == cursor and _valid_no_year_dot_candidate(candidate):
            return True
    return False


def _has_next_adjacent_no_year_dot_date(text: str, end: int) -> bool:
    """Return if another no-year dot date starts after whitespace at end."""
    cursor = end
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1

    if cursor == end:
        return False

    candidate = _DOT_DMY_NO_YEAR_CANDIDATE_RE.match(text, cursor)
    return bool(candidate and _valid_no_year_dot_candidate(candidate))


def _valid_no_year_dot_candidate(match: re.Match[str]) -> bool:
    """Return if a no-year dot candidate is a valid standalone date token."""
    return (
        _has_date_boundaries(match)
        and _validated_date(int(match.group("day")), int(match.group("month")))
        is not None
    )


def _is_no_year_date_dot(text: str, index: int) -> bool:
    """Return if a dot looks like the final dot in `DD.MM.`."""
    match = re.search(
        rf"(?P<day>{_DAY_RE})\.(?P<month>{_MONTH_RE})$",
        text[:index],
    )
    if match is None or not _has_start_boundary(text, match.start()):
        return False
    return _validated_date(int(match.group("day")), int(match.group("month"))) is not None


def _is_spaced_dot_date_dot(text: str, index: int) -> bool:
    """Return if a dot looks like punctuation inside `DD. MM.`."""
    day_match = re.search(rf"(?P<day>{_DAY_RE})$", text[:index])
    if day_match is not None and _has_start_boundary(text, day_match.start()):
        next_token = re.match(
            rf"\s+(?P<month>{_MONTH_RE})\.(?:\s*{_FULL_YEAR_RE})?",
            text[index + 1 :],
        )
        if next_token is not None and _validated_date(
            int(day_match.group("day")),
            int(next_token.group("month")),
        ):
            return True

    month_match = re.search(
        rf"(?P<day>{_DAY_RE})\.\s+(?P<month>{_MONTH_RE})$",
        text[:index],
    )
    return bool(
        month_match is not None
        and _has_start_boundary(text, month_match.start())
        and _validated_date(
            int(month_match.group("day")),
            int(month_match.group("month")),
        )
    )


def _is_day_month_name_dot(text: str, index: int) -> bool:
    """Return if a dot looks like the day dot in `DD. Month`."""
    match = re.search(rf"(?P<day>{_DAY_RE})$", text[:index])
    if match is None or not _has_start_boundary(text, match.start()):
        return False
    next_token = re.match(
        rf"\s+(?P<month>{_MONTH_NAME_RE.pattern})(?:\s|$)",
        text[index + 1 :],
        re.IGNORECASE,
    )
    return next_token is not None


def _month_name_value(month_name: str, language: str) -> tuple[int, str] | None:
    """Return a month number and canonical month name for a language."""
    normalized = month_name.casefold()
    if language == "de":
        return _DE_MONTHS.get(normalized)
    if language == "en":
        return _EN_MONTHS.get(normalized)
    return None


def _render_german_date(
    parsed: ParsedDate,
    text: str,
    start: int,
    converter: DateNumberConverter,
) -> str:
    """Render a German date with a curated month-name style."""
    form = _german_date_context_form(text, start)
    parts = [
        _german_ordinal(parsed.day, form, converter),
        _DE_MONTHS_BY_NUMBER[parsed.month],
    ]
    if parsed.year is not None:
        parts.append(converter(parsed.year, "de", "year"))
    return " ".join(parts)


def _render_english_date(
    parsed: ParsedDate,
    locale: str,
    converter: DateNumberConverter,
) -> str:
    """Render an English date with a curated month-name style."""
    day = converter(parsed.day, "en", "ordinal")
    month = _EN_MONTHS_BY_NUMBER[parsed.month]
    parts: list[str]
    if _region_from_locale(locale) in {"GB", "AU", "IE", "NZ", "ZA"}:
        parts = [day, "of", month]
    else:
        parts = [month, day]
    if parsed.year is not None:
        parts.append(_english_year(parsed.year, converter))
    return " ".join(parts)


def _render_numeric_fallback_date(
    parsed: ParsedDate,
    language: str,
    converter: DateNumberConverter,
) -> str:
    """Render a date as numeric spoken parts."""
    parts = [
        converter(parsed.day, language, "cardinal"),
        converter(parsed.month, language, "cardinal"),
    ]
    if parsed.year is not None:
        parts.append(converter(parsed.year, language, "year"))
    return " ".join(parts)


def _german_ordinal(
    value: int,
    form: str,
    converter: DateNumberConverter,
) -> str:
    """Return a German ordinal form for date rendering."""
    ordinal = converter(value, "de", "ordinal")
    if form == "weak_nominative":
        return ordinal
    if form == "weak_oblique":
        return ordinal[:-1] + "en" if ordinal.endswith("e") else f"{ordinal}n"
    if form == "strong_dative":
        return ordinal[:-1] + "em" if ordinal.endswith("e") else f"{ordinal}m"
    return ordinal[:-1] + "er" if ordinal.endswith("e") else f"{ordinal}r"


def _english_year(year: int, converter: DateNumberConverter) -> str:
    """Return a spoken English date year."""
    if 1900 <= year <= 1999:
        century = converter(year // 100, "en", "cardinal")
        remainder = year % 100
        if remainder == 0:
            return f"{century} hundred"
        if remainder < 10:
            return f"{century} oh {converter(remainder, 'en', 'cardinal')}"
        return f"{century} {converter(remainder, 'en', 'cardinal')}"

    if year == 2000:
        return "two thousand"
    if 2001 <= year <= 2009:
        return f"two thousand {converter(year % 100, 'en', 'cardinal')}"
    if 2010 <= year <= 2099:
        return f"twenty {converter(year % 100, 'en', 'cardinal')}"

    return converter(year, "en", "year")


def _german_date_context_form(text: str, start: int) -> str:
    """Return the German ordinal form implied by the immediate left context."""
    prefix = text[:start].rstrip()
    match = re.search(r"([A-Za-zÄÖÜäöüß]+)$", prefix)
    if not match:
        return "standalone"

    previous_word = match.group(1).casefold()
    if previous_word in _GERMAN_WEAK_NOMINATIVE_DATE_CONTEXT:
        return "weak_nominative"
    if previous_word in _GERMAN_WEAK_OBLIQUE_DATE_CONTEXT:
        return "weak_oblique"
    if previous_word in _GERMAN_STRONG_DATIVE_DATE_CONTEXT:
        return "strong_dative"
    return "standalone"


def _language_from_locale(locale: str) -> str:
    """Return the primary language subtag."""
    return normalize_date_locale(locale).split("-", 1)[0]


def _region_from_locale(locale: str) -> str:
    """Return the region subtag if present."""
    parts = normalize_date_locale(locale).split("-")
    return parts[1] if len(parts) > 1 and len(parts[1]) == 2 else ""


def _spellout_number_as(value: int, language: str, purpose: str) -> str:
    """Spell out a number with num2words for date rendering."""
    try:
        from num2words import num2words
    except ImportError as err:
        raise DateNormalizationError("num2words is not available") from err

    if purpose == "cardinal":
        return str(num2words(value, lang=language))
    return str(num2words(value, lang=language, to=purpose))


def _supported_spellout_languages() -> tuple[str, ...]:
    """Return languages supported by num2words."""
    try:
        from num2words import CONVERTER_CLASSES
    except ImportError:
        return ()

    return tuple(sorted(str(language).replace("_", "-") for language in CONVERTER_CLASSES))


_DE_MONTHS_BY_NUMBER = {number: name for number, name in _DE_MONTHS.values()}
_EN_MONTHS_BY_NUMBER = {number: name for number, name in _EN_MONTHS.values()}
