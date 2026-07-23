"""Text normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from .const import (
    CONF_NUMBER_NORMALIZER_ENABLED,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_REPLACEMENT_RULES,
    DEFAULT_MAX_BUFFER_CHARS,
    DEFAULT_SAFETY_TAIL_CHARS,
    RULE_ENABLED,
    RULE_DISABLED,
    RULE_NAME,
    RULE_FIND,
    RULE_IGNORE_CASE,
    RULE_CASE_SENSITIVE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_REPLACE,
)
from .date_normalizer import (
    DateNormalizer,
    is_date_token_punctuation,
    parse_date_normalizer,
)
from .emoji_normalizer import EmojiNormalizer, parse_emoji_normalizer
from .form_data import flatten_config_sections
from .markdown_normalizer import (
    MarkdownCleanupNormalizer,
    parse_markdown_cleanup_normalizer,
)

_CONTROL_TAG_RE = re.compile(r"(<[^>]*>|\[[^\]]*\])")
_NUMERIC_TEXT_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_SENTENCE_PUNCTUATION = ".!?:;"
_CLOSING_PUNCTUATION = "\"')]}"
_STRUCTURAL_PREFIX_CHARS = ".,:/+-"
_STRUCTURAL_SUFFIX_CHARS = ":/+-"
_MAX_INTEGER_DIGITS = 9
_MAX_FRACTION_DIGITS = 6

NumberConverter = Callable[[int | str, str], str]


class RuleMode(StrEnum):
    """Supported Replacement Rule modes."""

    LITERAL = RULE_MODE_LITERAL
    REGEX = RULE_MODE_REGEX


class RuleValidationError(ValueError):
    """Raised when a Replacement Rule is invalid."""


class NumberNormalizationError(ValueError):
    """Raised when Number Normalizer configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ReplacementRule:
    """A configured text Replacement Rule."""

    find: str
    replace: str
    mode: RuleMode = RuleMode.LITERAL
    ignore_case: bool = False
    enabled: bool = True
    name: str = ""

    def __post_init__(self) -> None:
        """Validate direct rule construction."""
        if not isinstance(self.mode, RuleMode):
            object.__setattr__(self, "mode", RuleMode(str(self.mode)))
        self.validate()

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> "ReplacementRule":
        """Build a rule from config-flow data."""
        raw_mode = raw.get(RULE_MODE) or RuleMode.LITERAL.value
        try:
            mode = RuleMode(str(raw_mode))
        except ValueError as err:
            raise RuleValidationError(f"Unsupported rule mode: {raw_mode!r}") from err

        if RULE_DISABLED in raw:
            enabled = not bool(raw.get(RULE_DISABLED))
        else:
            enabled = bool(raw.get(RULE_ENABLED, True))

        if RULE_CASE_SENSITIVE in raw:
            ignore_case = not bool(raw.get(RULE_CASE_SENSITIVE))
        else:
            ignore_case = bool(raw.get(RULE_IGNORE_CASE, True))

        return cls(
            find=str(raw.get(RULE_FIND, "")),
            replace=str(raw.get(RULE_REPLACE, "")),
            mode=mode,
            ignore_case=ignore_case,
            enabled=enabled,
            name=str(raw.get(RULE_NAME, "") or "").strip(),
        )

    def validate(self) -> None:
        """Validate this rule."""
        if not self.find:
            raise RuleValidationError("Replacement rule find value cannot be empty")

        if self.mode is RuleMode.REGEX:
            try:
                re.compile(self.find, self._flags)
            except re.error as err:
                raise RuleValidationError(f"Invalid regex rule {self.find!r}: {err}") from err

    @property
    def _flags(self) -> int:
        """Return regex flags for this rule."""
        return re.IGNORECASE if self.ignore_case else 0

    def apply(self, text: str) -> str:
        """Apply this rule once to a text segment."""
        if not self.enabled:
            return text

        if self.mode is RuleMode.REGEX:
            return re.sub(self.find, self.replace, text, flags=self._flags)

        if self.ignore_case:
            return re.sub(
                re.escape(self.find),
                lambda _match: self.replace,
                text,
                flags=self._flags,
            )

        return text.replace(self.find, self.replace)


@dataclass(frozen=True, slots=True)
class NumberNormalizer:
    """A configured Number Normalizer."""

    enabled: bool = False
    language: str = ""
    converter: NumberConverter | None = None

    def normalize(self, text: str) -> str:
        """Spell eligible numeric text as language-specific words."""
        if not self.enabled or not self.language:
            return text

        return _NUMERIC_TEXT_RE.sub(self._replace_match, text)

    @property
    def _number_converter(self) -> NumberConverter:
        """Return the configured converter or the num2words-backed converter."""
        return self.converter or _spellout_number

    def _replace_match(self, match: re.Match[str]) -> str:
        """Replace one eligible numeric token."""
        number_text = match.group(0)
        if not _is_eligible_numeric_match(match):
            return number_text

        digit_sequence = _leading_zero_integer_digits(number_text)
        if digit_sequence is not None:
            try:
                return _spellout_digit_sequence(
                    digit_sequence,
                    self.language,
                    self._number_converter,
                    negative=number_text.startswith("-"),
                )
            except (
                ArithmeticError,
                ImportError,
                NotImplementedError,
                TypeError,
                ValueError,
            ):
                return number_text

        value = _number_value(number_text)
        if value is None:
            return number_text

        try:
            return str(self._number_converter(value, self.language))
        except (
            ArithmeticError,
            ImportError,
            NotImplementedError,
            TypeError,
            ValueError,
        ):
            return number_text


def parse_number_normalizer(raw_config: Mapping[str, Any]) -> NumberNormalizer:
    """Parse and validate Number Normalizer configuration."""
    enabled = bool(raw_config.get(CONF_NUMBER_NORMALIZER_ENABLED, False))
    language = str(raw_config.get(CONF_NUMBER_SPELLOUT_LANGUAGE, "") or "").strip()
    if not enabled:
        return NumberNormalizer(enabled=False, language=language)

    if not language:
        raise NumberNormalizationError("Number Spellout Language is required")

    languages = supported_number_spellout_languages()
    if not languages:
        raise NumberNormalizationError("num2words is not available")
    if language not in languages:
        raise NumberNormalizationError(
            f"Unsupported Number Spellout Language: {language}"
        )

    return NumberNormalizer(enabled=True, language=language)


def supported_number_spellout_languages() -> tuple[str, ...]:
    """Return languages supported by num2words."""
    try:
        from num2words import CONVERTER_CLASSES
    except ImportError:
        return ()

    return tuple(sorted(str(language) for language in CONVERTER_CLASSES))


def normalize_text_from_raw_config(text: str, raw_config: Mapping[str, Any]) -> str:
    """Normalize text using raw Proxy Configuration data."""
    raw_config = flatten_config_sections(raw_config)
    return normalize_text(
        text,
        parse_rules(raw_config.get(CONF_REPLACEMENT_RULES, [])),
        markdown_normalizer=parse_markdown_cleanup_normalizer(raw_config),
        emoji_normalizer=parse_emoji_normalizer(raw_config),
        number_normalizer=parse_number_normalizer(raw_config),
        date_normalizer=parse_date_normalizer(raw_config),
    )


def parse_rules(raw_rules: Any) -> tuple[ReplacementRule, ...]:
    """Parse and validate Replacement Rules from configuration."""
    if raw_rules in (None, ""):
        return ()

    if not isinstance(raw_rules, list):
        raise RuleValidationError("Replacement rules must be a list")

    rules: list[ReplacementRule] = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, Mapping):
            raise RuleValidationError(f"Replacement rule {index} must be an object")
        try:
            rules.append(ReplacementRule.from_raw(raw_rule))
        except RuleValidationError as err:
            raise RuleValidationError(f"Replacement rule {index}: {err}") from err

    return tuple(rules)


def normalize_text(
    text: str,
    rules: Iterable[ReplacementRule],
    number_normalizer: NumberNormalizer | None = None,
    date_normalizer: DateNormalizer | None = None,
    markdown_normalizer: MarkdownCleanupNormalizer | None = None,
    emoji_normalizer: EmojiNormalizer | None = None,
) -> str:
    """Normalize text while preserving Provider Control Tags."""
    if not text:
        return text

    normalized = _normalize_preserving_control_tags(
        text,
        lambda segment: _apply_rules(segment, rules),
    )
    if markdown_normalizer is not None:
        normalized = markdown_normalizer.normalize(normalized)
    return _normalize_preserving_control_tags(
        normalized,
        lambda segment: _apply_date_and_number_normalizers(
            segment,
            number_normalizer,
            date_normalizer,
            emoji_normalizer,
        ),
    )


def _normalize_preserving_control_tags(
    text: str,
    normalize_segment: Callable[[str], str],
) -> str:
    """Normalize speech text segments while preserving Provider Control Tags."""
    parts: list[str] = []
    cursor = 0
    for match in _CONTROL_TAG_RE.finditer(text):
        if match.start() > cursor:
            parts.append(normalize_segment(text[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()

    if cursor < len(text):
        parts.append(normalize_segment(text[cursor:]))

    return "".join(parts)


async def normalize_stream(
    chunks: AsyncGenerator[str],
    rules: Iterable[ReplacementRule],
    number_normalizer: NumberNormalizer | None = None,
    date_normalizer: DateNormalizer | None = None,
    markdown_normalizer: MarkdownCleanupNormalizer | None = None,
    emoji_normalizer: EmojiNormalizer | None = None,
    *,
    safety_tail_chars: int = DEFAULT_SAFETY_TAIL_CHARS,
    max_buffer_chars: int = DEFAULT_MAX_BUFFER_CHARS,
) -> AsyncGenerator[str]:
    """Normalize an async text stream with bounded buffering."""
    validate_streaming_buffer_config(safety_tail_chars, max_buffer_chars)

    pending = ""
    materialized_rules = tuple(rules)

    async for chunk in chunks:
        if not chunk:
            continue
        pending += chunk

        while flush_at := _next_flush_index(
            pending,
            safety_tail_chars=safety_tail_chars,
            max_buffer_chars=max_buffer_chars,
        ):
            segment = pending[:flush_at]
            pending = pending[flush_at:]
            if segment:
                yield normalize_text(
                    segment,
                    materialized_rules,
                    markdown_normalizer=markdown_normalizer,
                    number_normalizer=number_normalizer,
                    date_normalizer=date_normalizer,
                    emoji_normalizer=emoji_normalizer,
                )

    if pending:
        yield normalize_text(
            pending,
            materialized_rules,
            markdown_normalizer=markdown_normalizer,
            number_normalizer=number_normalizer,
            date_normalizer=date_normalizer,
            emoji_normalizer=emoji_normalizer,
        )


def validate_streaming_buffer_config(
    safety_tail_chars: int,
    max_buffer_chars: int,
) -> None:
    """Validate streaming buffer settings."""
    if safety_tail_chars < 0:
        raise ValueError("Minimal Lookahead Buffer Length must be zero or greater")
    if max_buffer_chars <= 0:
        raise ValueError("Maximal Buffer Limit must be greater than zero")
    if max_buffer_chars <= safety_tail_chars:
        raise ValueError(
            "Maximal Buffer Limit must be greater than Minimal Lookahead Buffer Length"
        )


def _apply_rules(text: str, rules: Iterable[ReplacementRule]) -> str:
    """Apply enabled rules to one speech-text segment."""
    normalized = text
    for rule in rules:
        normalized = rule.apply(normalized)
    return normalized


def _apply_date_and_number_normalizers(
    text: str,
    number_normalizer: NumberNormalizer | None,
    date_normalizer: DateNormalizer | None,
    emoji_normalizer: EmojiNormalizer | None,
) -> str:
    """Apply Emoji Normalizer, Date Normalizer, then Number Normalizer."""
    normalized = text
    if emoji_normalizer is not None:
        normalized = emoji_normalizer.normalize(normalized)
    if date_normalizer is not None:
        normalized = date_normalizer.normalize(normalized)
    if number_normalizer is not None:
        normalized = number_normalizer.normalize(normalized)
    return normalized


def _number_value(number_text: str) -> int | str | None:
    """Return a converter value for eligible numeric text."""
    negative = number_text.startswith("-")
    unsigned = number_text[1:] if negative else number_text
    separator = _decimal_separator(unsigned)

    if separator is None:
        if not _integer_part_is_eligible(unsigned):
            return None
        return int(number_text)

    integer_part, fraction_part = unsigned.split(separator, 1)
    if not _integer_part_length_is_eligible(integer_part):
        return None
    if len(fraction_part) > _MAX_FRACTION_DIGITS:
        return None

    normalized_integer = integer_part.lstrip("0") or "0"
    normalized_fraction = fraction_part.rstrip("0")
    if not normalized_fraction:
        value = int(normalized_integer)
        return -value if negative and value else value

    sign = "-" if negative else ""
    return f"{sign}{normalized_integer}.{normalized_fraction}"


def _decimal_separator(unsigned_number_text: str) -> str | None:
    """Return the single decimal separator in unsigned text if present."""
    if "." in unsigned_number_text and "," in unsigned_number_text:
        return None
    if "." in unsigned_number_text:
        return "."
    if "," in unsigned_number_text:
        return ","
    return None


def _integer_part_is_eligible(integer_part: str) -> bool:
    """Return if an integer part is safe to spell out."""
    if not _integer_part_length_is_eligible(integer_part):
        return False
    if len(integer_part) > 1 and integer_part.startswith("0"):
        return False
    return True


def _integer_part_length_is_eligible(integer_part: str) -> bool:
    """Return if an integer part has a safe size."""
    if not integer_part:
        return False
    if len(integer_part) > _MAX_INTEGER_DIGITS:
        return False
    return True


def _leading_zero_integer_digits(number_text: str) -> tuple[int, ...] | None:
    """Return digits for a simple leading-zero integer token."""
    unsigned = number_text[1:] if number_text.startswith("-") else number_text
    if _decimal_separator(unsigned) is not None:
        return None
    if not _integer_part_length_is_eligible(unsigned):
        return None
    if len(unsigned) <= 1 or not unsigned.startswith("0"):
        return None
    return tuple(int(char) for char in unsigned)


def _spellout_digit_sequence(
    digits: tuple[int, ...],
    language: str,
    converter: NumberConverter,
    *,
    negative: bool,
) -> str:
    """Spell a leading-zero integer as individual digits."""
    words = [str(converter(digit, language)) for digit in digits]
    if negative:
        words.insert(0, _localized_minus_word(language, converter))
    return " ".join(words)


def _localized_minus_word(language: str, converter: NumberConverter) -> str:
    """Return a localized minus word using the configured converter."""
    minus_one = str(converter(-1, language))
    one = str(converter(1, language))
    if minus_one.endswith(one):
        minus_word = minus_one[: -len(one)].strip()
        if minus_word:
            return minus_word
    return "minus"


def _is_eligible_numeric_match(match: re.Match[str]) -> bool:
    """Return if a numeric regex match is structurally safe to spell out."""
    text = match.string
    start = match.start()
    end = match.end()

    if start > 0:
        previous = text[start - 1]
        if (
            previous.isalnum()
            or previous == "_"
            or previous in _STRUCTURAL_PREFIX_CHARS
        ):
            return False

    if end < len(text):
        next_char = text[end]
        if (
            next_char.isalnum()
            or next_char == "_"
            or next_char in _STRUCTURAL_SUFFIX_CHARS
        ):
            return False
        if next_char in ".," and end + 1 < len(text) and text[end + 1].isdigit():
            return False

    return True


def _spellout_number(value: int | str, language: str) -> str:
    """Spell out a number with num2words."""
    try:
        from num2words import num2words
    except ImportError as err:
        raise NumberNormalizationError("num2words is not available") from err

    return str(num2words(value, lang=language))


def _next_flush_index(
    pending: str,
    *,
    safety_tail_chars: int,
    max_buffer_chars: int,
) -> int | None:
    """Return the next safe flush index for pending text."""
    protected_start = max(0, len(pending) - safety_tail_chars)
    sentence_boundary = _find_sentence_boundary(pending, protected_start)
    if sentence_boundary is not None:
        return _avoid_unclosed_control_tag(pending, sentence_boundary)

    if len(pending) <= max_buffer_chars:
        return None

    whitespace_boundary = _find_whitespace_boundary(pending, protected_start)
    if whitespace_boundary is None:
        return None
    return _avoid_unclosed_control_tag(pending, whitespace_boundary)


def _find_sentence_boundary(text: str, protected_start: int) -> int | None:
    """Find a sentence-like boundary before protected_start."""
    index = 0
    best_boundary: int | None = None
    while index < protected_start:
        char = text[index]
        if char not in _SENTENCE_PUNCTUATION:
            index += 1
            continue

        if _is_decimal_separator(text, index):
            index += 1
            continue

        if is_date_token_punctuation(text, index):
            index += 1
            continue

        lookahead = index + 1
        while lookahead < len(text) and text[lookahead] in _CLOSING_PUNCTUATION:
            lookahead += 1

        if lookahead < len(text) and text[lookahead].isspace():
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead <= protected_start:
                best_boundary = lookahead

        index += 1

    return best_boundary


def _find_whitespace_boundary(text: str, protected_start: int) -> int | None:
    """Find the last whitespace boundary before protected_start."""
    for index in range(protected_start - 1, -1, -1):
        if text[index].isspace():
            return index + 1
    return None


def _avoid_unclosed_control_tag(text: str, flush_at: int) -> int | None:
    """Avoid flushing through an incomplete Provider Control Tag."""
    prefix = text[:flush_at]
    last_square_open = prefix.rfind("[")
    last_square_close = prefix.rfind("]")
    last_angle_open = prefix.rfind("<")
    last_angle_close = prefix.rfind(">")

    candidates: list[int] = []
    if last_square_open > last_square_close:
        candidates.append(last_square_open)
    if last_angle_open > last_angle_close:
        candidates.append(last_angle_open)

    if not candidates:
        return flush_at

    safe_flush = min(candidates)
    if safe_flush == 0:
        return None
    return safe_flush


def _is_decimal_separator(text: str, index: int) -> bool:
    """Return true if punctuation at index is decimal punctuation."""
    if text[index] not in ".,":
        return False
    return (
        index > 0
        and index + 1 < len(text)
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )
