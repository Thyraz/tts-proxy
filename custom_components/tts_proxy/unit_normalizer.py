"""Unit normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .const import (
    CONF_OUTPUT_LANGUAGE,
    CONF_UNIT_LOCALE,
    CONF_UNIT_NORMALIZER_ENABLED,
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

    def for_number(self, number_text: str) -> str:
        """Return the form for a numeric text."""
        if _is_singular(number_text):
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
    r"(?<![\w.,:/+\-–—])"
    r"(?P<number>-?\d+(?:[.,]\d+)?)"
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

    def normalize(self, text: str) -> str:
        """Replace supported unit symbols with spoken unit text."""
        if not self.enabled or not self.locale:
            return text

        return _UNIT_RE.sub(self._replace_match, text)

    def _replace_match(self, match: re.Match[str]) -> str:
        """Replace one eligible number-plus-unit match."""
        number_text = match.group("number")
        unit_text = match.group("unit")
        if _looks_like_grouped_number(number_text):
            return match.group(0)

        unit_key = _unit_key(unit_text)
        if unit_key is None:
            return match.group(0)

        return f"{number_text} {_unit_spoken_text(unit_key, self.locale, number_text)}"


def parse_unit_normalizer(raw_config: Mapping[str, Any]) -> UnitNormalizer:
    """Parse Unit Normalizer configuration."""
    output_language = str(raw_config.get(CONF_OUTPUT_LANGUAGE, "") or "")
    locale = _normalize_locale(
        str(raw_config.get(CONF_UNIT_LOCALE) or default_unit_locale(output_language))
    )
    enabled = bool(raw_config.get(CONF_UNIT_NORMALIZER_ENABLED, False))
    if enabled and not locale:
        raise UnitNormalizationError("Unit Locale is required")
    return UnitNormalizer(enabled=enabled, locale=locale)


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


def _unit_spoken_text(unit_key: str, locale: str, number_text: str) -> str:
    """Return spoken text for one unit symbol."""
    language = _language_from_locale(locale)

    if unit_key == "celsius":
        if language == "de":
            return "Grad"
        if language == "en" and _normal_temperature_scale(locale) == "celsius":
            return _degree_word(number_text)
        return f"{_degree_word(number_text)} Celsius"
    if unit_key == "fahrenheit":
        if language == "de":
            return "Grad Fahrenheit"
        if language == "en" and _normal_temperature_scale(locale) == "fahrenheit":
            return _degree_word(number_text)
        return f"{_degree_word(number_text)} Fahrenheit"

    forms = _unit_forms_for_locale(locale).get(unit_key)
    if forms is None:
        return unit_key
    return forms.for_number(number_text)


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


def _degree_word(number_text: str) -> str:
    """Return singular or plural English degree text."""
    return "degree" if _is_singular(number_text) else "degrees"


def _normal_temperature_scale(locale: str) -> str:
    """Return the locale's everyday temperature scale."""
    return "fahrenheit" if _normalize_locale(locale) == "en-US" else "celsius"


def _is_singular(number_text: str) -> bool:
    """Return if the numeric text has singular unit value."""
    try:
        return abs(Decimal(number_text.replace(",", "."))) == Decimal(1)
    except InvalidOperation:
        return False


def _looks_like_grouped_number(number_text: str) -> bool:
    """Return if one-separator numeric text looks like grouped thousands."""
    unsigned = number_text[1:] if number_text.startswith("-") else number_text
    separator = _decimal_separator(unsigned)
    if separator is None:
        return False

    integer_part, fraction_part = unsigned.split(separator, 1)
    return (
        len(fraction_part) == 3
        and len(integer_part) <= 3
        and not integer_part.startswith("0")
    )


def _decimal_separator(unsigned_number_text: str) -> str | None:
    """Return the single decimal separator in unsigned text if present."""
    if "." in unsigned_number_text and "," in unsigned_number_text:
        return None
    if "." in unsigned_number_text:
        return "."
    if "," in unsigned_number_text:
        return ","
    return None


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
