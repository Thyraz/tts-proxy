"""Constants for the TTS Proxy integration."""

from __future__ import annotations

DOMAIN = "tts_proxy"
PLATFORMS = ["tts"]

DEFAULT_NAME = "TTS Proxy"
DEFAULT_SAFETY_TAIL_CHARS = 64
DEFAULT_MAX_BUFFER_CHARS = 500

CONF_DATE_INPUT_FORMATS = "date_input_formats"
CONF_DATE_LOCALE = "date_locale"
CONF_DATE_NORMALIZER_ENABLED = "date_normalizer_enabled"
CONF_DATE_RENDERER = "date_renderer"
CONF_FINAL_TTS_ENTITY = "final_tts_entity"
CONF_OUTPUT_LANGUAGE = "output_language"
CONF_REPLACEMENT_RULES = "replacement_rules"
CONF_NUMBER_NORMALIZER_ENABLED = "number_normalizer_enabled"
CONF_NUMBER_SPELLOUT_LANGUAGE = "number_spellout_language"
CONF_PREVIEW_TEXT = "preview_text"
CONF_SAFETY_TAIL_CHARS = "safety_tail_chars"
CONF_MAX_BUFFER_CHARS = "max_buffer_chars"

PREVIEW_NAME = "tts_proxy"
MAX_PREVIEW_TEXT_CHARS = 2000

RULE_ENABLED = "enabled"
RULE_DISABLED = "disabled"
RULE_MODE = "mode"
RULE_FIND = "find"
RULE_REPLACE = "replace"
RULE_IGNORE_CASE = "ignore_case"
RULE_CASE_SENSITIVE = "case_sensitive"

DATE_INPUT_FORMAT_DMY_DOT = "dmy_dot"
DATE_INPUT_FORMAT_DMY_DOT_NO_YEAR = "dmy_dot_no_year"
DATE_INPUT_FORMAT_DMY_MONTH_NAME = "dmy_month_name"
DATE_INPUT_FORMAT_DMY_SLASH = "dmy_slash"
DATE_INPUT_FORMAT_DMY_SLASH_NO_YEAR = "dmy_slash_no_year"
DATE_INPUT_FORMAT_MDY_MONTH_NAME = "mdy_month_name"
DATE_INPUT_FORMAT_MDY_SLASH = "mdy_slash"
DATE_INPUT_FORMAT_MDY_SLASH_NO_YEAR = "mdy_slash_no_year"
DATE_INPUT_FORMAT_YMD_DASH = "ymd_dash"

DATE_RENDERER_CURATED = "curated"
DATE_RENDERER_NUMERIC_FALLBACK = "numeric_fallback"

RULE_MODE_LITERAL = "literal"
RULE_MODE_REGEX = "regex"
