# Home Assistant TTS Proxy Research

Research date: 2026-07-20

Question: can a Home Assistant custom integration expose a selectable text-to-speech entity that preprocesses text, then delegates synthesis to another TTS entity, including Assist/LLM streaming use cases?

## Short Answer

Yes, the shape is viable as a real `TextToSpeechEntity` exposed by a custom integration. Home Assistant already treats TTS entity IDs as selectable TTS engines, accepts both full-message and streaming-message TTS paths, and routes Assist pipeline TTS through the same TTS `ResultStream` machinery.

The main design risk is streaming preprocessing. Home Assistant does not guarantee that streamed LLM text chunks end on word, token, replacement, or sentence boundaries. A proxy must implement its own bounded text buffering before applying replacements.

## Primary Sources Checked

- Home Assistant developer docs: [Text-to-speech entity](https://developers.home-assistant.io/docs/core/entity/tts/), last updated 2026-07-09.
- Home Assistant developer docs: [Assist pipelines](https://developers.home-assistant.io/docs/voice/pipelines/), last updated 2026-06-15.
- Home Assistant developer docs: [Integration file structure](https://developers.home-assistant.io/docs/creating_integration_file_structure/), last updated 2026-06-15.
- Home Assistant developer docs: [YAML configuration](https://developers.home-assistant.io/docs/core/integration/yaml_configuration/), last updated 2026-06-16.
- Home Assistant user docs: [Text-to-speech building block](https://www.home-assistant.io/integrations/tts), site version 2026.7.2.
- Home Assistant core source, dev branch:
  - [`homeassistant/components/tts/entity.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/entity.py)
  - [`homeassistant/components/tts/__init__.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/__init__.py)
  - [`homeassistant/components/tts/media_source.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/media_source.py)
  - [`homeassistant/components/tts/helper.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/helper.py)
  - [`homeassistant/components/assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py)
  - [`homeassistant/components/assist_pipeline/websocket_api.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/websocket_api.py)
  - Example TTS providers: [`cloud/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/cloud/tts.py), [`elevenlabs/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/elevenlabs/tts.py), [`wyoming/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/wyoming/tts.py), [`google_translate/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/google_translate/tts.py), [`openai_conversation/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/openai_conversation/tts.py), [`google_generative_ai_conversation/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/google_generative_ai_conversation/tts.py).

## Facts From Home Assistant

### TTS entities are the right extension point

The developer docs define a TTS entity as a class derived from `homeassistant.components.tts.TextToSpeechEntity`; it must expose supported languages/default language and must implement one-shot TTS generation via `get_tts_audio` or `async_get_tts_audio`. Streaming input is optional via `async_stream_tts_audio` ([developer docs](https://developers.home-assistant.io/docs/core/entity/tts/)).

In core, `TextToSpeechEntity.async_speak` calls `media_player.play_media` with a TTS media source ID generated from the entity's own `entity_id` as the engine ([`tts/entity.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/entity.py#L133-L160)).

The TTS manager resolves engines from either a TTS entity registered in the entity component or a legacy provider ([`tts/helper.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/helper.py#L14-L20)). The media source root also lists registered TTS entities as browseable providers ([`tts/media_source.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/media_source.py#L168-L180)).

Implication: a proxy integration should expose `custom_components/<domain>/tts.py` with a `TextToSpeechEntity`. If the entity is present in HA, the Assist pipeline and `tts.speak` can select it like other TTS entities.

### Custom integration packaging is compatible

The integration file-structure docs say a custom integration lives under `<config directory>/custom_components/<domain>` and can provide platform files such as `light.py`, `switch.py`, and by extension `tts.py` for an entity platform ([file structure docs](https://developers.home-assistant.io/docs/creating_integration_file_structure/)).

The YAML configuration docs say the old platform-key style under entity domains is legacy and must not be used by new integrations; new integrations should use their own domain/config flow and load platforms from that integration ([YAML docs](https://developers.home-assistant.io/docs/core/integration/yaml_configuration/)).

Implication: configure the proxy with a config flow/options flow, not `tts: - platform: ...`.

### One-shot TTS path

The TTS domain registers `tts.speak` as an entity service and maps it to `TextToSpeechEntity.async_speak` ([`tts/__init__.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/__init__.py#L435-L445)).

For one-shot media source resolution, HA creates a `ResultStream`, calls `async_set_message(message)`, and the manager hashes the final message/language/options/engine for the memory and disk cache ([`tts/media_source.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/media_source.py#L133-L156), [`tts/__init__.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/__init__.py#L923-L978)).

If an engine does not support streaming input, the manager joins any incoming message generator into a complete string and calls `async_internal_get_tts_audio` ([`tts/__init__.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/__init__.py#L1084-L1105)).

Implication: a proxy can implement non-streaming by applying replacements to the complete message, then calling the delegate entity's one-shot method. If called with a streaming generator but the delegate lacks streaming support, HA's own fallback pattern is to join the stream first.

### Streaming TTS path

The TTS docs define `TTSAudioRequest` with `language`, `options`, and `message_gen`, and `TTSAudioResponse` with `extension` and `data_gen` ([developer docs](https://developers.home-assistant.io/docs/core/entity/tts/)). The implementation matches this in `tts/entity.py` ([source](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/entity.py#L36-L50)).

`TextToSpeechEntity.async_supports_streaming_input()` returns true when a concrete entity overrides `async_stream_tts_audio` ([`tts/entity.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/entity.py#L93-L98)).

`SpeechManager.async_create_result_stream` stores whether the selected engine supports streaming input; Assist uses that flag to decide whether response text can stream while the conversation agent is still generating ([`tts/__init__.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/__init__.py#L849-L885), [`assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py#L663-L672)).

The Assist pipeline begins streaming response text only when the selected TTS stream supports streaming input and enough response text has arrived. The threshold constant is 60 characters, and it also starts streaming when a tool call follows text ([`assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py#L105-L105), [`assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py#L1121-L1208)).

When streaming starts, HA concatenates the already queued deltas into the first generator chunk, then yields later assistant deltas as they arrive ([`assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py#L1190-L1208)).

Implication: the proxy should override `async_stream_tts_audio` if it wants Assist to advertise `stream_response: true`. Without that override, it will still work, but Assist will wait for the complete response and use one-shot synthesis.

### Streaming chunks are not safe replacement boundaries

The Assist pipeline forwards `delta["content"]` values into the TTS text queue without splitting or normalizing them by words or sentences ([`assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py#L1128-L1155)).

The ElevenLabs TTS integration explicitly handles this by using a sentence boundary detector; its source comment states that text chunks may not be on word or sentence boundaries ([`elevenlabs/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/elevenlabs/tts.py#L207-L225)).

Implication: matching `°C`, `kWh`, decimals, abbreviations, or multi-token rules cannot be implemented as a naive per-chunk `.replace()`. The proxy needs a streaming text normalizer with retained suffix context and flush rules.

### Audio format and preferred output options matter

The TTS manager treats preferred output options such as `preferred_format`, `preferred_sample_rate`, `preferred_sample_channels`, and `preferred_sample_bytes` as either provider options if supported or ffmpeg conversion parameters otherwise ([`tts/__init__.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/tts/__init__.py#L1044-L1079), [TTS user docs](https://www.home-assistant.io/integrations/tts)).

Assist prepares preferred output options from the requested TTS audio output, and for WAV it requests 16 kHz, 16-bit mono ([`assist_pipeline/pipeline.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/assist_pipeline/pipeline.py#L1417-L1437)).

Implication: the proxy should preserve preferred audio options and pass them through to the delegate when valid. If the proxy hides delegate-supported options, Assist satellites may receive less compatible audio.

## Design Implications

### Recommended architecture

Create a config-entry based `tts_proxy` custom integration that exposes one or more `TextToSpeechEntity` instances. Each proxy entity has:

- a selected delegate TTS entity ID, for example `tts.home_assistant_cloud`;
- a configured output language that is exposed to Home Assistant and passed to the delegate;
- a replacement profile owned by that proxy entity;
- policy flags for streaming fallback, cache behavior, and unknown options.

For one-shot input:

1. Receive `message`, `language`, and `options`.
2. Normalize the full message.
3. Resolve the delegate entity via HA's TTS helper/manager.
4. Call the delegate one-shot TTS path.
5. Return the delegate's extension and bytes.

For streaming input:

1. Receive `TTSAudioRequest.message_gen`.
2. Wrap it in a normalizing async generator.
3. If the delegate supports streaming input, call the delegate's `internal_async_stream_tts_audio` with the normalized generator.
4. If the delegate does not support streaming input, join and normalize the full message, then call one-shot.

### Replacement engine requirements

The stream normalizer should be rule-based but boundary-aware:

- Never apply replacements independently per incoming chunk.
- Keep a bounded suffix buffer at least as long as the longest left-hand pattern plus enough token context for number/unit rules.
- Flush on safe boundaries: whitespace after punctuation, sentence boundaries, or after a maximum latency/character threshold.
- Prefer regex or tokenizer rules over literal replacement for numbers, decimals, and unit inflection.
- Keep replacement rules owned by the configured proxy entity. Users create separate proxy entities for different language/provider contexts.
- Preserve provider control markup intentionally. The design decision is to treat XML-like tags and square-bracket provider tags as opaque segments, applying replacements only to normal speech text around them.

### Capability mirroring

The proxy entity should decide whether it mirrors the delegate's metadata live or stores it at config time:

- `supported_languages`: best mirrored from the delegate, with optional language filtering.
- `default_language`: best mirrored from the delegate.
- `supported_options`: should include only options that the proxy will pass through or handle. At minimum, pass through `voice` and HA preferred audio options.
- `async_get_supported_voices(language)`: should delegate to the selected target TTS entity.
- `async_supports_streaming_input`: should return true only when the proxy implements streaming and either can stream to the delegate or has an explicit "stream input but buffer all before audio" behavior. For good Assist UX, true should mean it can produce audio before the full LLM response is done.

### Risks to decide

- If the delegate is changed while the proxy entity is loaded, cached properties in `TextToSpeechEntity` can make capability changes awkward. A reload or entity-state update may be needed.
- Cache keys should be based on normalized text when the proxy is the selected engine. HA will naturally hash the incoming original message before it reaches the proxy only if the proxy delegates via nested media-source generation; direct delegate calls avoid a double-cache mismatch.
- Self-selection must be prevented: a proxy entity must not delegate to itself or to another proxy that cycles back.
- The first version should probably not try to be a global TTS interception layer. HA's current extension point is selectable TTS entities, not arbitrary middleware.

## Preliminary Recommendation

Build a selectable TTS proxy entity, not a custom service wrapper and not a monkey patch of the TTS building block.

Implement both:

- `async_get_tts_audio` for normal `tts.speak`, REST URL generation, media players, and non-streaming providers.
- `async_stream_tts_audio` for Assist/LLM streaming, with a buffering text-normalizer generator.

For an MVP, support:

- one proxy entity per config entry;
- one selected delegate TTS entity;
- one configured output language;
- literal and regex replacement rules owned by the proxy entity;
- pass-through `voice` and preferred audio options;
- streaming only when the delegate supports streaming; otherwise explicitly fall back to full-message synthesis.

Defer:

- SSML generation/parsing beyond preserving tags as opaque text;
- automatic number-to-words beyond targeted unit/decimal rules;
- multiple delegate routing by language/voice;
- global interception of all TTS calls.
