"""Text normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from .const import (
    DEFAULT_MAX_BUFFER_CHARS,
    DEFAULT_SAFETY_TAIL_CHARS,
    RULE_ENABLED,
    RULE_DISABLED,
    RULE_FIND,
    RULE_IGNORE_CASE,
    RULE_CASE_SENSITIVE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_REPLACE,
)

_CONTROL_TAG_RE = re.compile(r"(<[^>]*>|\[[^\]]*\])")
_SENTENCE_PUNCTUATION = ".!?:;"
_CLOSING_PUNCTUATION = "\"')]}"


class RuleMode(StrEnum):
    """Supported Replacement Rule modes."""

    LITERAL = RULE_MODE_LITERAL
    REGEX = RULE_MODE_REGEX


class RuleValidationError(ValueError):
    """Raised when a Replacement Rule is invalid."""


@dataclass(frozen=True, slots=True)
class ReplacementRule:
    """A configured text Replacement Rule."""

    find: str
    replace: str
    mode: RuleMode = RuleMode.LITERAL
    ignore_case: bool = False
    enabled: bool = True

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


def normalize_text(text: str, rules: Iterable[ReplacementRule]) -> str:
    """Normalize text while preserving Provider Control Tags."""
    if not text:
        return text

    parts: list[str] = []
    cursor = 0
    for match in _CONTROL_TAG_RE.finditer(text):
        if match.start() > cursor:
            parts.append(_apply_rules(text[cursor : match.start()], rules))
        parts.append(match.group(0))
        cursor = match.end()

    if cursor < len(text):
        parts.append(_apply_rules(text[cursor:], rules))

    return "".join(parts)


async def normalize_stream(
    chunks: AsyncGenerator[str],
    rules: Iterable[ReplacementRule],
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
                yield normalize_text(segment, materialized_rules)

    if pending:
        yield normalize_text(pending, materialized_rules)


def validate_streaming_buffer_config(
    safety_tail_chars: int,
    max_buffer_chars: int,
) -> None:
    """Validate streaming buffer settings."""
    if safety_tail_chars < 0:
        raise ValueError("Streaming Safety Tail must be zero or greater")
    if max_buffer_chars <= 0:
        raise ValueError("Streaming Buffer Limit must be greater than zero")
    if max_buffer_chars <= safety_tail_chars:
        raise ValueError("Streaming Buffer Limit must be greater than Streaming Safety Tail")


def _apply_rules(text: str, rules: Iterable[ReplacementRule]) -> str:
    """Apply enabled rules to one speech-text segment."""
    normalized = text
    for rule in rules:
        normalized = rule.apply(normalized)
    return normalized


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
