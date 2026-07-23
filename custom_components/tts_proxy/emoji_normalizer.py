"""Emoji normalization for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from .const import (
    CONF_EMOJI_HANDLING,
    CONF_EMOJI_LANGUAGE,
    CONF_EMOJI_NORMALIZER_ENABLED,
    EMOJI_HANDLING_REMOVE,
    EMOJI_HANDLING_SPELLOUT,
)

EmojiReplacementCallback = Callable[[str, Mapping[str, Any] | None], str]
EmojiReplacer = Callable[[str, EmojiReplacementCallback], str]

_EMOJI_METADATA_KEYS = {"E", "alias", "status", "variant"}


class EmojiHandling(StrEnum):
    """Supported Emoji Normalizer handling modes."""

    REMOVE = EMOJI_HANDLING_REMOVE
    SPELLOUT = EMOJI_HANDLING_SPELLOUT


class EmojiNormalizationError(ValueError):
    """Raised when Emoji Normalizer configuration is invalid."""


@dataclass(frozen=True, slots=True)
class EmojiNormalizer:
    """A configured Emoji Normalizer."""

    enabled: bool = False
    handling: EmojiHandling = EmojiHandling.SPELLOUT
    language: str = ""
    replacer: EmojiReplacer | None = None

    def __post_init__(self) -> None:
        """Normalize direct construction values."""
        if not isinstance(self.handling, EmojiHandling):
            object.__setattr__(self, "handling", EmojiHandling(str(self.handling)))

    def normalize(self, text: str) -> str:
        """Remove emoji or replace them with localized spoken names."""
        if not self.enabled or not text:
            return text

        if self.handling is EmojiHandling.REMOVE:
            replaced = self._emoji_replacer(text, lambda _chars, _data: "")
            if replaced == text:
                return text
            return _cleanup_removed_emoji_text(replaced)

        leading_whitespace = _edge_whitespace(text, leading=True)
        trailing_whitespace = _edge_whitespace(text, leading=False)
        replaced = self._emoji_replacer(text, self._spoken_emoji_replacement)
        if replaced == text:
            return text
        return _cleanup_spoken_emoji_text(
            replaced,
            leading_whitespace=leading_whitespace,
            trailing_whitespace=trailing_whitespace,
        )

    def _emoji_replacer(
        self,
        text: str,
        replace: EmojiReplacementCallback,
    ) -> str:
        """Return text after replacing emoji through the configured backend."""
        if self.replacer is not None:
            return self.replacer(text, replace)

        if self.handling is EmojiHandling.SPELLOUT:
            _load_emoji_languages((self.language, "en"))
        return _replace_emoji(text, replace)

    def _spoken_emoji_replacement(
        self,
        chars: str,
        data: Mapping[str, Any] | None,
    ) -> str:
        """Return one spoken emoji replacement."""
        name = _spoken_emoji_name(data, self.language)
        if not name:
            return chars
        return f", {name},"


def parse_emoji_normalizer(raw_config: Mapping[str, Any]) -> EmojiNormalizer:
    """Parse and validate Emoji Normalizer configuration."""
    enabled = bool(raw_config.get(CONF_EMOJI_NORMALIZER_ENABLED, False))
    raw_handling = raw_config.get(CONF_EMOJI_HANDLING) or EMOJI_HANDLING_SPELLOUT
    try:
        handling = EmojiHandling(str(raw_handling))
    except ValueError as err:
        raise EmojiNormalizationError(
            f"Unsupported Emoji Handling: {raw_handling}"
        ) from err

    language = str(raw_config.get(CONF_EMOJI_LANGUAGE, "") or "").strip()
    if not enabled:
        return EmojiNormalizer(enabled=False, handling=handling, language=language)

    languages = supported_emoji_languages()
    if not languages:
        raise EmojiNormalizationError("emoji is not available")

    if handling is EmojiHandling.SPELLOUT:
        if not language:
            raise EmojiNormalizationError("Emoji Language is required")
        if language not in languages:
            raise EmojiNormalizationError(f"Unsupported Emoji Language: {language}")

    return EmojiNormalizer(enabled=True, handling=handling, language=language)


def supported_emoji_languages() -> tuple[str, ...]:
    """Return languages supported by the emoji package."""
    try:
        from emoji import EMOJI_DATA, LANGUAGES
    except ImportError:
        return ()

    languages = set(str(language) for language in LANGUAGES)
    if not languages:
        for data in EMOJI_DATA.values():
            languages.update(
                str(key)
                for key in data
                if isinstance(key, str) and key not in _EMOJI_METADATA_KEYS
            )
            if languages:
                break

    return tuple(sorted(languages))


def default_emoji_language(
    output_language: str,
    emoji_languages: tuple[str, ...] | list[str],
) -> str:
    """Return the best default Emoji Language."""
    normalized_output = str(output_language or "").replace("-", "_")
    for candidate in (normalized_output, normalized_output[:2], "en"):
        if candidate in emoji_languages:
            return candidate
    return emoji_languages[0] if emoji_languages else ""


def _replace_emoji(
    text: str,
    replace: EmojiReplacementCallback,
) -> str:
    """Replace emoji with the emoji package."""
    try:
        import emoji
    except ImportError:
        return text

    return str(emoji.replace_emoji(text, replace=replace))


def _load_emoji_languages(languages: tuple[str, ...]) -> None:
    """Load emoji language data into EMOJI_DATA when the backend requires it."""
    try:
        import emoji
    except ImportError:
        return

    load_language = getattr(getattr(emoji, "config", None), "load_language", None)
    if load_language is None:
        return

    loaded: set[str] = set()
    for language in languages:
        if not language or language in loaded:
            continue
        loaded.add(language)
        try:
            load_language(language)
        except (TypeError, ValueError):
            continue


def _spoken_emoji_name(
    data: Mapping[str, Any] | None,
    language: str,
) -> str:
    """Return a speech-friendly emoji name from emoji metadata."""
    if not data:
        return ""

    raw_name = data.get(language) or data.get("en")
    if not isinstance(raw_name, str) or not raw_name:
        return ""

    name = raw_name.strip(":").replace("_", " ").strip()
    return re.sub(r"\s+", " ", name)


def _cleanup_spoken_emoji_text(
    text: str,
    *,
    leading_whitespace: str,
    trailing_whitespace: str,
) -> str:
    """Normalize comma spacing introduced by spoken emoji names."""
    text = re.sub(r"[ \t]*,[ \t]*", ", ", text)
    text = re.sub(r"(?:,\s*){2,}", ", ", text)
    text = re.sub(r"(^|[\r\n])\s*,\s*", r"\1", text)
    text = re.sub(r",\s*([.!?:;])", r"\1", text)
    text = re.sub(r"\s+([.!?:;])", r"\1", text)
    text = re.sub(r",\s*$", "", text)
    if leading_whitespace and text and not text.startswith(leading_whitespace):
        text = f"{leading_whitespace}{text}"
    if trailing_whitespace and text and not text.endswith(trailing_whitespace):
        text = f"{text}{trailing_whitespace}"
    return text


def _cleanup_removed_emoji_text(text: str) -> str:
    """Remove spacing artifacts introduced by deleted emoji."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.!?:;,])", r"\1", text)
    return text


def _edge_whitespace(text: str, *, leading: bool) -> str:
    """Return leading or trailing whitespace from text."""
    pattern = r"^\s+" if leading else r"\s+$"
    match = re.search(pattern, text)
    return match.group(0) if match else ""
