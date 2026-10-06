"""Text normalization for the TTS Proxy integration."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_NUMBER_ALLOW_GROUPED_NUMBERS,
    CONF_NUMBER_NORMALIZER_ENABLED,
    CONF_NUMBER_SEPARATE_GERMAN_WORD_PARTS,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_OUTPUT_LANGUAGE,
    CONF_REPLACEMENT_RULES,
    DEFAULT_MAX_BUFFER_CHARS,
    DEFAULT_SAFETY_TAIL_CHARS,
)
from .date_normalizer import (
    DateNormalizer,
    is_date_token_punctuation,
    parse_date_normalizer,
)
from .emoji_normalizer import EmojiNormalizer, parse_emoji_normalizer
from .form_data import flatten_config_sections
from .german_number_words import spellout_german_number_with_word_parts
from .markdown_normalizer import (
    MarkdownCleanupNormalizer,
    parse_markdown_cleanup_normalizer,
)
from .numeric_text import (
    has_numeric_boundaries,
    numeric_text_re,
    parse_numeric_text,
)
from .rules import (
    EntityStateReport,
    ReplacementRule,  # noqa: F401 - Preserve the public replacement-rule import.
    RuleMode,  # noqa: F401 - Preserve the public replacement-rule import.
    RuleValidationError,
    TextProcessingRule,
    resolve_rules,
)
from .text_cleanup_normalizer import (
    TextCleanupNormalizer,
    parse_text_cleanup_normalizer,
)
from .text_insertion import TextInsertionProcessor
from .time_normalizer import TimeNormalizer, parse_time_normalizer
from .unit_normalizer import UnitNormalizer, parse_unit_normalizer

_CONTROL_TAG_RE = re.compile(r"(<[^>]*>|\[[^\]]*\])")
_SENTENCE_PUNCTUATION = ".!?:;"
_CLOSING_PUNCTUATION = "\"')]}"

NumberConverter = Callable[[int | str, str], str]


class NumberNormalizationError(ValueError):
    """Raised when Number Normalizer configuration is invalid."""


@dataclass(frozen=True, slots=True)
class NumberNormalizer:
    """A configured Number Normalizer."""

    enabled: bool = False
    language: str = ""
    allow_grouped_numbers: bool = False
    separate_german_word_parts: bool = False
    locale_hint: str = ""
    converter: NumberConverter | None = None

    def normalize(self, text: str) -> str:
        """Spell eligible numeric text as language-specific words."""
        if not self.enabled or not self.language:
            return text

        return numeric_text_re(allow_grouped_numbers=self.allow_grouped_numbers).sub(
            self._replace_match, text
        )

    @property
    def _number_converter(self) -> NumberConverter:
        """Return the configured converter or the num2words-backed converter."""
        return self.converter or _spellout_number

    def _replace_match(self, match: re.Match[str]) -> str:
        """Replace one eligible numeric token."""
        number_text = match.group(0)
        if not has_numeric_boundaries(match.string, match.start(), match.end()):
            return number_text

        parsed = parse_numeric_text(
            number_text,
            allow_grouped_numbers=self.allow_grouped_numbers,
            locale_hint=self.locale_hint or self.language,
        )
        if parsed is None:
            return number_text

        if parsed.digit_sequence is not None:
            try:
                return _spellout_digit_sequence(
                    parsed.digit_sequence,
                    self.language,
                    self._number_converter,
                    negative=parsed.negative,
                )
            except (
                ArithmeticError,
                ImportError,
                NotImplementedError,
                TypeError,
                ValueError,
            ):
                return number_text

        if parsed.value is None:
            return number_text

        try:
            if (
                self.separate_german_word_parts
                and _supports_german_word_part_separation(self.language)
            ):
                return spellout_german_number_with_word_parts(parsed.value)
            return str(self._number_converter(parsed.value, self.language))
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
    allow_grouped_numbers = bool(
        raw_config.get(CONF_NUMBER_ALLOW_GROUPED_NUMBERS, False)
    )
    separate_german_word_parts = bool(
        raw_config.get(CONF_NUMBER_SEPARATE_GERMAN_WORD_PARTS, False)
    )
    output_language = str(raw_config.get(CONF_OUTPUT_LANGUAGE, "") or "")
    locale_hint = _number_locale_hint(language, output_language)
    if not enabled:
        return NumberNormalizer(
            enabled=False,
            language=language,
            allow_grouped_numbers=allow_grouped_numbers,
            separate_german_word_parts=separate_german_word_parts,
            locale_hint=locale_hint,
        )

    if not language:
        raise NumberNormalizationError("Number Spellout Language is required")

    languages = supported_number_spellout_languages()
    if not languages:
        raise NumberNormalizationError("num2words is not available")
    if language not in languages:
        raise NumberNormalizationError(
            f"Unsupported Number Spellout Language: {language}"
        )

    return NumberNormalizer(
        enabled=True,
        language=language,
        allow_grouped_numbers=allow_grouped_numbers,
        separate_german_word_parts=separate_german_word_parts,
        locale_hint=locale_hint,
    )


def supported_number_spellout_languages() -> tuple[str, ...]:
    """Return languages supported by num2words."""
    try:
        from num2words import CONVERTER_CLASSES
    except ImportError:
        return ()

    return tuple(sorted(str(language) for language in CONVERTER_CLASSES))


def _number_locale_hint(number_language: str, output_language: str) -> str:
    """Return the best locale hint for ambiguous grouped numbers."""
    return number_language or output_language


def _supports_german_word_part_separation(language: str) -> bool:
    """Return if the selected number spellout language has curated separation."""
    return str(language or "").replace("-", "_").lower() == "de"


def normalize_text_from_raw_config(
    text: str,
    raw_config: Mapping[str, Any],
    *,
    entity_states: Mapping[str, str | EntityStateReport] | None = None,
) -> str:
    """Normalize text using raw Proxy Configuration data."""
    raw_config = flatten_config_sections(raw_config)
    return normalize_text(
        text,
        resolve_rules(
            parse_rules(raw_config.get(CONF_REPLACEMENT_RULES, [])), entity_states
        ),
        markdown_normalizer=parse_markdown_cleanup_normalizer(raw_config),
        text_cleanup_normalizer=parse_text_cleanup_normalizer(raw_config),
        emoji_normalizer=parse_emoji_normalizer(raw_config),
        date_normalizer=parse_date_normalizer(raw_config),
        time_normalizer=parse_time_normalizer(raw_config),
        unit_normalizer=parse_unit_normalizer(raw_config),
        number_normalizer=parse_number_normalizer(raw_config),
    )


def parse_rules(raw_rules: Any) -> tuple[TextProcessingRule, ...]:
    """Parse and validate Text Processing Rules from configuration."""
    if raw_rules in (None, ""):
        return ()

    if not isinstance(raw_rules, list):
        raise RuleValidationError("Text processing rules must be a list")

    rules: list[TextProcessingRule] = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, Mapping):
            raise RuleValidationError(f"Text processing rule {index} must be an object")
        try:
            rules.append(TextProcessingRule.from_raw(raw_rule))
        except RuleValidationError as err:
            raise RuleValidationError(f"Text processing rule {index}: {err}") from err

    return tuple(rules)


def normalize_text(
    text: str,
    rules: Iterable[TextProcessingRule],
    number_normalizer: NumberNormalizer | None = None,
    date_normalizer: DateNormalizer | None = None,
    markdown_normalizer: MarkdownCleanupNormalizer | None = None,
    emoji_normalizer: EmojiNormalizer | None = None,
    text_cleanup_normalizer: TextCleanupNormalizer | None = None,
    unit_normalizer: UnitNormalizer | None = None,
    time_normalizer: TimeNormalizer | None = None,
    *,
    entity_states: Mapping[str, str | EntityStateReport] | None = None,
) -> str:
    """Normalize a logical message, resolving conditions once."""
    if not text:
        return text
    rules = resolve_rules(rules, entity_states)
    normalized = _normalize_before_insertions(text, rules, markdown_normalizer)
    normalized = TextInsertionProcessor(rules).feed(normalized, final=True)
    return _normalize_after_insertions(
        normalized,
        text_cleanup_normalizer,
        number_normalizer,
        date_normalizer,
        emoji_normalizer,
        time_normalizer,
        unit_normalizer,
    )


def _normalize_before_insertions(
    text: str,
    rules: Iterable[TextProcessingRule],
    markdown_normalizer: MarkdownCleanupNormalizer | None,
) -> str:
    """Apply replacements and Markdown Cleanup before insertion boundaries."""
    normalized = _normalize_preserving_control_tags(
        text,
        lambda segment: _apply_rules(segment, rules),
    )
    if markdown_normalizer is not None:
        normalized = markdown_normalizer.normalize(normalized)
    return normalized


def _normalize_after_insertions(
    text: str,
    text_cleanup_normalizer: TextCleanupNormalizer | None,
    number_normalizer: NumberNormalizer | None,
    date_normalizer: DateNormalizer | None,
    emoji_normalizer: EmojiNormalizer | None,
    time_normalizer: TimeNormalizer | None,
    unit_normalizer: UnitNormalizer | None,
) -> str:
    """Clean and normalize speech text while leaving inserted tags opaque."""
    if text_cleanup_normalizer is not None:
        text = _normalize_preserving_control_tags(
            text, text_cleanup_normalizer.normalize
        )
    return _normalize_preserving_control_tags(
        text,
        lambda segment: _apply_builtin_normalizers(
            segment,
            number_normalizer,
            date_normalizer,
            emoji_normalizer,
            time_normalizer,
            unit_normalizer,
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
    rules: Iterable[TextProcessingRule],
    number_normalizer: NumberNormalizer | None = None,
    date_normalizer: DateNormalizer | None = None,
    markdown_normalizer: MarkdownCleanupNormalizer | None = None,
    emoji_normalizer: EmojiNormalizer | None = None,
    text_cleanup_normalizer: TextCleanupNormalizer | None = None,
    unit_normalizer: UnitNormalizer | None = None,
    time_normalizer: TimeNormalizer | None = None,
    *,
    safety_tail_chars: int = DEFAULT_SAFETY_TAIL_CHARS,
    max_buffer_chars: int = DEFAULT_MAX_BUFFER_CHARS,
    entity_states: Mapping[str, str | EntityStateReport] | None = None,
) -> AsyncGenerator[str]:
    """Normalize buffered text with one condition snapshot and insertion state."""
    validate_streaming_buffer_config(safety_tail_chars, max_buffer_chars)
    rules = resolve_rules(rules, entity_states)
    insertions = TextInsertionProcessor(rules)
    pending = ""

    def process(segment: str, *, final: bool = False) -> str:
        normalized = _normalize_before_insertions(segment, rules, markdown_normalizer)
        inserted = insertions.feed(normalized, final=final)
        return _normalize_after_insertions(
            inserted,
            text_cleanup_normalizer,
            number_normalizer,
            date_normalizer,
            emoji_normalizer,
            time_normalizer,
            unit_normalizer,
        )

    async for chunk in chunks:
        if not chunk:
            continue
        pending += chunk
        while flush_at := _next_flush_index(
            pending,
            safety_tail_chars=safety_tail_chars,
            max_buffer_chars=max_buffer_chars,
        ):
            segment, pending = pending[:flush_at], pending[flush_at:]
            if normalized := process(segment):
                yield normalized
    if normalized := process(pending, final=True):
        yield normalized


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


def _apply_rules(text: str, rules: Iterable[TextProcessingRule]) -> str:
    """Apply enabled rules to one speech-text segment."""
    normalized = text
    for rule in rules:
        normalized = rule.apply(normalized)
    return normalized


def _apply_builtin_normalizers(
    text: str,
    number_normalizer: NumberNormalizer | None,
    date_normalizer: DateNormalizer | None,
    emoji_normalizer: EmojiNormalizer | None,
    time_normalizer: TimeNormalizer | None,
    unit_normalizer: UnitNormalizer | None,
) -> str:
    """Apply Emoji, Date, Time, Unit, then Number Normalizers."""
    normalized = text
    if emoji_normalizer is not None:
        normalized = emoji_normalizer.normalize(normalized)
    if date_normalizer is not None:
        normalized = date_normalizer.normalize(normalized)
    if time_normalizer is not None:
        normalized = time_normalizer.normalize(normalized)
    if unit_normalizer is not None:
        normalized = unit_normalizer.normalize(normalized)
    if number_normalizer is not None:
        normalized = number_normalizer.normalize(normalized)
    return normalized


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
