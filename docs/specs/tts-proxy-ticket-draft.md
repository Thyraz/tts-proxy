# TTS Proxy Ticket Draft

This breakdown captures the initial implementation plan for TTS Proxy.

## 01 - Create a minimal Proxy TTS Entity with one-shot passthrough

**Blocked by:** None - can start immediately.

**What it delivers:** A user can create one Proxy TTS Entity with a display name, Target TTS Entity, and Output Language, then use it as a normal TTS entity that delegates one-shot synthesis unchanged to the Target TTS Entity.

**Acceptance criteria**

- [ ] A config entry creates exactly one Proxy TTS Entity.
- [ ] Setup requires display name, Target TTS Entity, and Output Language.
- [ ] Setup rejects missing Target TTS Entity.
- [ ] Setup rejects Output Languages not supported by the Target TTS Entity.
- [ ] Setup prevents selecting the proxy itself or another proxy as the Target TTS Entity.
- [ ] The proxy exposes only its configured Output Language.
- [ ] One-shot TTS calls delegate directly to the Target TTS Entity and return its audio result.
- [ ] Tests cover successful setup, invalid setup, and one-shot passthrough.

## 02 - Add Replacement Rules for one-shot normalization

**Blocked by:** 01 - Create a minimal Proxy TTS Entity with one-shot passthrough.

**What it delivers:** A user can configure literal and regex Replacement Rules, then one-shot TTS input is processed before direct delegation.

**Acceptance criteria**

- [ ] Replacement Rules are stored in Proxy Configuration, not passed per call.
- [ ] Literal rules perform exact string replacement.
- [ ] Regex rules use Python-style substitution with capture groups.
- [ ] Rules run in user-configured order.
- [ ] Each rule is applied once per normalization pass.
- [ ] Rules are case-insensitive by default.
- [ ] Each rule supports a case-sensitive flag.
- [ ] Each rule supports an enabled flag.
- [ ] Each rule supports an optional display-only name.
- [ ] Collapsed rule rows show the rule name as primary text and the find value as secondary text.
- [ ] Invalid regex rules are rejected before configuration is saved.
- [ ] Every `<...>` and `[...]` span is preserved as a Provider Control Tag and not changed by Replacement Rules.
- [ ] One-shot TTS delegates processed text to the Target TTS Entity.
- [ ] Tests cover literals, regex captures, rule order, one-pass behavior, ignore-case, disabled rules, invalid regex, and Provider Control Tags.

## 03 - Add streaming normalization and honest streaming capability

**Blocked by:** 02 - Add Replacement Rules for one-shot normalization.

**What it delivers:** A user keeps streaming TTS behavior when the Target TTS Entity supports streaming, while replacements remain correct across arbitrary streamed text chunks.

**Acceptance criteria**

- [ ] The proxy reports streaming support only when the configured Target TTS Entity supports streaming.
- [ ] Streaming input is processed with a bounded pending buffer, not per incoming chunk.
- [ ] Minimal Lookahead Buffer Length defaults to 64 characters.
- [ ] Maximal Buffer Limit defaults to 500 characters.
- [ ] Both buffer settings are configurable per proxy entity.
- [ ] The normalizer flushes at sentence-like punctuation boundaries before the Minimal Lookahead Buffer Length.
- [ ] Decimal punctuation such as `53.4` is not treated as a sentence boundary.
- [ ] If the buffer exceeds the Maximal Buffer Limit, the normalizer flushes at a safe whitespace boundary while preserving the Minimal Lookahead Buffer Length.
- [ ] End of stream flushes all remaining pending text.
- [ ] If the Target TTS Entity supports streaming, the proxy delegates a processed text stream to it.
- [ ] If the Target TTS Entity does not support streaming, the proxy uses full-message normalization and one-shot synthesis.
- [ ] Tests cover split replacements, split Provider Control Tags, decimal punctuation, final flush without trailing punctuation, streaming delegation, and non-streaming fallback.

## 04 - Mirror Target TTS Entity capabilities and pass through valid options

**Blocked by:** 01 - Create a minimal Proxy TTS Entity with one-shot passthrough.

**What it delivers:** A user can keep using provider voices and Home Assistant preferred audio output options through the proxy without making replacement behavior a per-call option.

**Acceptance criteria**

- [ ] The proxy exposes only Passthrough TTS Options supported by the Target TTS Entity or Home Assistant preferred audio output options.
- [ ] Voice options are delegated to the Target TTS Entity when supported.
- [ ] Supported voices for the Output Language are delegated from the Target TTS Entity.
- [ ] Preferred audio output options are passed through so downstream audio requirements still work.
- [ ] Unsupported provider-specific options are rejected consistently with Home Assistant TTS option validation.
- [ ] Tests cover voice passthrough, preferred audio output passthrough, and unsupported option rejection.

## 05 - Add Proxy Reconfiguration and availability behavior

**Blocked by:** 02 - Add Replacement Rules for one-shot normalization; 04 - Mirror Target TTS Entity capabilities and pass through valid options.

**What it delivers:** A user can change the proxy display name, Target TTS Entity, Output Language, Replacement Rules, Minimal Lookahead Buffer Length, and Maximal Buffer Limit after setup without breaking existing Home Assistant references.

**Acceptance criteria**

- [ ] Options flow can change display name.
- [ ] Options flow can change Target TTS Entity.
- [ ] Changing Target TTS Entity requires choosing a supported Output Language for the new Target TTS Entity.
- [ ] Options flow can edit Replacement Rules.
- [ ] Options flow can edit Minimal Lookahead Buffer Length and Maximal Buffer Limit.
- [ ] Saving options reloads the config entry so cached capabilities are rebuilt.
- [ ] Proxy entity identity remains stable across Proxy Reconfiguration.
- [ ] The Proxy TTS Entity becomes unavailable when the Target TTS Entity is unavailable or missing.
- [ ] Runtime calls fail clearly if the Target TTS Entity becomes unavailable mid-call.
- [ ] Tests cover reconfiguration, stable identity, capability refresh, and unavailable Target TTS Entity behavior.

## 06 - Finish MVP UX, documentation, and examples

**Blocked by:** 03 - Add streaming normalization and honest streaming capability; 05 - Add Proxy Reconfiguration and availability behavior.

**What it delivers:** A user can install and configure the MVP with understandable labels, native Home Assistant controls, and examples for common replacements.

**Acceptance criteria**

- [ ] Config and options flows use native Home Assistant selectors where possible.
- [ ] Replacement Rules are edited as structured rows rather than one large text blob.
- [ ] User-facing strings explain Target TTS Entity, Output Language, Minimal Lookahead Buffer Length, and Maximal Buffer Limit.
- [ ] Documentation includes German examples such as `°C -> Grad` and `kWh -> Kilowattstunden`.
- [ ] Documentation explains that `<...>` and `[...]` spans are preserved and not changed in the MVP.
- [ ] Documentation explains that templates, Rule Presets, audio preview, built-in unit grammar, and proxy-to-proxy delegation are out of scope for the MVP.
- [ ] Final verification covers one-shot TTS and streaming TTS through fake or real-compatible test entities.

## 07 - Add Markdown Cleanup Normalizer

**Blocked by:** 03 - Add streaming normalization and honest streaming capability; 06 - Finish MVP UX, documentation, and examples.

**What it delivers:** A user can optionally simplify common Markdown syntax before text reaches date and number normalization.

**Acceptance criteria**

- [ ] Markdown Cleanup is a separate optional normalizer and is disabled by default.
- [ ] Markdown Cleanup runs after Replacement Rules and before Date Normalizer and Number Normalizer.
- [ ] Each cleanup behavior can be enabled independently.
- [ ] Enabled cleanup can strip emphasis, headings, list markers, table formatting, Markdown links, inline code backticks, blockquote markers, divider lines, strikethrough markers, and image syntax.
- [ ] Plain URL removal and fenced code block removal are opt-in.
- [ ] Markdown links keep visible link text and remove the URL target.
- [ ] Table cleanup removes separator lines and replaces cell separators with punctuation without announcing table semantics.
- [ ] Isolated square-bracket Provider Control Tags such as `[whispers]` are preserved.
- [ ] Options flow settings are grouped into native Home Assistant sections, with Preview Input as the final top-level field before the preview output.
- [ ] Preview uses unsaved sectioned form data.
- [ ] Tests cover Markdown cleanup behavior, pipeline order, Provider Control Tags, sectioned config flattening, and preview config flattening.
