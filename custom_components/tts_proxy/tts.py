"""TTS platform for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from homeassistant.components.tts import (
    TTSAudioRequest,
    TTSAudioResponse,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .config import merged_entry_config, parse_proxy_config
from .const import DOMAIN
from .normalizer import normalize_stream, normalize_text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TTS Proxy platform."""
    async_add_entities([ProxyTextToSpeechEntity(entry)])


class ProxyTextToSpeechEntity(TextToSpeechEntity):
    """Proxy TTS Entity that normalizes text before final synthesis."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._config = parse_proxy_config(merged_entry_config(entry))
        self._attr_name = self._config.name
        self._attr_unique_id = entry.entry_id

    @property
    def available(self) -> bool:
        """Return if the proxy can reach its Final TTS Entity."""
        final_entity = self._final_tts_entity
        return final_entity is not None and final_entity.available

    @property
    def supported_languages(self) -> list[str]:
        """Return the single Output Language."""
        return [self._config.output_language]

    @property
    def default_language(self) -> str:
        """Return the Output Language."""
        return self._config.output_language

    @property
    def supported_options(self) -> list[str] | None:
        """Return options supported by the Final TTS Entity."""
        final_entity = self._final_tts_entity
        if final_entity is None:
            return []
        return list(final_entity.supported_options or [])

    @property
    def default_options(self) -> dict[str, Any]:
        """Return default options from the Final TTS Entity."""
        final_entity = self._final_tts_entity
        if final_entity is None:
            return {}
        return dict(final_entity.default_options or {})

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return voices supported by the Final TTS Entity."""
        final_entity = self._final_tts_entity
        if final_entity is None:
            return None
        return final_entity.async_get_supported_voices(self._config.output_language)

    def async_supports_streaming_input(self) -> bool:
        """Return if the Final TTS Entity supports streaming input."""
        final_entity = self._final_tts_entity
        return bool(final_entity and final_entity.async_supports_streaming_input())

    async def async_added_to_hass(self) -> None:
        """Track Final TTS Entity availability changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._config.final_tts_entity],
                self._async_final_entity_state_changed,
            )
        )

    @callback
    def _async_final_entity_state_changed(self, event: Event) -> None:
        """Update state when Final TTS Entity availability changes."""
        self.async_write_ha_state()

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Generate one-shot speech through the Final TTS Entity."""
        final_entity = self._require_final_tts_entity()
        normalized = normalize_text(
            message,
            self._config.rules,
            self._config.number_normalizer,
            self._config.date_normalizer,
        )
        return await final_entity.async_internal_get_tts_audio(
            normalized,
            self._config.output_language,
            self._delegate_options(final_entity, options),
        )

    async def async_stream_tts_audio(
        self,
        request: TTSAudioRequest,
    ) -> TTSAudioResponse:
        """Generate streaming speech through the Final TTS Entity when possible."""
        final_entity = self._require_final_tts_entity()
        options = self._delegate_options(final_entity, request.options)

        if not final_entity.async_supports_streaming_input():
            message = "".join([chunk async for chunk in request.message_gen])
            extension, data = await self.async_get_tts_audio(
                message,
                self._config.output_language,
                options,
            )
            if extension is None or data is None:
                raise HomeAssistantError(
                    f"No TTS from {self._config.final_tts_entity} for normalized message"
                )

            async def data_gen() -> AsyncGenerator[bytes]:
                yield data

            return TTSAudioResponse(extension, data_gen())

        normalized_stream = normalize_stream(
            request.message_gen,
            self._config.rules,
            self._config.number_normalizer,
            self._config.date_normalizer,
            safety_tail_chars=self._config.safety_tail_chars,
            max_buffer_chars=self._config.max_buffer_chars,
        )
        return await final_entity.internal_async_stream_tts_audio(
            TTSAudioRequest(
                self._config.output_language,
                options,
                normalized_stream,
            )
        )

    @property
    def _final_tts_entity(self) -> TextToSpeechEntity | None:
        """Return the configured Final TTS Entity if it is valid."""
        if not hasattr(self, "hass"):
            return None
        engine = get_engine_instance(self.hass, self._config.final_tts_entity)
        if not isinstance(engine, TextToSpeechEntity):
            return None
        platform = getattr(engine, "platform", None)
        if getattr(platform, "domain", None) == DOMAIN:
            return None
        if engine.entity_id == self.entity_id:
            return None
        return engine

    def _require_final_tts_entity(self) -> TextToSpeechEntity:
        """Return the Final TTS Entity or raise a clear runtime error."""
        final_entity = self._final_tts_entity
        if final_entity is None or not final_entity.available:
            raise HomeAssistantError(
                f"Final TTS Entity {self._config.final_tts_entity} is unavailable"
            )
        return final_entity

    @staticmethod
    def _delegate_options(
        final_entity: TextToSpeechEntity,
        options: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Merge Final TTS Entity defaults with call options."""
        return {
            **dict(final_entity.default_options or {}),
            **dict(options or {}),
        }
