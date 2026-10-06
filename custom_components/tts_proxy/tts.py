"""TTS platform for the TTS Proxy integration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from homeassistant.components.tts import (
    TextToSpeechEntity,
    TTSAudioRequest,
    TTSAudioResponse,
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
from .const import DOMAIN, OPTION_PROCESSING_FINGERPRINT, OPTION_REQUEST_ID
from .emoji_normalizer import async_prepare_emoji_config, async_prepare_emoji_normalizer
from .normalizer import normalize_stream, normalize_text
from .rules import (
    EntityStateReport,
    TextProcessingRule,
    condition_snapshot,
    rules_from_snapshot,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TTS Proxy platform."""
    await async_prepare_emoji_config(hass, merged_entry_config(entry))
    async_add_entities([ProxyTextToSpeechEntity(entry)])


class ProxyTextToSpeechEntity(TextToSpeechEntity):
    """Proxy TTS Entity that processes text before synthesis."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        raw_config = merged_entry_config(entry)
        self._config = parse_proxy_config(raw_config)
        self._processing_fingerprint = hashlib.sha256(
            json.dumps(raw_config, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._has_conditioned_rules = any(
            rule.enabled and rule.condition is not None for rule in self._config.rules
        )
        self._attr_name = self._config.name
        self._attr_unique_id = entry.entry_id

    @property
    def available(self) -> bool:
        """Return if the proxy can reach its Target TTS Entity."""
        target_entity = self._target_tts_entity
        return target_entity is not None and target_entity.available

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
        """Return options supported by the Target TTS Entity."""
        target_entity = self._target_tts_entity
        if target_entity is None:
            return []
        return [
            option
            for option in target_entity.supported_options or []
            if option not in (OPTION_PROCESSING_FINGERPRINT, OPTION_REQUEST_ID)
        ]

    @property
    def default_options(self) -> dict[str, Any]:
        """Partition HA's cache without capturing conditions during preparation."""
        target_entity = self._target_tts_entity
        options = self._delegate_options(target_entity, {}) if target_entity else {}
        options[OPTION_PROCESSING_FINGERPRINT] = self._processing_fingerprint
        if self._has_conditioned_rules:
            # Assist reads defaults before speech recognition. Conditions are only
            # known once response text arrives, after HA's one-shot cache lookup.
            options[OPTION_REQUEST_ID] = uuid4().hex
        return options

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return voices supported by the Target TTS Entity."""
        target_entity = self._target_tts_entity
        if target_entity is None:
            return None
        return target_entity.async_get_supported_voices(self._config.output_language)

    def async_supports_streaming_input(self) -> bool:
        """Return if the Target TTS Entity supports streaming input."""
        target_entity = self._target_tts_entity
        return bool(target_entity and target_entity.async_supports_streaming_input())

    async def async_added_to_hass(self) -> None:
        """Track Target TTS Entity availability changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._config.target_tts_entity],
                self._async_target_entity_state_changed,
            )
        )

    @callback
    def _async_target_entity_state_changed(self, event: Event) -> None:
        """Update state when Target TTS Entity availability changes."""
        self.async_write_ha_state()

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Generate one-shot speech through the Target TTS Entity."""
        target_entity = self._require_target_tts_entity()
        rules = self._capture_rules(options)
        return await self._async_synthesize(target_entity, message, options, rules)

    async def _async_synthesize(
        self,
        target_entity: TextToSpeechEntity,
        message: str,
        options: dict[str, Any],
        rules: tuple[TextProcessingRule, ...],
    ) -> TtsAudioType:
        """Synthesize text using the rules already captured for this request."""
        await async_prepare_emoji_normalizer(self.hass, self._config.emoji_normalizer)
        normalized = normalize_text(
            message,
            rules,
            markdown_normalizer=self._config.markdown_normalizer,
            text_cleanup_normalizer=self._config.text_cleanup_normalizer,
            emoji_normalizer=self._config.emoji_normalizer,
            time_normalizer=self._config.time_normalizer,
            unit_normalizer=self._config.unit_normalizer,
            number_normalizer=self._config.number_normalizer,
            date_normalizer=self._config.date_normalizer,
        )
        return await target_entity.async_internal_get_tts_audio(
            normalized,
            self._config.output_language,
            self._delegate_options(target_entity, options),
        )

    async def async_stream_tts_audio(
        self,
        request: TTSAudioRequest,
    ) -> TTSAudioResponse:
        """Generate streaming speech through the Target TTS Entity when possible."""
        target_entity = self._require_target_tts_entity()
        options = self._delegate_options(target_entity, request.options)

        # Opening a stream can precede the sensor update. Wait for actual text,
        # then freeze conditions before normalization, async preparation, or
        # reading more chunks, including when the target needs a complete message.
        first_chunk = ""
        async for chunk in request.message_gen:
            if chunk:
                first_chunk = chunk
                break
        rules = self._capture_rules(request.options) if first_chunk else ()

        async def message_gen() -> AsyncGenerator[str]:
            if first_chunk:
                yield first_chunk
            async for chunk in request.message_gen:
                yield chunk

        if not target_entity.async_supports_streaming_input():
            message = "".join([chunk async for chunk in message_gen()])
            extension, data = await self._async_synthesize(
                target_entity,
                message,
                options,
                rules,
            )
            if extension is None or data is None:
                raise HomeAssistantError(
                    f"No TTS from {self._config.target_tts_entity} for processed message"
                )

            async def data_gen() -> AsyncGenerator[bytes]:
                yield data

            return TTSAudioResponse(extension, data_gen())

        await async_prepare_emoji_normalizer(self.hass, self._config.emoji_normalizer)
        normalized_stream = normalize_stream(
            message_gen(),
            rules,
            markdown_normalizer=self._config.markdown_normalizer,
            text_cleanup_normalizer=self._config.text_cleanup_normalizer,
            emoji_normalizer=self._config.emoji_normalizer,
            time_normalizer=self._config.time_normalizer,
            unit_normalizer=self._config.unit_normalizer,
            number_normalizer=self._config.number_normalizer,
            date_normalizer=self._config.date_normalizer,
            safety_tail_chars=self._config.safety_tail_chars,
            max_buffer_chars=self._config.max_buffer_chars,
        )
        return await target_entity.internal_async_stream_tts_audio(
            TTSAudioRequest(
                self._config.output_language,
                options,
                normalized_stream,
            )
        )

    def _entity_state(self, entity_id: str) -> EntityStateReport | None:
        """Copy the state and report time when a request snapshot is created."""
        state = self.hass.states.get(entity_id)
        return (
            EntityStateReport(state.state, state.last_reported)
            if state is not None
            else None
        )

    def _capture_rules(self, options: dict[str, Any]) -> tuple[TextProcessingRule, ...]:
        """Snapshot current conditions once response text is available."""
        fingerprint = options.get(OPTION_PROCESSING_FINGERPRINT)
        if fingerprint is not None and fingerprint != self._processing_fingerprint:
            raise HomeAssistantError("Invalid or outdated TTS Proxy configuration")
        snapshot = condition_snapshot(self._config.rules, self._entity_state)
        return rules_from_snapshot(self._config.rules, snapshot)

    @property
    def _target_tts_entity(self) -> TextToSpeechEntity | None:
        """Return the configured Target TTS Entity if it is valid."""
        if not hasattr(self, "hass"):
            return None
        engine = get_engine_instance(self.hass, self._config.target_tts_entity)
        if not isinstance(engine, TextToSpeechEntity):
            return None
        platform = getattr(engine, "platform", None)
        if getattr(platform, "domain", None) == DOMAIN:
            return None
        if engine.entity_id == self.entity_id:
            return None
        return engine

    def _require_target_tts_entity(self) -> TextToSpeechEntity:
        """Return the Target TTS Entity or raise a clear runtime error."""
        target_entity = self._target_tts_entity
        if target_entity is None or not target_entity.available:
            raise HomeAssistantError(
                f"Target TTS Entity {self._config.target_tts_entity} is unavailable"
            )
        return target_entity

    @staticmethod
    def _delegate_options(
        target_entity: TextToSpeechEntity,
        options: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Merge Target TTS Entity defaults with call options."""
        delegated = {
            **dict(target_entity.default_options or {}),
            **dict(options or {}),
        }
        delegated.pop(OPTION_PROCESSING_FINGERPRINT, None)
        delegated.pop(OPTION_REQUEST_ID, None)
        return delegated
