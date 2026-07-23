"""Configuration helpers for the TTS Proxy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_DATE_INPUT_FORMATS,
    CONF_DATE_LOCALE,
    CONF_DATE_NORMALIZER_ENABLED,
    CONF_DATE_RENDERER,
    CONF_TARGET_TTS_ENTITY,
    CONF_MARKDOWN_CLEANUP_ENABLED,
    CONF_MARKDOWN_REMOVE_CODE_BLOCKS,
    CONF_MARKDOWN_REMOVE_DIVIDER_LINES,
    CONF_MARKDOWN_REMOVE_PLAIN_URLS,
    CONF_MARKDOWN_STRIP_BLOCKQUOTES,
    CONF_MARKDOWN_STRIP_EMPHASIS,
    CONF_MARKDOWN_STRIP_HEADINGS,
    CONF_MARKDOWN_STRIP_IMAGES,
    CONF_MARKDOWN_STRIP_INLINE_CODE,
    CONF_MARKDOWN_STRIP_LINKS,
    CONF_MARKDOWN_STRIP_LIST_MARKERS,
    CONF_MARKDOWN_STRIP_STRIKETHROUGH,
    CONF_MARKDOWN_STRIP_TABLES,
    CONF_MAX_BUFFER_CHARS,
    CONF_NUMBER_NORMALIZER_ENABLED,
    CONF_NUMBER_SPELLOUT_LANGUAGE,
    CONF_OUTPUT_LANGUAGE,
    CONF_PREVIEW_TEXT,
    CONF_REPLACEMENT_RULES,
    CONF_SAFETY_TAIL_CHARS,
    DEFAULT_MAX_BUFFER_CHARS,
    DEFAULT_NAME,
    DEFAULT_SAFETY_TAIL_CHARS,
    RULE_CASE_SENSITIVE,
    RULE_DISABLED,
    RULE_ENABLED,
    RULE_FIND,
    RULE_IGNORE_CASE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_NAME,
    RULE_REPLACE,
)
from .form_data import flatten_config_sections
from .markdown_normalizer import (
    MarkdownCleanupNormalizer,
    parse_markdown_cleanup_normalizer,
)
from .normalizer import (
    NumberNormalizer,
    ReplacementRule,
    parse_number_normalizer,
    parse_rules,
    validate_streaming_buffer_config,
)
from .date_normalizer import DateNormalizer, parse_date_normalizer

CONF_NAME = "name"


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Validated Proxy Configuration."""

    name: str
    target_tts_entity: str
    output_language: str
    rules: tuple[ReplacementRule, ...]
    markdown_normalizer: MarkdownCleanupNormalizer
    date_normalizer: DateNormalizer
    number_normalizer: NumberNormalizer
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
    raw_config = flatten_config_sections(raw_config)
    safety_tail_chars = int(
        raw_config.get(CONF_SAFETY_TAIL_CHARS, DEFAULT_SAFETY_TAIL_CHARS)
    )
    max_buffer_chars = int(
        raw_config.get(CONF_MAX_BUFFER_CHARS, DEFAULT_MAX_BUFFER_CHARS)
    )
    validate_streaming_buffer_config(safety_tail_chars, max_buffer_chars)

    target_tts_entity = _clean_string(raw_config.get(CONF_TARGET_TTS_ENTITY))
    output_language = _clean_string(raw_config.get(CONF_OUTPUT_LANGUAGE))
    if not target_tts_entity:
        raise ValueError("Target TTS Entity is required")
    if not output_language:
        raise ValueError("Output Language is required")

    name = _clean_string(raw_config.get(CONF_NAME)) or DEFAULT_NAME

    return ProxyConfig(
        name=name,
        target_tts_entity=target_tts_entity,
        output_language=output_language,
        rules=parse_rules(raw_config.get(CONF_REPLACEMENT_RULES, [])),
        markdown_normalizer=parse_markdown_cleanup_normalizer(raw_config),
        date_normalizer=parse_date_normalizer(raw_config),
        number_normalizer=parse_number_normalizer(raw_config),
        safety_tail_chars=safety_tail_chars,
        max_buffer_chars=max_buffer_chars,
    )


def serializable_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """Return normalized config data suitable for config-entry storage."""
    config = parse_proxy_config(raw_config)
    return {
        CONF_NAME: config.name,
        CONF_TARGET_TTS_ENTITY: config.target_tts_entity,
        CONF_OUTPUT_LANGUAGE: config.output_language,
        CONF_REPLACEMENT_RULES: serializable_replacement_rules(config.rules),
        CONF_MARKDOWN_CLEANUP_ENABLED: config.markdown_normalizer.enabled,
        CONF_MARKDOWN_STRIP_EMPHASIS: config.markdown_normalizer.strip_emphasis,
        CONF_MARKDOWN_STRIP_HEADINGS: config.markdown_normalizer.strip_headings,
        CONF_MARKDOWN_STRIP_LIST_MARKERS: (
            config.markdown_normalizer.strip_list_markers
        ),
        CONF_MARKDOWN_STRIP_TABLES: config.markdown_normalizer.strip_tables,
        CONF_MARKDOWN_STRIP_LINKS: config.markdown_normalizer.strip_links,
        CONF_MARKDOWN_REMOVE_PLAIN_URLS: (
            config.markdown_normalizer.remove_plain_urls
        ),
        CONF_MARKDOWN_STRIP_INLINE_CODE: (
            config.markdown_normalizer.strip_inline_code
        ),
        CONF_MARKDOWN_REMOVE_CODE_BLOCKS: (
            config.markdown_normalizer.remove_code_blocks
        ),
        CONF_MARKDOWN_STRIP_BLOCKQUOTES: (
            config.markdown_normalizer.strip_blockquotes
        ),
        CONF_MARKDOWN_REMOVE_DIVIDER_LINES: (
            config.markdown_normalizer.remove_divider_lines
        ),
        CONF_MARKDOWN_STRIP_STRIKETHROUGH: (
            config.markdown_normalizer.strip_strikethrough
        ),
        CONF_MARKDOWN_STRIP_IMAGES: config.markdown_normalizer.strip_images,
        CONF_DATE_NORMALIZER_ENABLED: config.date_normalizer.enabled,
        CONF_DATE_LOCALE: config.date_normalizer.locale,
        CONF_DATE_RENDERER: config.date_normalizer.renderer,
        CONF_DATE_INPUT_FORMATS: list(config.date_normalizer.input_formats),
        CONF_NUMBER_NORMALIZER_ENABLED: config.number_normalizer.enabled,
        CONF_NUMBER_SPELLOUT_LANGUAGE: config.number_normalizer.language,
        CONF_SAFETY_TAIL_CHARS: config.safety_tail_chars,
        CONF_MAX_BUFFER_CHARS: config.max_buffer_chars,
    }


def form_defaults(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    """Return config data safe to use as config-flow form defaults."""
    defaults = flatten_config_sections(raw_config)
    defaults.pop(CONF_PREVIEW_TEXT, None)
    if CONF_REPLACEMENT_RULES in defaults:
        defaults[CONF_REPLACEMENT_RULES] = [
            _form_rule_defaults(raw_rule)
            for raw_rule in defaults.get(CONF_REPLACEMENT_RULES, [])
            if isinstance(raw_rule, dict)
        ]
    return defaults


def serializable_replacement_rules(
    rules: tuple[ReplacementRule, ...],
) -> list[dict[str, Any]]:
    """Return Replacement Rules using only current UI field names."""
    return [
        {
            RULE_NAME: rule.name,
            RULE_DISABLED: not rule.enabled,
            RULE_MODE: rule.mode.value,
            RULE_FIND: rule.find,
            RULE_REPLACE: rule.replace,
            RULE_CASE_SENSITIVE: not rule.ignore_case,
        }
        for rule in rules
    ]


def _form_rule_defaults(raw_rule: dict[str, Any]) -> dict[str, Any]:
    """Return one rule using only current config-flow field names."""
    if RULE_DISABLED in raw_rule:
        disabled = bool(raw_rule.get(RULE_DISABLED))
    else:
        disabled = not bool(raw_rule.get(RULE_ENABLED, True))

    if RULE_CASE_SENSITIVE in raw_rule:
        case_sensitive = bool(raw_rule.get(RULE_CASE_SENSITIVE))
    else:
        case_sensitive = not bool(raw_rule.get(RULE_IGNORE_CASE, True))

    return {
        RULE_NAME: str(raw_rule.get(RULE_NAME, "") or "").strip(),
        RULE_DISABLED: disabled,
        RULE_MODE: str(raw_rule.get(RULE_MODE) or RULE_MODE_LITERAL),
        RULE_FIND: str(raw_rule.get(RULE_FIND, "")),
        RULE_REPLACE: str(raw_rule.get(RULE_REPLACE, "")),
        RULE_CASE_SENSITIVE: case_sensitive,
    }


def _clean_string(value: Any) -> str:
    """Return a stripped string, treating None as missing."""
    if value is None:
        return ""
    return str(value).strip()
