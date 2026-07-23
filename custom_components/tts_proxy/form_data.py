"""Helpers for Home Assistant form data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import (
    SECTION_DATES,
    SECTION_EMOJI,
    SECTION_GENERAL,
    SECTION_MARKDOWN,
    SECTION_NUMBERS,
    SECTION_REPLACEMENTS,
    SECTION_STREAMING,
)

_SECTION_KEYS = (
    SECTION_GENERAL,
    SECTION_REPLACEMENTS,
    SECTION_MARKDOWN,
    SECTION_EMOJI,
    SECTION_DATES,
    SECTION_NUMBERS,
    SECTION_STREAMING,
)


def flatten_config_sections(raw_config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return config data with Home Assistant form sections flattened."""
    flattened = dict(raw_config or {})
    for section_key in _SECTION_KEYS:
        section_value = flattened.pop(section_key, None)
        if isinstance(section_value, Mapping):
            flattened.update(section_value)
    return flattened
