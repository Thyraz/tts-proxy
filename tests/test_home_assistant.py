"""Home Assistant TTS-manager and preview checks (optional runtime dependency)."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.tts_proxy.const import (
    CONF_OUTPUT_LANGUAGE,
    CONF_PREVIEW_TEXT,
    CONF_REPLACEMENT_RULES,
    CONF_TARGET_TTS_ENTITY,
    OPTION_PROCESSING_FINGERPRINT,
    OPTION_REQUEST_ID,
    RULE_CONDITION_ENTITY,
    RULE_CONDITION_MAX_AGE,
    RULE_CONDITION_STATE,
    RULE_DISABLED,
    RULE_FIND,
    RULE_MODE,
    RULE_MODE_INSERT,
    RULE_MODE_LITERAL,
    RULE_PLACEMENTS,
    RULE_REPLACE,
)

HAS_HA = importlib.util.find_spec("homeassistant") is not None
if HAS_HA:
    import homeassistant  # noqa: F401 - Initialize HA validation before voluptuous.
    import voluptuous as vol
    from homeassistant.components.tts import (
        SpeechManager,
        TextToSpeechEntity,
        TTSAudioRequest,
        TTSAudioResponse,
    )
    from homeassistant.components.tts.const import DATA_COMPONENT, DATA_TTS_MANAGER
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.tts_proxy.config_flow import (
        _replacement_rules_section_schema,
        ws_start_preview,
    )
    from custom_components.tts_proxy.tts import ProxyTextToSpeechEntity

    class EchoTarget(TextToSpeechEntity):
        """Use the actual HA entity wrappers, echoing processed text as audio bytes."""

        _attr_name = "Echo target"
        _attr_default_language = "en"

        def __init__(self, hass):
            self._attr_supported_languages = ["en"]
            self._attr_supported_options = ["voice"]
            self._attr_default_options = {"voice": "example"}
            self.hass = hass
            self.entity_id = "tts.target"
            self.calls = []
            self.streaming = False
            self.async_write_ha_state = lambda: None

        def async_supports_streaming_input(self):
            return self.streaming

        async def async_get_tts_audio(self, message, language, options):
            self.calls.append((message, language, options))
            return "wav", message.encode()

        async def async_stream_tts_audio(self, request):
            message = "".join([part async for part in request.message_gen])
            self.calls.append((message, request.language, request.options))

            async def data_gen():
                yield message.encode()

            return TTSAudioResponse("wav", data_gen())


@unittest.skipUnless(
    HAS_HA, "Install tests/requirements.txt for actual HA manager tests"
)
class HomeAssistantProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tts-proxy-tests-")
        self.hass = HomeAssistant(self.directory.name)
        self.target = EchoTarget(self.hass)
        self.rule = {
            RULE_MODE: RULE_MODE_INSERT,
            RULE_REPLACE: "[whisper] ",
            RULE_PLACEMENTS: ["sentence_start"],
            RULE_CONDITION_ENTITY: "binary_sensor.whisper",
            RULE_CONDITION_STATE: "on",
        }
        self.raw_config = {
            CONF_TARGET_TTS_ENTITY: "tts.target",
            CONF_OUTPUT_LANGUAGE: "en",
            CONF_REPLACEMENT_RULES: [self.rule],
        }
        self.proxy = self.make_proxy(self.raw_config)
        self.entities = {"tts.target": self.target, "tts.proxy": self.proxy}
        self.hass.data[DATA_COMPONENT] = SimpleNamespace(get_entity=self.entities.get)
        self.manager = SpeechManager(self.hass, False, self.directory.name, 60)
        self.hass.data[DATA_TTS_MANAGER] = self.manager
        self.hass.states.async_set("binary_sensor.whisper", "on")

    def make_proxy(self, raw_config):
        entry = SimpleNamespace(data=raw_config, options={}, entry_id="proxy-example")
        proxy = ProxyTextToSpeechEntity(entry)
        proxy.hass = self.hass
        proxy.entity_id = "tts.proxy"
        proxy.async_write_ha_state = lambda: None
        return proxy

    async def asyncTearDown(self):
        for cleaner in (
            self.manager.memcache_cleanup,
            self.manager.token_to_stream_cleanup,
        ):
            if cleaner.unsub:
                cleaner.unsub()
        await self.hass.async_stop(force=True)
        self.directory.cleanup()

    def request_stream(self, *, disk_cache=False):
        return self.manager.async_create_result_stream(
            "tts.proxy",
            use_file_cache=disk_cache,
            language="en",
            options={"preferred_format": "wav"},
        )

    async def audio(self, stream):
        await self.hass.async_block_till_done(wait_background_tasks=True)
        return b"".join([part async for part in stream.async_stream_result()])

    async def test_early_stream_preparation_uses_current_round_state(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                self.target.streaming = streaming
                self.hass.states.async_set("binary_sensor.whisper", "off")
                previous_calls = len(self.target.calls)
                replies = []
                for current_state in ("on", "off", "off"):
                    # Assist prepares TTS before the user finishes speaking.
                    stream = self.request_stream()
                    self.hass.states.async_set("binary_sensor.whisper", current_state)
                    if streaming:

                        async def chunks():
                            yield "Done."

                        stream.async_set_message_stream(chunks())
                    else:
                        stream.async_set_message("Done.")
                    replies.append(await self.audio(stream))
                self.assertEqual(replies, [b"[whisper] Done.", b"Done.", b"Done."])
                self.assertEqual(len(self.target.calls) - previous_calls, 3)
        for _, _, options in self.target.calls:
            self.assertEqual(options, {"voice": "example"})

    async def test_conditioned_requests_do_not_reuse_disk_audio(self):
        for state, expected in (
            ("on", b"[whisper] Done."),
            ("off", b"Done."),
            ("off", b"Done."),
        ):
            # Identical preparation state must not cause a stale cache hit.
            self.hass.states.async_set("binary_sensor.whisper", "off")
            stream = self.request_stream(disk_cache=True)
            self.hass.states.async_set("binary_sensor.whisper", state)
            stream.async_set_message("Done.")
            self.assertEqual(await self.audio(stream), expected)
            self.manager.mem_cache.clear()
        self.assertEqual(len(self.manager.file_cache), 3)
        self.assertEqual(len(self.target.calls), 3)

    async def test_actual_manager_streaming_freezes_state_on_first_text(self):
        self.target.streaming = True
        self.hass.states.async_set("binary_sensor.whisper", "off")
        stream = self.request_stream()

        async def chunks():
            yield ""
            self.hass.states.async_set("binary_sensor.whisper", "on")
            yield "First. "
            self.hass.states.async_set("binary_sensor.whisper", "off")
            yield "Next."

        stream.async_set_message_stream(chunks())
        self.assertEqual(await self.audio(stream), b"[whisper] First. [whisper] Next.")
        self.assertEqual(self.target.calls[-1][2], {"voice": "example"})

    async def test_complete_response_reads_state_after_stream_preparation(self):
        stream = self.request_stream()
        self.hass.states.async_set("binary_sensor.whisper", "off")
        stream.async_set_message("Done.")
        self.assertEqual(await self.audio(stream), b"Done.")

    async def test_expired_condition_skips_rule_but_a_fresh_report_activates_it(self):
        timed_rule = {**self.rule, RULE_CONDITION_MAX_AGE: 30}
        self.entities["tts.proxy"] = self.make_proxy(
            {**self.raw_config, CONF_REPLACEMENT_RULES: [timed_rule]}
        )
        state = self.hass.states.get("binary_sensor.whisper")
        state.last_reported = datetime.now(UTC) - timedelta(minutes=5)
        expired = self.request_stream(disk_cache=True)
        expired.async_set_message("Done.")
        self.assertEqual(await self.audio(expired), b"Done.")

        # Another identical report must count, even without a state change.
        last_changed = state.last_changed
        self.hass.states.async_set("binary_sensor.whisper", "on")
        self.assertEqual(
            self.hass.states.get(state.entity_id).last_changed, last_changed
        )
        fresh = self.request_stream(disk_cache=True)
        fresh.async_set_message("Done.")
        self.assertEqual(await self.audio(fresh), b"[whisper] Done.")
        self.assertEqual(len(self.target.calls), 2)

        # Leaving the limit unset preserves the existing matching behavior.
        self.entities["tts.proxy"] = self.proxy
        state.last_reported = datetime.now(UTC) - timedelta(minutes=5)
        unlimited = self.request_stream()
        unlimited.async_set_message("Done.")
        self.assertEqual(await self.audio(unlimited), b"[whisper] Done.")

    async def test_independent_speaker_rules_insert_only_for_fresh_matching_reports(
        self,
    ):
        kitchen = {**self.rule, RULE_CONDITION_MAX_AGE: 30}
        living_room = {
            **kitchen,
            RULE_CONDITION_ENTITY: "binary_sensor.living_room_whisper",
        }
        self.entities["tts.proxy"] = self.make_proxy(
            {**self.raw_config, CONF_REPLACEMENT_RULES: [kitchen, living_room]}
        )
        for kitchen_age, living_room_age, expected in (
            (300, 300, b"Done."),
            (1, 300, b"[whisper] Done."),
            (1, 1, b"[whisper] Done."),
        ):
            with self.subTest(kitchen=kitchen_age, living_room=living_room_age):
                for rule, age in (
                    (kitchen, kitchen_age),
                    (living_room, living_room_age),
                ):
                    entity_id = rule[RULE_CONDITION_ENTITY]
                    self.hass.states.async_set(entity_id, "on")
                    self.hass.states.get(entity_id).last_reported = datetime.now(
                        UTC
                    ) - timedelta(seconds=age)
                stream = self.request_stream()
                stream.async_set_message("Done.")
                self.assertEqual(await self.audio(stream), expected)

    async def test_age_is_frozen_at_first_text_for_streaming_and_fallback(self):
        self.proxy = self.make_proxy(
            {
                **self.raw_config,
                CONF_REPLACEMENT_RULES: [{**self.rule, RULE_CONDITION_MAX_AGE: 30}],
            }
        )
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                self.target.streaming = streaming
                self.hass.states.get("binary_sensor.whisper").last_reported = (
                    datetime.now(UTC) - timedelta(minutes=5)
                )

                async def chunks():
                    yield ""
                    self.hass.states.async_set("binary_sensor.whisper", "on")
                    yield "First. "
                    self.hass.states.get("binary_sensor.whisper").last_reported = (
                        datetime.now(UTC) - timedelta(minutes=5)
                    )
                    yield "Next."

                response = await self.proxy.async_stream_tts_audio(
                    TTSAudioRequest("en", {}, chunks())
                )
                data = b"".join([part async for part in response.data_gen])
                self.assertEqual(data, b"[whisper] First. [whisper] Next.")

    async def test_cache_changes_after_processing_configuration_changes(self):
        unconditional_rule = {
            key: value
            for key, value in self.rule.items()
            if key not in (RULE_CONDITION_ENTITY, RULE_CONDITION_STATE)
        }
        self.entities["tts.proxy"] = self.make_proxy(
            {**self.raw_config, CONF_REPLACEMENT_RULES: [unconditional_rule]}
        )
        first = self.request_stream()
        first.async_set_message("Done.")
        self.assertEqual(await self.audio(first), b"[whisper] Done.")
        repeated = self.request_stream()
        repeated.async_set_message("Done.")
        self.assertEqual(await self.audio(repeated), b"[whisper] Done.")
        self.assertEqual(len(self.target.calls), 1)
        new_rule = {**unconditional_rule, RULE_REPLACE: "[sleepy] "}
        self.entities["tts.proxy"] = self.make_proxy(
            {**self.raw_config, CONF_REPLACEMENT_RULES: [new_rule]}
        )
        second = self.request_stream()
        second.async_set_message("Done.")
        self.assertEqual(await self.audio(second), b"[sleepy] Done.")
        self.assertEqual(len(self.target.calls), 2)

    async def test_concurrent_requests_keep_independent_snapshots(self):
        self.target.streaming = True
        first_text_read = asyncio.Event()
        finish_first = asyncio.Event()

        async def first_chunks():
            yield "First. "
            # The proxy has captured its snapshot before requesting more input.
            first_text_read.set()
            await finish_first.wait()
            yield "Next."

        first = self.request_stream()
        first.async_set_message_stream(first_chunks())
        await asyncio.wait_for(first_text_read.wait(), timeout=1)
        self.hass.states.async_set("binary_sensor.whisper", "off")
        second = self.request_stream()

        async def second_chunks():
            yield "Done."

        second.async_set_message_stream(second_chunks())
        finish_first.set()
        self.assertEqual(await self.audio(first), b"[whisper] First. [whisper] Next.")
        self.assertEqual(await self.audio(second), b"Done.")

    async def test_streaming_and_fallback_keep_snapshot_while_input_changes_state(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                self.target.streaming = streaming
                self.hass.states.async_set("binary_sensor.whisper", "off")

                async def chunks():
                    yield ""
                    self.hass.states.async_set("binary_sensor.whisper", "on")
                    yield "First. "
                    self.hass.states.async_set("binary_sensor.whisper", "off")
                    yield "Next."

                # Also exercise direct callers which have no manager-injected option.
                response = await self.proxy.async_stream_tts_audio(
                    TTSAudioRequest("en", {}, chunks())
                )
                data = b"".join([part async for part in response.data_gen])
                self.assertEqual(data, b"[whisper] First. [whisper] Next.")
                self.assertEqual(self.target.calls[-1][2], {"voice": "example"})

    async def test_unconditional_rules_and_disabled_conditions_reuse_audio(self):
        for rule, expected in (
            (
                {
                    key: value
                    for key, value in self.rule.items()
                    if key not in (RULE_CONDITION_ENTITY, RULE_CONDITION_STATE)
                },
                b"[whisper] Done.",
            ),
            ({**self.rule, RULE_DISABLED: True}, b"Done."),
        ):
            with self.subTest(rule=rule):
                self.entities["tts.proxy"] = self.make_proxy(
                    {**self.raw_config, CONF_REPLACEMENT_RULES: [rule]}
                )
                previous_calls = len(self.target.calls)
                for state in ("on", "off", "off"):
                    self.hass.states.async_set("binary_sensor.whisper", state)
                    stream = self.request_stream(disk_cache=True)
                    stream.async_set_message("Done.")
                    self.assertEqual(await self.audio(stream), expected)
                    # Also exercise disk reuse after memory eviction.
                    self.manager.mem_cache.clear()
                self.assertEqual(len(self.target.calls) - previous_calls, 1)

    async def test_empty_stream_does_not_read_entity_states(self):
        self.target.streaming = True
        original_state_reader = self.proxy._entity_state
        self.proxy._entity_state = MagicMock(wraps=original_state_reader)
        stream = self.request_stream()

        async def chunks():
            yield ""

        stream.async_set_message_stream(chunks())
        self.assertEqual(await self.audio(stream), b"")
        self.proxy._entity_state.assert_not_called()

    async def test_open_stream_waits_for_text_before_reading_conditions(self):
        self.target.streaming = True
        self.hass.states.async_set("binary_sensor.whisper", "off")
        self.proxy._entity_state = MagicMock(wraps=self.proxy._entity_state)
        input_started = asyncio.Event()
        text_ready = asyncio.Event()
        stream = self.request_stream()

        async def chunks():
            input_started.set()
            yield ""
            await text_ready.wait()
            yield "First. "
            self.hass.states.async_set("binary_sensor.whisper", "off")
            yield "Next."

        stream.async_set_message_stream(chunks())
        await asyncio.wait_for(input_started.wait(), timeout=1)
        self.proxy._entity_state.assert_not_called()
        self.hass.states.async_set("binary_sensor.whisper", "on")
        text_ready.set()
        self.assertEqual(await self.audio(stream), b"[whisper] First. [whisper] Next.")
        self.proxy._entity_state.assert_called_once_with("binary_sensor.whisper")

    async def test_cancelling_before_first_text_does_not_capture_conditions(self):
        self.target.streaming = True
        self.proxy._entity_state = MagicMock(wraps=self.proxy._entity_state)
        input_started = asyncio.Event()
        source_closed = asyncio.Event()

        async def chunks():
            try:
                input_started.set()
                await asyncio.Event().wait()
                yield "Never emitted."
            finally:
                source_closed.set()

        task = asyncio.create_task(
            self.proxy.async_stream_tts_audio(TTSAudioRequest("en", {}, chunks()))
        )
        await asyncio.wait_for(input_started.wait(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(source_closed.is_set())
        self.proxy._entity_state.assert_not_called()
        self.assertEqual(self.target.calls, [])

    async def test_private_option_cannot_be_overridden_as_a_call_option(self):
        for key in (OPTION_PROCESSING_FINGERPRINT, OPTION_REQUEST_ID):
            with self.subTest(key=key), self.assertRaises(HomeAssistantError):
                self.manager.async_create_result_stream(
                    "tts.proxy", options={key: "spoof"}
                )
        with self.assertRaises(HomeAssistantError):
            await self.proxy.async_get_tts_audio(
                "Hello.", "en", {OPTION_PROCESSING_FINGERPRINT: "stale"}
            )

    async def test_actual_preview_uses_unsaved_values_and_live_entity_states(self):
        connection = MagicMock()
        connection.subscriptions = {}
        unsaved = {
            CONF_PREVIEW_TEXT: "Hello.",
            CONF_REPLACEMENT_RULES: [{**self.rule, RULE_REPLACE: "[sleepy] "}],
        }
        for state, expected in (("on", "[sleepy] Hello."), ("off", "Hello.")):
            self.hass.states.async_set("binary_sensor.whisper", state)
            await ws_start_preview.__wrapped__(
                self.hass, connection, {"id": 1, "user_input": unsaved}
            )
            self.assertEqual(
                connection.send_message.call_args.args[0]["event"]["state"], expected
            )
        self.assertEqual(self.target.calls, [])
        self.assertEqual(self.rule[RULE_REPLACE], "[whisper] ")

    async def test_preview_checks_unsaved_age_limit_against_report_time(self):
        connection = MagicMock()
        connection.subscriptions = {}
        unsaved = {
            CONF_PREVIEW_TEXT: "Hello.",
            CONF_REPLACEMENT_RULES: [{**self.rule, RULE_CONDITION_MAX_AGE: 30}],
        }
        for age, expected in ((1, "[whisper] Hello."), (300, "Hello.")):
            self.hass.states.get("binary_sensor.whisper").last_reported = datetime.now(
                UTC
            ) - timedelta(seconds=age)
            await ws_start_preview.__wrapped__(
                self.hass, connection, {"id": 1, "user_input": unsaved}
            )
            self.assertEqual(
                connection.send_message.call_args.args[0]["event"]["state"], expected
            )
        self.assertEqual(self.target.calls, [])
        self.assertNotIn(RULE_CONDITION_MAX_AGE, self.rule)

    async def test_rule_selector_accepts_insertion_and_existing_rule_forms(self):
        section = _replacement_rules_section_schema({})
        value = {
            CONF_REPLACEMENT_RULES: [
                {**self.rule, RULE_CONDITION_MAX_AGE: 30},
                {RULE_MODE: RULE_MODE_LITERAL, RULE_FIND: "Hello", RULE_REPLACE: "Bye"},
            ]
        }
        self.assertEqual(section(value), value)
        with self.assertRaises(vol.Invalid):
            section(
                {CONF_REPLACEMENT_RULES: [{**self.rule, RULE_PLACEMENTS: ["invalid"]}]}
            )
        with self.assertRaises(vol.Invalid):
            section(
                {CONF_REPLACEMENT_RULES: [{**self.rule, RULE_CONDITION_MAX_AGE: 0}]}
            )
