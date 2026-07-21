"""Preview payload helpers for the TTS Proxy integration."""

from __future__ import annotations

from typing import Any


def preview_event_payload(preview_text: str, normalized_text: str) -> dict[str, Any]:
    """Return a successful generic Home Assistant preview event payload."""
    return {
        "attributes": {
            "friendly_name": "Normalized text",
            "input": preview_text,
        },
        "domain": "sensor",
        "listeners": {},
        "state": normalized_text,
    }
