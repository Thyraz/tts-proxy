"""Configuration helpers for the TTS Proxy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_FINAL_TTS_ENTITY,
    CONF_MAX_BUFFER_CHARS,
    CONF_OUTPUT_LANGUAGE,
    CONF_REPLACEMENT_RULES,
    CONF_SAFETY_TAIL_CHARS,
    DEFAULT_MAX_BUFFER_CHARS,
    DEFAULT_NAME,
    DEFAULT_SAFETY_TAIL_CHARS,
)
from .normalizer import ReplacementRule, parse_rules, validate_streaming_buffer_config

CONF_NAME = "name"


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Validated Proxy Configuration."""

    name: str
    final_tts_entity: str
    output_language: str
    rules: tuple[ReplacementRule, ...]
    safety_tail_chars: int
    max_buffer_chars: int


def merged_entry_config(entry: Any) -> dict[str, Any]:
    """Merge config-entry data and options."""
    return {
        **dict(getattr(entry, "data", {}) or {}),
        **dict(getattr(entry, "options", {}) or {}),
    }


def parse_proxy_config(raw_config: dict[str, Any]) -> ProxyConfig:
    """Parse and validate Proxy Configuration."""
    safety_tail_chars = int(
        raw_config.get(CONF_SAFETY_TAIL_CHARS, DEFAULT_SAFETY_TAIL_CHARS)
    )
    max_buffer_chars = int(
        raw_config.get(CONF_MAX_BUFFER_CHARS, DEFAULT_MAX_BUFFER_CHARS)
    )
    validate_streaming_buffer_config(safety_tail_chars, max_buffer_chars)

    final_tts_entity = _clean_string(raw_config.get(CONF_FINAL_TTS_ENTITY))
    output_language = _clean_string(raw_config.get(CONF_OUTPUT_LANGUAGE))
    if not final_tts_entity:
        raise ValueError("Final TTS Entity is required")
    if not output_language:
        raise ValueError("Output Language is required")

    name = _clean_string(raw_config.get(CONF_NAME)) or DEFAULT_NAME

    return ProxyConfig(
        name=name,
        final_tts_entity=final_tts_entity,
        output_language=output_language,
        rules=parse_rules(raw_config.get(CONF_REPLACEMENT_RULES, [])),
        safety_tail_chars=safety_tail_chars,
        max_buffer_chars=max_buffer_chars,
    )


def serializable_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """Return normalized config data suitable for config-entry storage."""
    config = parse_proxy_config(raw_config)
    return {
        CONF_NAME: config.name,
        CONF_FINAL_TTS_ENTITY: config.final_tts_entity,
        CONF_OUTPUT_LANGUAGE: config.output_language,
        CONF_REPLACEMENT_RULES: raw_config.get(CONF_REPLACEMENT_RULES, []),
        CONF_SAFETY_TAIL_CHARS: config.safety_tail_chars,
        CONF_MAX_BUFFER_CHARS: config.max_buffer_chars,
    }


def _clean_string(value: Any) -> str:
    """Return a stripped string, treating None as missing."""
    if value is None:
        return ""
    return str(value).strip()
