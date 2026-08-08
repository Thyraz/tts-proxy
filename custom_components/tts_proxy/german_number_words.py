"""German number word rendering helpers."""

from __future__ import annotations

_UNITS = {
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
}
_UNIT_PREFIXES = {
    1: "ein",
    2: "zwei",
    3: "drei",
    4: "vier",
    5: "fünf",
    6: "sechs",
    7: "sieben",
    8: "acht",
    9: "neun",
}
_TEENS = {
    10: "zehn",
    11: "elf",
    12: "zwölf",
    13: "dreizehn",
    14: "vierzehn",
    15: "fünfzehn",
    16: "sechzehn",
    17: "siebzehn",
    18: "achtzehn",
    19: "neunzehn",
}
_TENS = {
    20: "zwanzig",
    30: "dreißig",
    40: "vierzig",
    50: "fünfzig",
    60: "sechzig",
    70: "siebzig",
    80: "achtzig",
    90: "neunzig",
}


def spellout_german_number_with_word_parts(value: int | str) -> str:
    """Spell a German cardinal number with separators between word parts."""
    if isinstance(value, int):
        if value < 0:
            return f"minus {'-'.join(_unsigned_integer_parts(abs(value)))}"
        return "-".join(_integer_parts(value))

    text = str(value)
    if "." not in text:
        return spellout_german_number_with_word_parts(int(text))

    negative = text.startswith("-")
    unsigned = text[1:] if negative else text
    integer_text, fraction_text = unsigned.split(".", 1)
    if not integer_text.isdigit() or not fraction_text.isdigit():
        raise ValueError(f"Unsupported German number text: {value!r}")

    integer_words = "-".join(_integer_parts(int(integer_text)))
    if negative:
        integer_words = f"minus {integer_words}"

    fraction_words = " ".join(_UNITS[int(char)] for char in fraction_text)
    return f"{integer_words} Komma {fraction_words}"


def _integer_parts(value: int) -> tuple[str, ...]:
    """Return German cardinal word parts for one integer."""
    if value < 0:
        raise ValueError(f"Unsupported unsigned German number: {value!r}")
    return _unsigned_integer_parts(value)


def _unsigned_integer_parts(value: int) -> tuple[str, ...]:
    """Return German cardinal word parts for one unsigned integer."""
    if value == 0:
        return ("null",)

    parts: list[str] = []
    rest = value

    millions, rest = divmod(rest, 1_000_000)
    if millions:
        if millions == 1:
            parts.extend(("eine", "million"))
        else:
            parts.extend(_under_thousand_parts(millions))
            parts.append("millionen")

    thousands, rest = divmod(rest, 1_000)
    if thousands:
        if thousands == 1:
            parts.append("ein")
        else:
            parts.extend(_under_thousand_parts(thousands))
        parts.append("tausend")

    if rest:
        parts.extend(_under_thousand_parts(rest))

    return tuple(parts)


def _under_thousand_parts(value: int) -> tuple[str, ...]:
    """Return German cardinal word parts for a value from 1 to 999."""
    if not 0 < value < 1000:
        raise ValueError(f"Unsupported German number group: {value!r}")

    hundreds, rest = divmod(value, 100)
    parts: list[str] = []
    if hundreds:
        parts.append(_UNIT_PREFIXES[hundreds])
        parts.append("hundert")
    if rest:
        parts.extend(_under_hundred_parts(rest))
    return tuple(parts)


def _under_hundred_parts(value: int) -> tuple[str, ...]:
    """Return German cardinal word parts for a value from 1 to 99."""
    if value < 10:
        return (_UNITS[value],)
    if value < 20:
        return (_TEENS[value],)

    tens, unit = divmod(value, 10)
    tens_word = _TENS[tens * 10]
    if unit == 0:
        return (tens_word,)
    return (_UNIT_PREFIXES[unit], "und", tens_word)
