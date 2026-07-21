"""Config flow for the TTS Proxy integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .config import form_defaults, merged_entry_config, serializable_config
from .const import (
    CONF_DATE_INPUT_FORMATS,
    CONF_DATE_LOCALE,
    CONF_DATE_NORMALIZER_ENABLED,
    CONF_DATE_RENDERER,
    CONF_FINAL_TTS_ENTITY,
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
    DOMAIN,
    MAX_PREVIEW_TEXT_CHARS,
    PREVIEW_NAME,
    RULE_DISABLED,
    RULE_FIND,
    RULE_CASE_SENSITIVE,
    RULE_MODE,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_REPLACE,
)
from .date_normalizer import (
    DateNormalizationError,
    default_date_input_formats,
    default_date_locale,
    default_date_renderer,
    supported_date_input_formats,
    supported_date_locales,
    supported_date_renderers,
)
from .normalizer import (
    NumberNormalizationError,
    RuleValidationError,
    normalize_text_from_raw_config,
    supported_number_spellout_languages,
)
from .preview import preview_event_payload


class TtsProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TTS Proxy."""

    VERSION = 1
    _partial_config: dict[str, Any]

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up the Normalization Preview websocket API."""
        websocket_api.async_register_command(hass, ws_start_preview)

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
            preview=PREVIEW_NAME,
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

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up the Normalization Preview websocket API."""
        websocket_api.async_register_command(hass, ws_start_preview)

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
            preview=PREVIEW_NAME,
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
    defaults = form_defaults(defaults)
    languages = _supported_languages(hass, final_tts_entity)
    language_default = defaults.get(CONF_OUTPUT_LANGUAGE)
    if language_default not in languages:
        language_default = languages[0] if languages else ""

    number_languages = list(supported_number_spellout_languages())
    number_language_default = _default_number_spellout_language(
        defaults,
        language_default,
        number_languages,
    )
    date_locales = list(supported_date_locales())
    date_locale_default = _default_date_locale(
        defaults,
        language_default,
        number_language_default,
        date_locales,
    )
    date_renderer_default = defaults.get(
        CONF_DATE_RENDERER,
        default_date_renderer(date_locale_default),
    )
    date_input_formats_default = defaults.get(
        CONF_DATE_INPUT_FORMATS,
        list(default_date_input_formats(date_locale_default)),
    )

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
                CONF_DATE_NORMALIZER_ENABLED,
                default=defaults.get(CONF_DATE_NORMALIZER_ENABLED, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_DATE_LOCALE,
                default=date_locale_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=date_locales,
                    mode="dropdown",
                    sort=True,
                )
            ),
            vol.Optional(
                CONF_DATE_RENDERER,
                default=date_renderer_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_date_renderer_options(),
                    mode="dropdown",
                )
            ),
            vol.Optional(
                CONF_DATE_INPUT_FORMATS,
                default=date_input_formats_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_date_input_format_options(),
                    multiple=True,
                    mode="list",
                )
            ),
            vol.Optional(
                CONF_NUMBER_NORMALIZER_ENABLED,
                default=defaults.get(CONF_NUMBER_NORMALIZER_ENABLED, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NUMBER_SPELLOUT_LANGUAGE,
                default=number_language_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=number_languages,
                    mode="dropdown",
                    sort=True,
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
            vol.Optional(
                CONF_PREVIEW_TEXT,
                default=defaults.get(CONF_PREVIEW_TEXT, ""),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
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


def _date_input_format_options() -> list[dict[str, str]]:
    """Return Date Input Format selector options."""
    labels = {
        "ymd_dash": "YYYY-MM-DD",
        "dmy_dot": "DD.MM.YYYY",
        "dmy_dot_no_year": "DD.MM.",
        "dmy_month_name": "DD Month Name",
        "dmy_slash": "DD/MM/YYYY",
        "dmy_slash_no_year": "DD/MM",
        "mdy_month_name": "Month Name DD",
        "mdy_slash": "MM/DD/YYYY",
        "mdy_slash_no_year": "MM/DD",
    }
    return [
        {"value": value, "label": labels[value]}
        for value in supported_date_input_formats()
    ]


def _date_renderer_options() -> list[dict[str, str]]:
    """Return Date Renderer selector options."""
    labels = {
        "curated": "Curated German/English",
        "numeric_fallback": "Numeric fallback",
    }
    return [
        {"value": value, "label": labels[value]}
        for value in supported_date_renderers()
    ]


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
    except DateNormalizationError:
        errors[CONF_DATE_LOCALE] = "invalid_date_normalizer"
        return errors
    except NumberNormalizationError:
        errors[CONF_NUMBER_SPELLOUT_LANGUAGE] = "invalid_number_normalizer"
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


def _default_number_spellout_language(
    defaults: dict[str, Any],
    output_language: str,
    number_languages: list[str],
) -> str:
    """Return the best default Number Spellout Language."""
    configured = defaults.get(CONF_NUMBER_SPELLOUT_LANGUAGE)
    if configured in number_languages:
        return configured

    normalized_output = str(output_language or "").replace("-", "_")
    for candidate in (normalized_output, normalized_output[:2]):
        if candidate in number_languages:
            return candidate

    return number_languages[0] if number_languages else ""


def _default_date_locale(
    defaults: dict[str, Any],
    output_language: str,
    number_language: str,
    date_locales: list[str],
) -> str:
    """Return a Date Locale default present in selector options."""
    candidates = (
        defaults.get(CONF_DATE_LOCALE),
        default_date_locale(output_language, number_language),
        default_date_locale("", number_language),
    )
    for candidate in candidates:
        if candidate in date_locales:
            return candidate
    return date_locales[0] if date_locales else ""


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


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{PREVIEW_NAME}/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@callback
def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a Normalization Preview for current form values."""
    user_input = dict(msg["user_input"])
    preview_text = str(user_input.get(CONF_PREVIEW_TEXT, "") or "")
    if len(preview_text) > MAX_PREVIEW_TEXT_CHARS:
        _send_preview_input_error(
            connection,
            msg,
            {
                CONF_PREVIEW_TEXT: (
                    f"Preview input must be {MAX_PREVIEW_TEXT_CHARS} characters or less"
                )
            },
        )
        return

    try:
        normalized = normalize_text_from_raw_config(preview_text, user_input)
    except (
        DateNormalizationError,
        NumberNormalizationError,
        RuleValidationError,
        ValueError,
    ) as err:
        _send_preview_input_error(connection, msg, {"base": str(err)})
        return

    connection.send_result(msg["id"])
    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            preview_event_payload(preview_text, normalized),
        )
    )
    connection.subscriptions[msg["id"]] = lambda: None


@callback
def _send_preview_input_error(
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Send preview validation errors."""
    connection.send_message(
        {
            "id": msg["id"],
            "type": websocket_api.TYPE_RESULT,
            "success": False,
            "error": {
                "code": "invalid_user_input",
                "message": errors,
            },
        }
    )
