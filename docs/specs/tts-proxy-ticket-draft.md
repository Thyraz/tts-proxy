# TTS Proxy Ticket Draft

This breakdown has been approved for publication. The repo is configured for GitHub issues, but there is no Git remote yet, so these are not published tickets.

## 01 - Create a minimal Proxy TTS Entity with one-shot passthrough

**Blocked by:** None - can start immediately.

**What it delivers:** A user can create one Proxy TTS Entity with a display name, Final TTS Entity, and Output Language, then use it as a normal TTS entity that delegates one-shot synthesis unchanged to the Final TTS Entity.

**Acceptance criteria**

- [ ] A config entry creates exactly one Proxy TTS Entity.
- [ ] Setup requires display name, Final TTS Entity, and Output Language.
- [ ] Setup rejects missing Final TTS Entity.
- [ ] Setup rejects Output Languages not supported by the Final TTS Entity.
- [ ] Setup prevents selecting the proxy itself or another proxy as the Final TTS Entity.
- [ ] The proxy exposes only its configured Output Language.
- [ ] One-shot TTS calls delegate directly to the Final TTS Entity and return its audio result.
- [ ] Tests cover successful setup, invalid setup, and one-shot passthrough.

## 02 - Add Replacement Rules for one-shot normalization

**Blocked by:** 01 - Create a minimal Proxy TTS Entity with one-shot passthrough.

**What it delivers:** A user can configure literal and regex Replacement Rules, then one-shot TTS input is normalized before direct delegation.

**Acceptance criteria**

- [ ] Replacement Rules are stored in Proxy Configuration, not passed per call.
- [ ] Literal rules perform exact string replacement.
- [ ] Regex rules use Python-style substitution with capture groups.
- [ ] Rules run in user-configured order.
- [ ] Each rule is applied once per normalization pass.
- [ ] Rules are case-sensitive by default.
- [ ] Each rule supports an ignore-case flag.
- [ ] Each rule supports an enabled flag.
- [ ] Invalid regex rules are rejected before configuration is saved.
- [ ] Every `<...>` and `[...]` span is preserved as a Provider Control Tag and not changed by Replacement Rules.
- [ ] One-shot TTS delegates normalized text to the Final TTS Entity.
- [ ] Tests cover literals, regex captures, rule order, one-pass behavior, ignore-case, disabled rules, invalid regex, and Provider Control Tags.

## 03 - Add streaming normalization and honest streaming capability

**Blocked by:** 02 - Add Replacement Rules for one-shot normalization.

**What it delivers:** A user keeps streaming TTS behavior when the Final TTS Entity supports streaming, while replacements remain correct across arbitrary streamed text chunks.

**Acceptance criteria**

- [ ] The proxy reports streaming support only when the configured Final TTS Entity supports streaming.
- [ ] Streaming input is normalized with a bounded pending buffer, not per incoming chunk.
- [ ] Streaming Safety Tail defaults to 64 characters.
- [ ] Streaming Buffer Limit defaults to 500 characters.
- [ ] Both buffer settings are configurable per proxy entity.
- [ ] The normalizer flushes at sentence-like punctuation boundaries before the Streaming Safety Tail.
- [ ] Decimal punctuation such as `53.4` is not treated as a sentence boundary.
- [ ] If the buffer exceeds the Streaming Buffer Limit, the normalizer flushes at a safe whitespace boundary while preserving the Streaming Safety Tail.
- [ ] End of stream flushes all remaining pending text.
- [ ] If the Final TTS Entity supports streaming, the proxy delegates a normalized text stream to it.
- [ ] If the Final TTS Entity does not support streaming, the proxy uses full-message normalization and one-shot synthesis.
- [ ] Tests cover split replacements, split Provider Control Tags, decimal punctuation, final flush without trailing punctuation, streaming delegation, and non-streaming fallback.

## 04 - Mirror Final TTS Entity capabilities and pass through valid options

**Blocked by:** 01 - Create a minimal Proxy TTS Entity with one-shot passthrough.

**What it delivers:** A user can keep using provider voices and Home Assistant preferred audio output options through the proxy without making replacement behavior a per-call option.

**Acceptance criteria**

- [ ] The proxy exposes only Passthrough TTS Options supported by the Final TTS Entity or Home Assistant preferred audio output options.
- [ ] Voice options are delegated to the Final TTS Entity when supported.
- [ ] Supported voices for the Output Language are delegated from the Final TTS Entity.
- [ ] Preferred audio output options are passed through so downstream audio requirements still work.
- [ ] Unsupported provider-specific options are rejected consistently with Home Assistant TTS option validation.
- [ ] Tests cover voice passthrough, preferred audio output passthrough, and unsupported option rejection.

## 05 - Add Proxy Reconfiguration and availability behavior

**Blocked by:** 02 - Add Replacement Rules for one-shot normalization; 04 - Mirror Final TTS Entity capabilities and pass through valid options.

**What it delivers:** A user can change the proxy display name, Final TTS Entity, Output Language, Replacement Rules, Streaming Safety Tail, and Streaming Buffer Limit after setup without breaking existing Home Assistant references.

**Acceptance criteria**

- [ ] Options flow can change display name.
- [ ] Options flow can change Final TTS Entity.
- [ ] Changing Final TTS Entity requires choosing a supported Output Language for the new Final TTS Entity.
- [ ] Options flow can edit Replacement Rules.
- [ ] Options flow can edit Streaming Safety Tail and Streaming Buffer Limit.
- [ ] Saving options reloads the config entry so cached capabilities are rebuilt.
- [ ] Proxy entity identity remains stable across Proxy Reconfiguration.
- [ ] The Proxy TTS Entity becomes unavailable when the Final TTS Entity is unavailable or missing.
- [ ] Runtime calls fail clearly if the Final TTS Entity becomes unavailable mid-call.
- [ ] Tests cover reconfiguration, stable identity, capability refresh, and unavailable Final TTS Entity behavior.

## 06 - Finish MVP UX, documentation, and examples

**Blocked by:** 03 - Add streaming normalization and honest streaming capability; 05 - Add Proxy Reconfiguration and availability behavior.

**What it delivers:** A user can install and configure the MVP with understandable labels, native Home Assistant controls, and examples for common replacements.

**Acceptance criteria**

- [ ] Config and options flows use native Home Assistant selectors where possible.
- [ ] Replacement Rules are edited as structured rows rather than one large text blob.
- [ ] User-facing strings explain Final TTS Entity, Output Language, Streaming Safety Tail, and Streaming Buffer Limit.
- [ ] Documentation includes German examples such as `°C -> Grad` and `kWh -> Kilowattstunden`.
- [ ] Documentation explains that `<...>` and `[...]` spans are preserved and not normalized in the MVP.
- [ ] Documentation explains that templates, Rule Presets, preview service, built-in number grammar, and proxy-to-proxy delegation are out of scope for the MVP.
- [ ] Final verification covers one-shot TTS and streaming TTS through fake or real-compatible test entities.
