"""Config flow for the TTS Proxy integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .config import merged_entry_config, serializable_config
from .const import (
    CONF_FINAL_TTS_ENTITY,
    CONF_MAX_BUFFER_CHARS,
    CONF_OUTPUT_LANGUAGE,
    CONF_REPLACEMENT_RULES,
    CONF_SAFETY_TAIL_CHARS,
    DEFAULT_MAX_BUFFER_CHARS,
    DEFAULT_NAME,
    DEFAULT_SAFETY_TAIL_CHARS,
    DOMAIN,
    RULE_DISABLED,
    RULE_FIND,
    RULE_CASE_SENSITIVE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_REPLACE,
)
from .normalizer import RuleValidationError


class TtsProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TTS Proxy."""

    VERSION = 1
    _partial_config: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_final_tts_entity(self.hass, user_input)
            if not errors:
                self._partial_config = dict(user_input)
                return await self.async_step_details()

        return self.async_show_form(
            step_id="user",
            data_schema=_final_entity_schema(user_input),
            errors=errors,
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect Output Language and rule details."""
        errors: dict[str, str] = {}
        partial_config = getattr(self, "_partial_config", {})

        if user_input is not None:
            data = {**partial_config, **user_input}
            errors = _validate_details(self.hass, data)
            if not errors:
                stored_data = serializable_config(data)
                return self.async_create_entry(
                    title=stored_data[CONF_NAME],
                    data=stored_data,
                )

        return self.async_show_form(
            step_id="details",
            data_schema=_details_schema(
                self.hass,
                partial_config[CONF_FINAL_TTS_ENTITY],
                user_input,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TtsProxyOptionsFlow:
        """Create the options flow."""
        return TtsProxyOptionsFlow(config_entry)


class TtsProxyOptionsFlow(config_entries.OptionsFlow):
    """Handle TTS Proxy options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = entry
        self._partial_config: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage display name and Final TTS Entity options."""
        current = merged_entry_config(self._entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_final_tts_entity(self.hass, user_input)
            if not errors:
                self._partial_config = {
                    **current,
                    **user_input,
                }
                return await self.async_step_details()

        return self.async_show_form(
            step_id="init",
            data_schema=_final_entity_schema(
                current if user_input is None else user_input
            ),
            errors=errors,
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage Output Language, rules, and buffer options."""
        partial_config = self._partial_config or merged_entry_config(self._entry)
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**partial_config, **user_input}
            errors = _validate_details(self.hass, data)
            if not errors:
                options = serializable_config(data)
                return self.async_create_entry(title=options[CONF_NAME], data=options)

        return self.async_show_form(
            step_id="details",
            data_schema=_details_schema(
                self.hass,
                partial_config[CONF_FINAL_TTS_ENTITY],
                partial_config if user_input is None else user_input,
            ),
            errors=errors,
        )


def _final_entity_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the display name and Final TTS Entity schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): selector.TextSelector(),
            vol.Required(
                CONF_FINAL_TTS_ENTITY,
                default=defaults.get(CONF_FINAL_TTS_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(filter={"domain": "tts"})
            ),
        }
    )


def _details_schema(
    hass: HomeAssistant,
    final_tts_entity: str,
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the Output Language, Replacement Rules, and buffer schema."""
    defaults = defaults or {}
    languages = _supported_languages(hass, final_tts_entity)
    language_default = defaults.get(CONF_OUTPUT_LANGUAGE)
    if language_default not in languages:
        language_default = languages[0] if languages else ""

    return vol.Schema(
        {
            vol.Required(
                CONF_OUTPUT_LANGUAGE,
                default=language_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=languages,
                    mode="dropdown",
                    sort=True,
                )
            ),
            vol.Optional(
                CONF_REPLACEMENT_RULES,
                default=defaults.get(CONF_REPLACEMENT_RULES, []),
            ): selector.ObjectSelector(
                selector.ObjectSelectorConfig(
                    multiple=True,
                    label_field=RULE_FIND,
                    fields={
                        RULE_DISABLED: {
                            "label": "Disabled",
                            "required": False,
                            "selector": selector.BooleanSelector(),
                        },
                        RULE_MODE: {
                            "label": "Mode (default: literal)",
                            "required": False,
                            "selector": selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=[RULE_MODE_LITERAL, RULE_MODE_REGEX]
                                )
                            ),
                        },
                        RULE_FIND: {
                            "label": "Find",
                            "required": True,
                            "selector": selector.TextSelector(),
                        },
                        RULE_REPLACE: {
                            "label": "Replace",
                            "required": False,
                            "selector": selector.TextSelector(),
                        },
                        RULE_CASE_SENSITIVE: {
                            "label": "Case sensitive",
                            "required": False,
                            "selector": selector.BooleanSelector(),
                        },
                    },
                )
            ),
            vol.Optional(
                CONF_SAFETY_TAIL_CHARS,
                default=defaults.get(
                    CONF_SAFETY_TAIL_CHARS, DEFAULT_SAFETY_TAIL_CHARS
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=1024, mode="box")
            ),
            vol.Optional(
                CONF_MAX_BUFFER_CHARS,
                default=defaults.get(CONF_MAX_BUFFER_CHARS, DEFAULT_MAX_BUFFER_CHARS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10000, mode="box")
            ),
        }
    )


def _validate_final_tts_entity(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> dict[str, str]:
    """Validate the selected Final TTS Entity."""
    errors: dict[str, str] = {}
    final_tts_entity = user_input.get(CONF_FINAL_TTS_ENTITY)
    if not final_tts_entity or _get_final_tts_entity(hass, final_tts_entity) is None:
        errors[CONF_FINAL_TTS_ENTITY] = "invalid_final_tts_entity"
    return errors


def _validate_details(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> dict[str, str]:
    """Validate Output Language, rules, and buffer settings."""
    errors: dict[str, str] = {}
    try:
        config = serializable_config(user_input)
    except RuleValidationError:
        errors[CONF_REPLACEMENT_RULES] = "invalid_rule"
        return errors
    except ValueError:
        errors["base"] = "invalid_buffer_config"
        return errors

    final_entity = _get_final_tts_entity(hass, config[CONF_FINAL_TTS_ENTITY])
    if final_entity is None:
        errors[CONF_FINAL_TTS_ENTITY] = "invalid_final_tts_entity"
        return errors

    if config[CONF_OUTPUT_LANGUAGE] not in final_entity.supported_languages:
        errors[CONF_OUTPUT_LANGUAGE] = "unsupported_output_language"

    return errors


def _supported_languages(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return supported languages for a valid Final TTS Entity."""
    final_entity = _get_final_tts_entity(hass, entity_id)
    if final_entity is None:
        return []
    return list(final_entity.supported_languages or [])


def _get_final_tts_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> TextToSpeechEntity | None:
    """Return a valid non-proxy Final TTS Entity."""
    entity = get_engine_instance(hass, entity_id)
    if not isinstance(entity, TextToSpeechEntity):
        return None

    platform = getattr(entity, "platform", None)
    if getattr(platform, "domain", None) == DOMAIN:
        return None

    return entity
