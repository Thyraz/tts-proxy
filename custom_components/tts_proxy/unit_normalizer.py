"""Unit normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .const import (
    CONF_NUMBER_ALLOW_GROUPED_NUMBERS,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_OUTPUT_LANGUAGE,
    CONF_UNIT_LOCALE,
    CONF_UNIT_NORMALIZER_ENABLED,
)
from .numeric_text import (
    ParsedNumericText,
    has_numeric_prefix_boundary,
    looks_like_ambiguous_grouped_number,
    numeric_text_re,
    parse_numeric_text,
)

_CURATED_UNIT_LOCALES = (
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
_GENERIC_UNIT_LOCALES = (
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


@dataclass(frozen=True, slots=True)
class UnitAlias:
    """A supported written unit alias."""

    text: str
    key: str
    ignore_case: bool = True


@dataclass(frozen=True, slots=True)
class UnitForms:
    """Spoken unit forms for singular and plural numeric values."""

    singular: str
    plural: str | None = None

    def for_singular(self, singular: bool) -> str:
        """Return the form for a numeric text."""
        if singular:
            return self.singular
        return self.plural or self.singular


_UNIT_ALIASES = (
    UnitAlias("Mbit/s", "megabit_per_second"),
    UnitAlias("km/h", "kilometer_per_hour"),
    UnitAlias("kmh", "kilometer_per_hour"),
    UnitAlias("kWh", "kilowatt_hour"),
    UnitAlias("hPa", "hectopascal"),
    UnitAlias("mbar", "millibar"),
    UnitAlias("m/s", "meter_per_second"),
    UnitAlias("mA", "milliampere"),
    UnitAlias("Wh", "watt_hour"),
    UnitAlias("kW", "kilowatt"),
    UnitAlias("KB", "kilobyte"),
    UnitAlias("MB", "megabyte"),
    UnitAlias("GB", "gigabyte"),
    UnitAlias("°C", "celsius"),
    UnitAlias("°F", "fahrenheit"),
    UnitAlias("bar", "bar"),
    UnitAlias("km", "kilometer"),
    UnitAlias("lx", "lux"),
    UnitAlias("lm", "lumen"),
    UnitAlias("W", "watt"),
    UnitAlias("V", "volt", ignore_case=False),
    UnitAlias("A", "ampere", ignore_case=False),
    UnitAlias("B", "byte", ignore_case=False),
    UnitAlias("%", "percent", ignore_case=False),
)
_EXACT_ALIASES = {alias.text: alias.key for alias in _UNIT_ALIASES}
_CASEFOLD_ALIASES = {
    alias.text.casefold(): alias.key for alias in _UNIT_ALIASES if alias.ignore_case
}


def _unit_alias_pattern(alias: UnitAlias) -> str:
    """Return the regex pattern for one unit alias."""
    escaped = re.escape(alias.text)
    if alias.ignore_case:
        return f"(?i:{escaped})"
    return escaped


_UNIT_PATTERN = "|".join(
    _unit_alias_pattern(alias)
    for alias in sorted(_UNIT_ALIASES, key=lambda alias: len(alias.text), reverse=True)
)
_UNIT_RE = re.compile(
    rf"(?P<number>{numeric_text_re(allow_grouped_numbers=False).pattern})"
    r"\s*"
    rf"(?P<unit>{_UNIT_PATTERN})"
    r"(?![\w/])"
)
_GROUPED_UNIT_RE = re.compile(
    rf"(?P<number>{numeric_text_re(allow_grouped_numbers=True).pattern})"
    r"\s*"
    rf"(?P<unit>{_UNIT_PATTERN})"
    r"(?![\w/])"
)

_GERMAN_UNIT_FORMS = {
    "percent": UnitForms("Prozent"),
    "watt": UnitForms("Watt"),
    "kilowatt": UnitForms("Kilowatt"),
    "watt_hour": UnitForms("Wattstunde", "Wattstunden"),
    "kilowatt_hour": UnitForms("Kilowattstunde", "Kilowattstunden"),
    "volt": UnitForms("Volt"),
    "ampere": UnitForms("Ampere"),
    "milliampere": UnitForms("Milliampere"),
    "kilometer": UnitForms("Kilometer"),
    "kilometer_per_hour": UnitForms("Kilometer pro Stunde"),
    "meter_per_second": UnitForms("Meter pro Sekunde"),
    "hectopascal": UnitForms("Hektopascal"),
    "millibar": UnitForms("Millibar"),
    "bar": UnitForms("Bar"),
    "lux": UnitForms("Lux"),
    "lumen": UnitForms("Lumen"),
    "byte": UnitForms("Byte"),
    "kilobyte": UnitForms("Kilobyte"),
    "megabyte": UnitForms("Megabyte"),
    "gigabyte": UnitForms("Gigabyte"),
    "megabit_per_second": UnitForms("Megabit pro Sekunde"),
}
_ENGLISH_UNIT_FORMS = {
    "percent": UnitForms("percent"),
    "watt": UnitForms("watt", "watts"),
    "kilowatt": UnitForms("kilowatt", "kilowatts"),
    "watt_hour": UnitForms("watt hour", "watt hours"),
    "kilowatt_hour": UnitForms("kilowatt hour", "kilowatt hours"),
    "volt": UnitForms("volt", "volts"),
    "ampere": UnitForms("ampere", "amperes"),
    "milliampere": UnitForms("milliampere", "milliamperes"),
    "kilometer": UnitForms("kilometer", "kilometers"),
    "kilometer_per_hour": UnitForms("kilometer per hour", "kilometers per hour"),
    "meter_per_second": UnitForms("meter per second", "meters per second"),
    "hectopascal": UnitForms("hectopascal", "hectopascals"),
    "millibar": UnitForms("millibar", "millibars"),
    "bar": UnitForms("bar", "bars"),
    "lux": UnitForms("lux"),
    "lumen": UnitForms("lumen", "lumens"),
    "byte": UnitForms("byte", "bytes"),
    "kilobyte": UnitForms("kilobyte", "kilobytes"),
    "megabyte": UnitForms("megabyte", "megabytes"),
    "gigabyte": UnitForms("gigabyte", "gigabytes"),
    "megabit_per_second": UnitForms("megabit per second", "megabits per second"),
}
_GENERIC_UNIT_FORMS = _ENGLISH_UNIT_FORMS


class UnitNormalizationError(ValueError):
    """Raised when Unit Normalizer configuration is invalid."""


@dataclass(frozen=True, slots=True)
class UnitNormalizer:
    """A configured Unit Normalizer."""

    enabled: bool = False
    locale: str = ""
    allow_grouped_numbers: bool = False
    number_locale_hint: str = ""

    def normalize(self, text: str) -> str:
        """Replace supported unit symbols with spoken unit text."""
        if not self.enabled or not self.locale:
            return text

        unit_re = _GROUPED_UNIT_RE if self.allow_grouped_numbers else _UNIT_RE
        return unit_re.sub(self._replace_match, text)

    def _replace_match(self, match: re.Match[str]) -> str:
        """Replace one eligible number-plus-unit match."""
        number_text = match.group("number")
        unit_text = match.group("unit")
        if not has_numeric_prefix_boundary(match.string, match.start("number")):
            return match.group(0)
        if (
            not self.allow_grouped_numbers
            and looks_like_ambiguous_grouped_number(number_text)
        ):
            return match.group(0)

        parsed = parse_numeric_text(
            number_text,
            allow_grouped_numbers=self.allow_grouped_numbers,
            locale_hint=self.number_locale_hint or self.locale,
        )
        if parsed is None:
            return match.group(0)

        unit_key = _unit_key(unit_text)
        if unit_key is None:
            return match.group(0)

        return f"{number_text} {_unit_spoken_text(unit_key, self.locale, parsed)}"


def parse_unit_normalizer(raw_config: Mapping[str, Any]) -> UnitNormalizer:
    """Parse Unit Normalizer configuration."""
    output_language = str(raw_config.get(CONF_OUTPUT_LANGUAGE, "") or "")
    locale = _normalize_locale(
        str(raw_config.get(CONF_UNIT_LOCALE) or default_unit_locale(output_language))
    )
    enabled = bool(raw_config.get(CONF_UNIT_NORMALIZER_ENABLED, False))
    if enabled and not locale:
        raise UnitNormalizationError("Unit Locale is required")
    number_language = str(raw_config.get(CONF_NUMBER_SPELLOUT_LANGUAGE, "") or "")
    return UnitNormalizer(
        enabled=enabled,
        locale=locale,
        allow_grouped_numbers=bool(
            raw_config.get(CONF_NUMBER_ALLOW_GROUPED_NUMBERS, False)
        ),
        number_locale_hint=_numeric_locale_hint(
            number_language,
            locale,
            output_language,
        ),
    )


def default_unit_locale(output_language: str = "") -> str:
    """Return the best Unit Locale default."""
    return _normalize_locale(output_language)


def supported_unit_locales(output_languages: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return Unit Locales offered in the config flow."""
    locales = {
        *_CURATED_UNIT_LOCALES,
        *_GENERIC_UNIT_LOCALES,
        *(
            normalized
            for output_language in output_languages
            if (normalized := _normalize_locale(output_language))
        ),
    }
    return tuple(sorted(locales))


def _unit_spoken_text(
    unit_key: str,
    locale: str,
    parsed_number: ParsedNumericText,
) -> str:
    """Return spoken text for one unit symbol."""
    language = _language_from_locale(locale)
    singular = _is_singular(parsed_number)

    if unit_key == "celsius":
        if language == "de":
            return "Grad"
        if language == "en" and _normal_temperature_scale(locale) == "celsius":
            return _degree_word(singular)
        return f"{_degree_word(singular)} Celsius"
    if unit_key == "fahrenheit":
        if language == "de":
            return "Grad Fahrenheit"
        if language == "en" and _normal_temperature_scale(locale) == "fahrenheit":
            return _degree_word(singular)
        return f"{_degree_word(singular)} Fahrenheit"

    forms = _unit_forms_for_locale(locale).get(unit_key)
    if forms is None:
        return unit_key
    return forms.for_singular(singular)


def _unit_forms_for_locale(locale: str) -> dict[str, UnitForms]:
    """Return spoken unit forms for a locale."""
    language = _language_from_locale(locale)
    if language == "de":
        return _GERMAN_UNIT_FORMS
    if language == "en":
        return _ENGLISH_UNIT_FORMS
    return _GENERIC_UNIT_FORMS


def _unit_key(unit_text: str) -> str | None:
    """Return the canonical unit key for written unit text."""
    return _EXACT_ALIASES.get(unit_text) or _CASEFOLD_ALIASES.get(
        unit_text.casefold()
    )


def _degree_word(singular: bool) -> str:
    """Return singular or plural English degree text."""
    return "degree" if singular else "degrees"


def _normal_temperature_scale(locale: str) -> str:
    """Return the locale's everyday temperature scale."""
    return "fahrenheit" if _normalize_locale(locale) == "en-US" else "celsius"


def _is_singular(parsed_number: ParsedNumericText) -> bool:
    """Return if the numeric text has singular unit value."""
    if parsed_number.value is None:
        return False
    try:
        return abs(Decimal(str(parsed_number.value))) == Decimal(1)
    except InvalidOperation:
        return False


def _numeric_locale_hint(
    number_language: str,
    unit_locale: str,
    output_language: str,
) -> str:
    """Return the best locale hint for ambiguous grouped numbers."""
    return (
        str(number_language or "").strip()
        or str(unit_locale or "").strip()
        or str(output_language or "").strip()
    )


def _language_from_locale(locale: str) -> str:
    """Return the language part of a locale."""
    return _normalize_locale(locale).split("-", 1)[0]


def _normalize_locale(locale: str) -> str:
    """Return a normalized locale string."""
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
