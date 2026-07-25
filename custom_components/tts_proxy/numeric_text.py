"""Shared numeric-token parsing for text normalizers."""

from __future__ import annotations

from dataclasses import dataclass
import re

NEGATIVE_SIGN_CHARS = "-\u2212\u2013\u2014"
GROUP_SEPARATOR_SPACES = " \u00a0\u202f\u2009"

_PUNCTUATION_SEPARATORS = ".,"
_SIGN_PATTERN = rf"[{re.escape(NEGATIVE_SIGN_CHARS)}]"
_SIMPLE_NUMERIC_TEXT_PATTERN = rf"{_SIGN_PATTERN}?\d+(?:[.,]\d+)?"
_SPACE_GROUPED_NUMERIC_TEXT_PATTERN = (
    rf"\d{{1,3}}(?:[{re.escape(GROUP_SEPARATOR_SPACES)}]\d{{3}})+(?:[.,]\d+)?"
)
_DOT_GROUPED_NUMERIC_TEXT_PATTERN = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?"
_COMMA_GROUPED_NUMERIC_TEXT_PATTERN = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"
_GROUPED_NUMERIC_TEXT_PATTERN = (
    rf"{_SIGN_PATTERN}?(?:"
    rf"{_SPACE_GROUPED_NUMERIC_TEXT_PATTERN}|"
    rf"{_DOT_GROUPED_NUMERIC_TEXT_PATTERN}|"
    rf"{_COMMA_GROUPED_NUMERIC_TEXT_PATTERN}|"
    rf"\d+(?:[.,]\d+)?"
    rf")"
)
_STRUCTURAL_PREFIX_CHARS = set(".,:/+") | set(NEGATIVE_SIGN_CHARS)
_STRUCTURAL_SUFFIX_CHARS = set(":/+") | set(NEGATIVE_SIGN_CHARS)
_MAX_INTEGER_DIGITS = 9
_MAX_FRACTION_DIGITS = 6

SIMPLE_NUMERIC_TEXT_RE = re.compile(_SIMPLE_NUMERIC_TEXT_PATTERN)
GROUPED_NUMERIC_TEXT_RE = re.compile(_GROUPED_NUMERIC_TEXT_PATTERN)


@dataclass(frozen=True, slots=True)
class ParsedNumericText:
    """Numeric token converted to a safe Number Normalizer input."""

    value: int | str | None
    digit_sequence: tuple[int, ...] | None = None
    negative: bool = False


def numeric_text_re(*, allow_grouped_numbers: bool) -> re.Pattern[str]:
    """Return the numeric-token regex for the selected grouping mode."""
    if allow_grouped_numbers:
        return GROUPED_NUMERIC_TEXT_RE
    return SIMPLE_NUMERIC_TEXT_RE


def has_numeric_boundaries(text: str, start: int, end: int) -> bool:
    """Return if a numeric token has safe surrounding boundaries."""
    return has_numeric_prefix_boundary(text, start) and has_numeric_suffix_boundary(
        text, end
    )


def has_numeric_prefix_boundary(text: str, start: int) -> bool:
    """Return if a numeric token has a safe leading boundary."""
    if start <= 0:
        return True

    previous = text[start - 1]
    if previous.isalnum() or previous == "_" or previous in _STRUCTURAL_PREFIX_CHARS:
        return False
    return not _looks_like_group_separator_before(text, start)


def has_numeric_suffix_boundary(text: str, end: int) -> bool:
    """Return if a numeric token has a safe trailing boundary."""
    if end >= len(text):
        return True

    next_char = text[end]
    if (
        next_char.isalnum()
        or next_char == "_"
        or next_char in _STRUCTURAL_SUFFIX_CHARS
    ):
        return False
    if next_char in _PUNCTUATION_SEPARATORS and _next_char_is_digit(text, end):
        return False
    return not _looks_like_group_separator_after(text, end)


def parse_numeric_text(
    number_text: str,
    *,
    allow_grouped_numbers: bool = False,
    locale_hint: str = "",
) -> ParsedNumericText | None:
    """Parse numeric text into a Number Normalizer value."""
    if not number_text:
        return None

    negative = has_negative_sign(number_text)
    unsigned = unsigned_number_text(number_text)
    if not unsigned or is_ipv4_address_text(unsigned):
        return None

    if any(separator in unsigned for separator in GROUP_SEPARATOR_SPACES):
        if not allow_grouped_numbers:
            return None
        return _parse_space_grouped_number(unsigned, negative=negative)

    has_dot = "." in unsigned
    has_comma = "," in unsigned
    if has_dot and has_comma:
        if not allow_grouped_numbers:
            return None
        return _parse_mixed_punctuation_grouped_number(unsigned, negative=negative)

    separator = decimal_separator(unsigned)
    if separator is None:
        return _parse_integer(unsigned, negative=negative)

    if unsigned.count(separator) > 1:
        if not allow_grouped_numbers:
            return None
        return _parse_grouped_integer(unsigned.split(separator), negative=negative)

    integer_part, fraction_part = unsigned.split(separator, 1)
    if (
        allow_grouped_numbers
        and _is_valid_grouped_integer_parts((integer_part, fraction_part))
        and _locale_group_separator(locale_hint) == separator
    ):
        return _grouped_value((integer_part, fraction_part), negative=negative)

    return _parse_decimal(integer_part, fraction_part, negative=negative)


def looks_like_ambiguous_grouped_number(number_text: str) -> bool:
    """Return if one-separator numeric text may be grouped thousands."""
    unsigned = unsigned_number_text(number_text)
    separator = decimal_separator(unsigned)
    if separator is None:
        return False

    integer_part, fraction_part = unsigned.split(separator, 1)
    return _is_valid_grouped_integer_parts((integer_part, fraction_part))


def is_ipv4_address_text(text: str) -> bool:
    """Return if text is a valid IPv4 address."""
    parts = text.split(".")
    if len(parts) != 4:
        return False

    for part in parts:
        if not part.isdigit():
            return False
        value = int(part)
        if value > 255:
            return False
    return True


def decimal_separator(unsigned_number_text: str) -> str | None:
    """Return the single punctuation separator in unsigned text if present."""
    has_dot = "." in unsigned_number_text
    has_comma = "," in unsigned_number_text
    if has_dot and has_comma:
        return None
    if has_dot:
        return "."
    if has_comma:
        return ","
    return None


def has_negative_sign(number_text: str) -> bool:
    """Return if numeric text starts with a supported negative sign."""
    return bool(number_text) and number_text[0] in NEGATIVE_SIGN_CHARS


def unsigned_number_text(number_text: str) -> str:
    """Return numeric text without a supported leading negative sign."""
    return number_text[1:] if has_negative_sign(number_text) else number_text


def _parse_integer(unsigned: str, *, negative: bool) -> ParsedNumericText | None:
    """Parse simple unsigned integer text."""
    if not _integer_part_length_is_eligible(unsigned):
        return None
    if len(unsigned) > 1 and unsigned.startswith("0"):
        value = int(unsigned)
        return ParsedNumericText(
            value=-value if negative and value else value,
            digit_sequence=tuple(int(char) for char in unsigned),
            negative=negative,
        )

    value = int(unsigned)
    return ParsedNumericText(value=-value if negative and value else value)


def _parse_decimal(
    integer_part: str,
    fraction_part: str,
    *,
    negative: bool,
) -> ParsedNumericText | None:
    """Parse one-separator decimal text."""
    if not integer_part.isdigit() or not fraction_part.isdigit():
        return None
    if not _integer_part_length_is_eligible(integer_part):
        return None
    if not 0 < len(fraction_part) <= _MAX_FRACTION_DIGITS:
        return None

    normalized_integer = integer_part.lstrip("0") or "0"
    normalized_fraction = fraction_part.rstrip("0")
    if not normalized_fraction:
        value = int(normalized_integer)
        return ParsedNumericText(value=-value if negative and value else value)

    sign = "-" if negative else ""
    return ParsedNumericText(value=f"{sign}{normalized_integer}.{normalized_fraction}")


def _parse_space_grouped_number(
    unsigned: str,
    *,
    negative: bool,
) -> ParsedNumericText | None:
    """Parse grouped number text that uses spaces as thousands separators."""
    space_separators = {
        separator for separator in GROUP_SEPARATOR_SPACES if separator in unsigned
    }
    if len(space_separators) != 1:
        return None

    space_separator = next(iter(space_separators))
    punctuation_separators = [
        separator for separator in _PUNCTUATION_SEPARATORS if separator in unsigned
    ]
    if len(punctuation_separators) > 1:
        return None

    fraction_part: str | None = None
    integer_text = unsigned
    if punctuation_separators:
        decimal_separator_text = punctuation_separators[0]
        if unsigned.count(decimal_separator_text) != 1:
            return None
        integer_text, fraction_part = unsigned.rsplit(decimal_separator_text, 1)
        if space_separator in fraction_part:
            return None

    groups = integer_text.split(space_separator)
    return _grouped_value(groups, fraction_part=fraction_part, negative=negative)


def _parse_mixed_punctuation_grouped_number(
    unsigned: str,
    *,
    negative: bool,
) -> ParsedNumericText | None:
    """Parse grouped number text with punctuation grouping and decimal separator."""
    decimal_separator_text = "." if unsigned.rfind(".") > unsigned.rfind(",") else ","
    group_separator = "," if decimal_separator_text == "." else "."
    integer_text, fraction_part = unsigned.rsplit(decimal_separator_text, 1)

    if decimal_separator_text in integer_text or group_separator in fraction_part:
        return None

    groups = integer_text.split(group_separator)
    return _grouped_value(groups, fraction_part=fraction_part, negative=negative)


def _parse_grouped_integer(
    groups: list[str],
    *,
    negative: bool,
) -> ParsedNumericText | None:
    """Parse grouped integer text."""
    return _grouped_value(groups, negative=negative)


def _grouped_value(
    groups: list[str] | tuple[str, ...],
    *,
    negative: bool,
    fraction_part: str | None = None,
) -> ParsedNumericText | None:
    """Return a parsed grouped number value."""
    if not _is_valid_grouped_integer_parts(groups):
        return None

    integer_text = "".join(groups)
    if not _integer_part_length_is_eligible(integer_text):
        return None

    if fraction_part is None:
        value = int(integer_text)
        return ParsedNumericText(value=-value if negative and value else value)

    if not fraction_part.isdigit():
        return None
    if not 0 < len(fraction_part) <= _MAX_FRACTION_DIGITS:
        return None

    normalized_fraction = fraction_part.rstrip("0")
    if not normalized_fraction:
        value = int(integer_text)
        return ParsedNumericText(value=-value if negative and value else value)

    sign = "-" if negative else ""
    return ParsedNumericText(value=f"{sign}{integer_text}.{normalized_fraction}")


def _is_valid_grouped_integer_parts(groups: tuple[str, ...] | list[str]) -> bool:
    """Return if integer groups form a valid thousands-grouped number."""
    if len(groups) < 2:
        return False
    first, *rest = groups
    if not first.isdigit() or not 1 <= len(first) <= 3 or first.startswith("0"):
        return False
    return all(part.isdigit() and len(part) == 3 for part in rest)


def _integer_part_length_is_eligible(integer_part: str) -> bool:
    """Return if an integer part has a safe size."""
    if not integer_part:
        return False
    if len(integer_part) > _MAX_INTEGER_DIGITS:
        return False
    return True


def _locale_group_separator(locale_hint: str) -> str | None:
    """Return the locale's punctuation group separator when known."""
    language = str(locale_hint or "").replace("_", "-").split("-", 1)[0].lower()
    if language == "de":
        return "."
    if language == "en":
        return ","
    return None


def _next_char_is_digit(text: str, index: int) -> bool:
    """Return if the character after index is a digit."""
    return index + 1 < len(text) and text[index + 1].isdigit()


def _looks_like_group_separator_after(text: str, end: int) -> bool:
    """Return if a following space likely continues the same grouped number."""
    if end >= len(text) or text[end] not in GROUP_SEPARATOR_SPACES:
        return False

    previous_digits = _previous_digit_run_length(text, end)
    next_digits = _next_digit_run_length(text, end + 1)
    return 1 <= previous_digits <= 3 and next_digits == 3


def _looks_like_group_separator_before(text: str, start: int) -> bool:
    """Return if a previous space likely continues the same grouped number."""
    if start <= 0 or text[start - 1] not in GROUP_SEPARATOR_SPACES:
        return False

    previous_digits = _previous_digit_run_length(text, start - 1)
    next_digits = _next_digit_run_length(text, start)
    return 1 <= previous_digits <= 3 and next_digits == 3


def _previous_digit_run_length(text: str, end: int) -> int:
    """Return the digit run length directly before end."""
    index = end - 1
    length = 0
    while index >= 0 and text[index].isdigit():
        length += 1
        index -= 1
    return length


def _next_digit_run_length(text: str, start: int) -> int:
    """Return the digit run length directly after start."""
    index = start
    length = 0
    while index < len(text) and text[index].isdigit():
        length += 1
        index += 1
    return length
