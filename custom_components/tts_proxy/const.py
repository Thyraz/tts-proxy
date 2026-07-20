"""Constants for the TTS Proxy integration."""

from __future__ import annotations

DOMAIN = "tts_proxy"
PLATFORMS = ["tts"]

DEFAULT_NAME = "TTS Proxy"
DEFAULT_SAFETY_TAIL_CHARS = 64
DEFAULT_MAX_BUFFER_CHARS = 500

CONF_FINAL_TTS_ENTITY = "final_tts_entity"
CONF_OUTPUT_LANGUAGE = "output_language"
CONF_REPLACEMENT_RULES = "replacement_rules"
CONF_SAFETY_TAIL_CHARS = "safety_tail_chars"
CONF_MAX_BUFFER_CHARS = "max_buffer_chars"

RULE_ENABLED = "enabled"
RULE_DISABLED = "disabled"
RULE_MODE = "mode"
RULE_FIND = "find"
RULE_REPLACE = "replace"
RULE_IGNORE_CASE = "ignore_case"
RULE_CASE_SENSITIVE = "case_sensitive"

RULE_MODE_LITERAL = "literal"
RULE_MODE_REGEX = "regex"
