"""Time normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import re
from typing import Any

from .const import (
    CONF_OUTPUT_LANGUAGE,
    CONF_TIME_CLOCK_TIMES_ENABLED,
    CONF_TIME_DURATIONS_ENABLED,
    CONF_TIME_LOCALE,
    CONF_TIME_NORMALIZER_ENABLED,
    CONF_TIME_RANGES_ENABLED,
)

TimeNumberConverter = Callable[[int, str, str], str]

_SUPPORTED_TIME_LOCALES = (
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
_TIME_SUFFIX_RE = r"(?:uhr|a\.m\.|p\.m\.|am|pm)"
_CLOCK_TIME_RE = re.compile(
    rf"(?P<hour>\d{{1,2}}):(?P<minute>\d{{2}})"
    rf"(?P<suffix>\s*{_TIME_SUFFIX_RE})?",
    re.IGNORECASE,
)
_TIME_RANGE_RE = re.compile(
    rf"(?P<start_hour>\d{{1,2}}):(?P<start_minute>\d{{2}})"
    rf"(?P<start_suffix>\s*{_TIME_SUFFIX_RE})?"
    r"\s*(?P<marker>-|–|—|bis|to)\s*"
    rf"(?P<end_hour>\d{{1,2}}):(?P<end_minute>\d{{2}})"
    rf"(?P<end_suffix>\s*{_TIME_SUFFIX_RE})?",
    re.IGNORECASE,
)
_DURATION_HMS_RE = re.compile(
    r"(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})"
)
_DURATION_HM_SUFFIX_RE = re.compile(
    r"(?P<hours>\d+):(?P<minutes>\d{2})\s*h(?![A-Za-z_])",
    re.IGNORECASE,
)
_STRUCTURAL_PREFIX_CHARS = ".:/+"
_STRUCTURAL_SUFFIX_CHARS = ":/+"
_CLOCK_MARKER_AFTER_RE = re.compile(
    rf"\s*(?:{_TIME_SUFFIX_RE})(?=$|[\s,.;:!?)\]}}])",
    re.IGNORECASE,
)


class TimeNormalizationError(ValueError):
    """Raised when Time Normalizer configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ClockTime:
    """A parsed clock time token."""

    hour: int
    minute: int
    suffix: str = ""


@dataclass(frozen=True, slots=True)
class Duration:
    """A parsed duration token."""

    hours: int
    minutes: int
    seconds: int = 0


@dataclass(frozen=True, slots=True)
class TimeNormalizer:
    """A configured Time Normalizer."""

    enabled: bool = False
    locale: str = ""
    clock_times_enabled: bool = True
    time_ranges_enabled: bool = True
    durations_enabled: bool = False
    converter: TimeNumberConverter | None = None

    def normalize(self, text: str) -> str:
        """Replace configured time strings with spoken time text."""
        if not self.enabled:
            return text

        normalized = text
        if self.time_ranges_enabled:
            normalized = _TIME_RANGE_RE.sub(self._replace_range_match, normalized)
        if self.durations_enabled:
            normalized = _DURATION_HMS_RE.sub(
                self._replace_hms_duration_match,
                normalized,
            )
            normalized = _DURATION_HM_SUFFIX_RE.sub(
                self._replace_hm_duration_match,
                normalized,
            )
        if self.clock_times_enabled:
            normalized = _CLOCK_TIME_RE.sub(self._replace_clock_match, normalized)
        return normalized

    @property
    def _converter(self) -> TimeNumberConverter:
        """Return the configured converter or the num2words-backed converter."""
        return self.converter or _spellout_number_as

    def _replace_range_match(self, match: re.Match[str]) -> str:
        """Replace one clock-time range match."""
        if not _has_time_boundaries(match):
            return match.group(0)
        if not _range_marker_allowed(match.group("marker"), self.locale):
            return match.group(0)

        start = _parsed_clock_time(
            match.group("start_hour"),
            match.group("start_minute"),
            match.group("start_suffix") or "",
            self.locale,
        )
        end = _parsed_clock_time(
            match.group("end_hour"),
            match.group("end_minute"),
            match.group("end_suffix") or "",
            self.locale,
        )
        if start is None or end is None:
            return match.group(0)

        try:
            return _render_time_range(start, end, self.locale, self._converter)
        except (
            ArithmeticError,
            ImportError,
            NotImplementedError,
            TypeError,
            ValueError,
        ):
            return match.group(0)

    def _replace_hms_duration_match(self, match: re.Match[str]) -> str:
        """Replace one HH:MM:SS duration match."""
        if not _has_time_boundaries(match):
            return match.group(0)
        if _has_clock_marker_after(match.string, match.end()):
            return match.group(0)

        duration = _parsed_duration(
            match.group("hours"),
            match.group("minutes"),
            match.group("seconds"),
        )
        if duration is None:
            return match.group(0)

        try:
            return _render_duration(duration, self.locale, self._converter)
        except (
            ArithmeticError,
            ImportError,
            NotImplementedError,
            TypeError,
            ValueError,
        ):
            return match.group(0)

    def _replace_hm_duration_match(self, match: re.Match[str]) -> str:
        """Replace one H:MMh duration match."""
        if not _has_time_boundaries(match):
            return match.group(0)
        if _has_clock_marker_after(match.string, match.end()):
            return match.group(0)

        duration = _parsed_duration(match.group("hours"), match.group("minutes"), "0")
        if duration is None:
            return match.group(0)

        try:
            return _render_duration(duration, self.locale, self._converter)
        except (
            ArithmeticError,
            ImportError,
            NotImplementedError,
            TypeError,
            ValueError,
        ):
            return match.group(0)

    def _replace_clock_match(self, match: re.Match[str]) -> str:
        """Replace one clock-time match."""
        if not _has_time_boundaries(match):
            return match.group(0)

        parsed = _parsed_clock_time(
            match.group("hour"),
            match.group("minute"),
            match.group("suffix") or "",
            self.locale,
        )
        if parsed is None:
            return match.group(0)

        try:
            return _render_clock_time(parsed, self.locale, self._converter)
        except (
            ArithmeticError,
            ImportError,
            NotImplementedError,
            TypeError,
            ValueError,
        ):
            return match.group(0)


def parse_time_normalizer(raw_config: Mapping[str, Any]) -> TimeNormalizer:
    """Parse and validate Time Normalizer configuration."""
    output_language = str(raw_config.get(CONF_OUTPUT_LANGUAGE, "") or "")
    locale = normalize_time_locale(
        str(raw_config.get(CONF_TIME_LOCALE) or default_time_locale(output_language))
    )
    enabled = bool(raw_config.get(CONF_TIME_NORMALIZER_ENABLED, False))
    clock_times_enabled = bool(raw_config.get(CONF_TIME_CLOCK_TIMES_ENABLED, True))
    time_ranges_enabled = bool(raw_config.get(CONF_TIME_RANGES_ENABLED, True))
    durations_enabled = bool(raw_config.get(CONF_TIME_DURATIONS_ENABLED, False))

    if enabled:
        if not locale:
            raise TimeNormalizationError("Time Locale is required")
        if locale not in _SUPPORTED_TIME_LOCALES:
            raise TimeNormalizationError(f"Unsupported Time Locale: {locale}")

    return TimeNormalizer(
        enabled=enabled,
        locale=locale,
        clock_times_enabled=clock_times_enabled,
        time_ranges_enabled=time_ranges_enabled,
        durations_enabled=durations_enabled,
    )


def default_time_locale(output_language: str = "") -> str:
    """Return the best Time Locale default."""
    locale = normalize_time_locale(output_language)
    if locale in _SUPPORTED_TIME_LOCALES:
        return locale

    language = _language_from_locale(locale)
    if language in _SUPPORTED_TIME_LOCALES:
        return language
    return ""


def supported_time_locales() -> tuple[str, ...]:
    """Return Time Locales offered in the config flow."""
    return tuple(sorted(_SUPPORTED_TIME_LOCALES))


def normalize_time_locale(locale: str) -> str:
    """Return a normalized Time Locale string."""
    parts = [part for part in str(locale or "").replace("_", "-").split("-") if part]
    if not parts:
        return ""
    language = parts[0].lower()
    if len(parts) == 1:
        return language
    return "-".join(
        [
            language,
            *(part.upper() if len(part) == 2 else part for part in parts[1:]),
        ]
    )


def _parsed_clock_time(
    raw_hour: str,
    raw_minute: str,
    raw_suffix: str,
    locale: str,
) -> ClockTime | None:
    """Return a validated clock time candidate or None."""
    hour = int(raw_hour)
    minute = int(raw_minute)
    suffix = _normalized_suffix(raw_suffix)
    language = _language_from_locale(locale)

    if minute > 59:
        return None
    if language == "de" and suffix not in {"", "uhr"}:
        return None
    if language == "en" and suffix in {"uhr"}:
        return None

    if suffix in {"am", "pm"}:
        if hour < 1 or hour > 12:
            return None
    elif hour > 23:
        return None

    return ClockTime(hour=hour, minute=minute, suffix=suffix)


def _parsed_duration(
    raw_hours: str,
    raw_minutes: str,
    raw_seconds: str,
) -> Duration | None:
    """Return a validated duration candidate or None."""
    hours = int(raw_hours)
    minutes = int(raw_minutes)
    seconds = int(raw_seconds)
    if minutes > 59 or seconds > 59:
        return None
    return Duration(hours=hours, minutes=minutes, seconds=seconds)


def _render_time_range(
    start: ClockTime,
    end: ClockTime,
    locale: str,
    converter: TimeNumberConverter,
) -> str:
    """Render one clock-time range."""
    separator = "bis" if _language_from_locale(locale) == "de" else "to"
    return (
        f"{_render_clock_time(start, locale, converter)} "
        f"{separator} "
        f"{_render_clock_time(end, locale, converter)}"
    )


def _render_clock_time(
    parsed: ClockTime,
    locale: str,
    converter: TimeNumberConverter,
) -> str:
    """Render one clock time for the configured Time Locale."""
    language = _language_from_locale(locale)
    if language == "de":
        return _render_german_clock_time(parsed, converter)
    if language == "en":
        return _render_english_clock_time(parsed, converter)
    return f"{parsed.hour}:{parsed.minute:02d}"


def _render_german_clock_time(
    parsed: ClockTime,
    converter: TimeNumberConverter,
) -> str:
    """Render one German clock time."""
    hour = "ein" if parsed.hour == 1 else _cardinal(parsed.hour, "de", converter)
    if parsed.minute == 0:
        return f"{hour} Uhr"
    return f"{hour} Uhr {_cardinal(parsed.minute, 'de', converter)}"


def _render_english_clock_time(
    parsed: ClockTime,
    converter: TimeNumberConverter,
) -> str:
    """Render one English clock time."""
    parts = [_cardinal(parsed.hour, "en", converter)]
    if parsed.minute:
        minute = _cardinal(parsed.minute, "en", converter)
        parts.append(f"oh {minute}" if parsed.minute < 10 else minute)
    if parsed.suffix in {"am", "pm"}:
        parts.append(parsed.suffix.upper())
    return " ".join(parts)


def _render_duration(
    duration: Duration,
    locale: str,
    converter: TimeNumberConverter,
) -> str:
    """Render one duration for the configured Time Locale."""
    language = _language_from_locale(locale)
    if language == "de":
        return _render_german_duration(duration, converter)
    if language == "en":
        return _render_english_duration(duration, converter)
    return f"{duration.hours}:{duration.minutes:02d}:{duration.seconds:02d}"


def _render_german_duration(
    duration: Duration,
    converter: TimeNumberConverter,
) -> str:
    """Render one German duration."""
    parts: list[str] = []
    if duration.hours:
        parts.append(
            _german_duration_component(
                duration.hours,
                "Stunde",
                "Stunden",
                converter,
            )
        )
    if duration.minutes:
        parts.append(
            _german_duration_component(duration.minutes, "Minute", "Minuten", converter)
        )
    if duration.seconds:
        parts.append(
            _german_duration_component(
                duration.seconds,
                "Sekunde",
                "Sekunden",
                converter,
            )
        )
    return " ".join(parts) if parts else "null Sekunden"


def _render_english_duration(
    duration: Duration,
    converter: TimeNumberConverter,
) -> str:
    """Render one English duration."""
    parts: list[str] = []
    if duration.hours:
        parts.append(_english_duration_component(duration.hours, "hour", converter))
    if duration.minutes:
        parts.append(_english_duration_component(duration.minutes, "minute", converter))
    if duration.seconds:
        parts.append(_english_duration_component(duration.seconds, "second", converter))
    return " ".join(parts) if parts else "zero seconds"


def _german_duration_component(
    value: int,
    singular: str,
    plural: str,
    converter: TimeNumberConverter,
) -> str:
    """Return a German duration component."""
    if value == 1:
        return f"eine {singular}"
    return f"{_cardinal(value, 'de', converter)} {plural}"


def _english_duration_component(
    value: int,
    unit: str,
    converter: TimeNumberConverter,
) -> str:
    """Return an English duration component."""
    word = _cardinal(value, "en", converter)
    suffix = "" if value == 1 else "s"
    return f"{word} {unit}{suffix}"


def _has_time_boundaries(match: re.Match[str]) -> bool:
    """Return if a time candidate has safe text boundaries."""
    return _has_time_start_boundary(
        match.string,
        match.start(),
    ) and _has_time_end_boundary(
        match.string,
        match.end(),
    )


def _has_time_start_boundary(text: str, start: int) -> bool:
    """Return if a time candidate has a safe left boundary."""
    if start <= 0:
        return True
    previous = text[start - 1]
    return not (
        previous.isalnum()
        or previous == "_"
        or previous in _STRUCTURAL_PREFIX_CHARS
    )


def _has_time_end_boundary(text: str, end: int) -> bool:
    """Return if a time candidate has a safe right boundary."""
    if end >= len(text):
        return True
    next_char = text[end]
    if (
        next_char.isalnum()
        or next_char == "_"
        or next_char in _STRUCTURAL_SUFFIX_CHARS
    ):
        return False
    return not (
        next_char in ".," and end + 1 < len(text) and text[end + 1].isdigit()
    )


def _has_clock_marker_after(text: str, end: int) -> bool:
    """Return if a clock marker follows a candidate duration."""
    return bool(_CLOCK_MARKER_AFTER_RE.match(text[end:]))


def _range_marker_allowed(marker: str, locale: str) -> bool:
    """Return if a range marker is valid for the configured locale."""
    language = _language_from_locale(locale)
    normalized = marker.casefold()
    if normalized in {"-", "–", "—"}:
        return True
    if language == "de":
        return normalized == "bis"
    if language == "en":
        return normalized == "to"
    return False


def _normalized_suffix(raw_suffix: str) -> str:
    """Return the normalized clock suffix marker."""
    suffix = re.sub(r"\s+", "", raw_suffix or "").casefold()
    if suffix == "uhr":
        return "uhr"
    if suffix in {"am", "a.m."}:
        return "am"
    if suffix in {"pm", "p.m."}:
        return "pm"
    return ""


def _cardinal(
    value: int,
    language: str,
    converter: TimeNumberConverter,
) -> str:
    """Spell out a cardinal number."""
    return str(converter(value, language, "cardinal"))


def _language_from_locale(locale: str) -> str:
    """Return the language part of a locale."""
    return normalize_time_locale(locale).split("-", 1)[0]


def _spellout_number_as(value: int, language: str, _purpose: str) -> str:
    """Spell out a number with num2words."""
    try:
        from num2words import num2words
    except ImportError as err:
        raise TimeNormalizationError("num2words is not available") from err

    return str(num2words(value, lang=language))
