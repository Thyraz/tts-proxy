"""General text cleanup for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

from .const import CONF_TEXT_CLEANUP_REPLACE_LINE_BREAKS

_LINE_BREAK_RE = re.compile(r"[ \t]*(?:\r\n|\r|\n)+[ \t]*")


@dataclass(frozen=True, slots=True)
class TextCleanupNormalizer:
    """A configured Text Cleanup Normalizer."""

    replace_line_breaks: bool = False

    def normalize(self, text: str) -> str:
        """Apply configured text cleanup rules."""
        if not text:
            return text
        if self.replace_line_breaks:
            text = _LINE_BREAK_RE.sub(" ", text)
        return text


def parse_text_cleanup_normalizer(
    raw_config: Mapping[str, Any],
) -> TextCleanupNormalizer:
    """Parse Text Cleanup Normalizer configuration."""
    return TextCleanupNormalizer(
        replace_line_breaks=bool(
            raw_config.get(CONF_TEXT_CLEANUP_REPLACE_LINE_BREAKS, False)
        )
    )
