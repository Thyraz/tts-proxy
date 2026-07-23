# TTS Proxy Spec

## Problem Statement

Home Assistant users can choose from many text-to-speech engines, but TTS output is often poor for dates, numbers, decimals, units, abbreviations, and symbols. This is especially visible when an LLM Assist response is spoken in a language or style the TTS service does not handle well.

Users need a caller-agnostic Home Assistant TTS entity that can be selected anywhere Home Assistant supports TTS, applies configured text processing to incoming text, and forwards the processed text to another TTS entity for synthesis. It must work for normal one-shot TTS and preserve streaming behavior when the target TTS entity supports streaming.

## Solution

Build a custom Home Assistant integration that exposes one Proxy TTS Entity per config entry. The Proxy TTS Entity is selected like any other TTS entity. It receives text, applies configured Replacement Rules, optional Markdown Cleanup, optional Date Normalizer processing, and optional Number Normalizer processing, then delegates directly to its configured Target TTS Entity.

The Proxy Configuration requires:

- display name
- Target TTS Entity
- Output Language
- Replacement Rules
- Markdown Cleanup settings
- Date Normalizer settings
- Number Normalizer settings
- Minimal Lookahead Buffer Length
- Maximal Buffer Limit

The Proxy TTS Entity exposes exactly one Output Language and passes it to the Target TTS Entity during synthesis. Replacement Rules are not language-scoped in the MVP; the user creates one proxy entity for the intended input and output context.

For one-shot TTS, the proxy processes the full message and calls the Target TTS Entity directly. For streaming TTS, the proxy wraps the incoming text generator with a streaming-safe normalizer and delegates that processed stream to the Target TTS Entity when it supports streaming. If the Target TTS Entity does not support streaming, the proxy reports itself as non-streaming and uses full-message processing/synthesis.

## User Stories

1. As a Home Assistant user, I want to create a Proxy TTS Entity, so that I can select it anywhere Home Assistant supports TTS.
2. As a Home Assistant user, I want to choose a Target TTS Entity during setup, so that the proxy knows where to send processed text.
3. As a Home Assistant user, I want to choose one Output Language during setup, so that Home Assistant and the Target TTS Entity receive a valid TTS language.
4. As a Home Assistant user, I want setup to reject unsupported Output Languages, so that speech does not fail later at runtime.
5. As a Home Assistant user, I want to name the proxy entity, so that I can distinguish multiple processed TTS setups.
6. As a Home Assistant user, I want one config entry to create one Proxy TTS Entity, so that each entity has a clear rule set and Target TTS Entity.
7. As a Home Assistant user, I want to reconfigure the Target TTS Entity later, so that I can switch TTS providers without recreating automations.
8. As a Home Assistant user, I want reconfiguration to require a valid Output Language for the new Target TTS Entity, so that the proxy remains valid after changes.
9. As a Home Assistant user, I want the proxy entity to keep the same identity after reconfiguration, so that automations and Assist pipeline selections do not break.
10. As a Home Assistant user, I want the proxy to become unavailable if the Target TTS Entity disappears, so that broken configuration is visible before speech is requested.
11. As a Home Assistant user, I want to configure literal Replacement Rules, so that simple strings like `°C` can become `Grad`.
12. As a Home Assistant user, I want to configure regex Replacement Rules, so that patterns like numbers followed by units can be rewritten.
13. As a Home Assistant user, I want regex capture groups in replacement output, so that dynamic parts of the input can be preserved.
14. As a Home Assistant user, I want rules to run in the order I configured them, so that I can reason about rule interactions.
15. As a Home Assistant user, I want each rule to run once per normalization pass, so that a rule cannot recursively expand forever.
16. As a Home Assistant user, I want matching to be case-insensitive by default, so that words with variable capitalization are normalized without extra configuration.
17. As a Home Assistant user, I want a case-sensitive option per rule, so that acronyms and units can be protected when needed.
18. As a Home Assistant user, I want to disable a rule without deleting it, so that I can test pronunciation changes.
19. As a Home Assistant user, I want invalid regex rules rejected during setup or reconfiguration, so that TTS does not break at runtime.
20. As a Home Assistant user, I want to name Replacement Rules, so that I can understand cryptic regex or unit rules in the collapsed options UI.
21. As a Home Assistant user, I want Replacement Rules configured on the entity, not per TTS call, so that callers do not need to know the proxy exists.
22. As a Home Assistant user, I want the proxy to preserve ElevenLabs-style square-bracket audio tags, so that voice direction such as `[whispers]` still reaches the Target TTS Entity.
23. As a Home Assistant user, I want the proxy to preserve XML-like tags, so that SSML-like or provider-specific markup is not corrupted.
24. As a Home Assistant user, I want replacements applied only to normal speech text around Provider Control Tags, so that control markup remains intact.
25. As a Home Assistant user, I want streaming responses to remain streaming when the Target TTS Entity supports streaming, so that voice responses start promptly.
26. As a Home Assistant user, I want the proxy to avoid per-chunk replacement bugs, so that split chunks like `53`, `.4`, `°`, `C` normalize correctly.
27. As a Home Assistant user, I want a configurable Minimal Lookahead Buffer Length, so that I can tune correctness for longer local patterns.
28. As a Home Assistant user, I want a configurable Maximal Buffer Limit, so that streaming does not wait too long for ideal punctuation.
29. As a Home Assistant user, I want the proxy to fall back to non-streaming behavior when the Target TTS Entity cannot stream, so that behavior is honest and reliable.
30. As a Home Assistant user, I want voice and audio-format options to pass through when the Target TTS Entity supports them, so that provider voices and satellite audio requirements still work.
31. As a Home Assistant user, I want preferred audio output options preserved, so that Assist satellites and media players can receive compatible audio.
32. As a Home Assistant user, I want the proxy to avoid selecting itself as a Target TTS Entity, so that recursive calls cannot happen.
33. As a Home Assistant user, I want proxy-to-proxy delegation disallowed in the MVP, so that behavior stays understandable and cycle-free.
34. As a Home Assistant user, I want one-shot TTS cached by Home Assistant at the proxy level, so that repeated identical original input is efficient.
35. As a Home Assistant user, I want no nested target-entity HA cache entry, so that caching and streaming behavior stay under the proxy boundary.
36. As a Home Assistant user, I want a preview area in the options flow, so that I can test unsaved settings without generating audio.
37. As a Home Assistant user, I want optional Markdown Cleanup, so that LLM responses with Markdown syntax can be made safer for TTS services that speak formatting characters.
38. As a Home Assistant user, I want Markdown Cleanup features to be individually enabled, so that I can keep syntax my Target TTS Entity already handles well.
39. As a Home Assistant user, I want Markdown links reduced to their visible text, so that URLs do not dominate spoken output when a useful label exists.
40. As a Home Assistant user, I want table formatting removed without pretending to fully explain tables, so that TTS output is less confusing while remaining language-neutral.
41. As a Home Assistant user, I want isolated square-bracket Provider Control Tags preserved even when Markdown Cleanup is enabled, so that tags such as `[whispers]` still reach the Target TTS Entity.
42. As a future user, I want rule presets to be possible later, so that common language/use-case replacements can be added without changing the MVP model.
43. As a future user, I want template replacement mode to be possible later, so that advanced dynamic normalization can be explored after streaming and caching semantics are designed.

## Implementation Decisions

- Build a Home Assistant custom integration exposing a real Proxy TTS Entity, not a custom service wrapper or global middleware.
- Use config-entry based setup and options flow. Do not use legacy `tts:` YAML platform configuration.
- Create exactly one Proxy TTS Entity per config entry.
- Require a Target TTS Entity at setup time. The entity is not created in a usable-but-unconfigured state.
- Require a single Output Language supported by the Target TTS Entity.
- Allow Proxy Reconfiguration through an options flow. Changing the Target TTS Entity requires choosing a valid Output Language for the new target entity and reloading the config entry.
- Preserve proxy entity identity across Proxy Reconfiguration so Home Assistant references remain stable.
- The Target TTS Entity must be a non-proxy TTS entity in the MVP. Prevent self-selection and proxy-to-proxy delegation.
- The Proxy TTS Entity is unavailable when the Target TTS Entity is unavailable or missing. Runtime calls should still fail clearly if availability changes mid-call.
- Delegate directly to the Target TTS Entity after normalization, rather than creating a nested Home Assistant TTS media-source URL.
- Implement both one-shot and streaming TTS methods on the Proxy TTS Entity.
- Report streaming support only when the configured Target TTS Entity supports streaming.
- For one-shot input, apply replacements to the complete message and delegate to the Target TTS Entity's one-shot synthesis path.
- For streaming input, wrap the incoming message generator in a streaming normalizer and pass the processed stream to the Target TTS Entity's streaming API.
- If the Target TTS Entity cannot stream, join the input stream, normalize the complete message, and use one-shot synthesis.
- Use proxy-level HA caching for one-shot input. Do not create a nested target-entity cache entry.
- Pass through Passthrough TTS Options only when supported by the Target TTS Entity or when they are Home Assistant preferred audio output options.
- Delegate supported voices to the Target TTS Entity for the configured Output Language.
- Replacement Rules live in Proxy Configuration, not per-call TTS options.
- The MVP rule modes are literal and regex.
- Literal rules perform exact string replacement.
- Regex rules use Python-style regex substitution with capture groups.
- Replacement Rules run in user-configured order.
- Each Replacement Rule is applied once per normalization pass, not recursively until stable.
- Matching is case-insensitive by default, with an optional per-rule case-sensitive flag.
- Each Replacement Rule has an enabled flag.
- Each Replacement Rule may have an optional display-only name.
- The options flow displays Replacement Rule rows with Name as the primary row text and Find as the secondary row text, following Home Assistant ObjectSelector constraints.
- Regex rules must compile successfully before Proxy Configuration or Proxy Reconfiguration is saved.
- Markdown Cleanup, date detection, and number detection are separate optional normalizers that run after user-defined Replacement Rules.
- The normalization pipeline is Replacement Rules, then Markdown Cleanup, then Date Normalizer, then Number Normalizer.
- Markdown Cleanup is disabled by default. When enabled, emphasis, headings, list markers, table formatting, Markdown links, inline code backticks, blockquote markers, divider lines, strikethrough markers, and image syntax cleanup are enabled by default; plain URL removal and fenced code block removal are opt-in.
- Markdown Cleanup is a conservative cleanup normalizer, not a semantic Markdown-to-speech renderer. It does not announce table structure, infer column meaning, parse HTML tags, or process reference-style links.
- The Number Normalizer spells simple leading-zero integers digit by digit, while one-separator decimals are normalized by removing leading integer zeroes and trailing fractional zeroes before spellout.
- The German Date Renderer uses deterministic immediate left-context rules for clear article and preposition patterns, but does not use a general NLP parser.
- Sloppy spaced numeric date formats such as `DD. MM. YYYY` are separate Date Input Formats. The German default enables the full-year spaced form, but not the no-year spaced form.
- Numeric No-Year Date candidates separated only by whitespace are left unchanged; a visible separator or word between candidates allows normalization.
- Locale-specific unit grammar remains user-defined through Replacement Rules.
- The options flow groups settings into General, Replacement Rules, Markdown Cleanup, Date Normalizer, Number Normalizer, and Settings for TTS Streaming sections, then places Preview Input as the final top-level field directly before the Home Assistant preview output.
- The options flow includes a preview area that uses current unsaved settings and does not generate audio.
- Preserve Provider Control Tags as opaque segments for Replacement Rules, Date Normalizer, and Number Normalizer. Markdown Cleanup may rewrite explicit Markdown constructs such as `[label](url)`, `![alt](url)`, and task-list markers, but isolated square-bracket spans and XML-like `<...>` spans remain protected.
- The streaming normalizer keeps a configurable Minimal Lookahead Buffer Length, defaulting to 64 characters.
- The streaming normalizer keeps a configurable Maximal Buffer Limit, defaulting to 500 characters.
- The streaming normalizer flushes preferentially at sentence-like punctuation boundaries before the Minimal Lookahead Buffer Length.
- Sentence-like punctuation requires boundary evidence such as following whitespace, newline, or stream end; decimal punctuation such as `53.4` must not be treated as a sentence split.
- If no sentence-like boundary appears and pending text exceeds the Maximal Buffer Limit, flush up to a safe whitespace boundary while keeping the Minimal Lookahead Buffer Length.
- When the input stream ends, normalize and flush all remaining pending text even if there is no trailing punctuation or whitespace.

## Testing Decisions

The primary test seam is the Proxy TTS Entity contract with fake Target TTS Entities. Tests should call the same one-shot and streaming methods Home Assistant will call, and assert the resulting text passed to the fake target entity plus the reported audio behavior.

The supporting test seam is the pure text normalizer. It should be tested directly for dense edge cases that would be hard to observe through entity-level tests: chunk splits, Provider Control Tags, Markdown cleanup, punctuation boundaries, regex capture groups, disabled rules, case-sensitive behavior, date detection, number detection, and invalid regex validation.

Good tests should verify externally visible behavior:

- entity setup accepts valid Proxy Configuration and rejects invalid configuration
- unsupported Output Language is rejected
- missing or unavailable Target TTS Entity makes the Proxy TTS Entity unavailable
- one-shot text is processed before delegation
- streaming text split across arbitrary chunks is processed correctly
- streaming support is reported only when the Target TTS Entity supports streaming
- non-streaming Target TTS Entity receives full processed text
- preview shows the processed text for current unsaved options
- Markdown Cleanup preserves Provider Control Tags while simplifying configured Markdown syntax
- Provider Control Tags are preserved and not modified by Replacement Rules
- Passthrough TTS Options are accepted only when valid for the Target TTS Entity or HA preferred audio output
- reconfiguration reloads capabilities while preserving proxy identity

Tests should stay focused on the Home Assistant-facing TTS entity behavior and the pure text-processing helpers behind it.

## Out of Scope

- Global interception of all Home Assistant TTS calls.
- Multiple Target TTS Entities per Proxy TTS Entity.
- Dynamic routing by language, voice, caller, media player, or Assist pipeline.
- Proxy-to-proxy delegation in the MVP.
- Built-in locale-specific unit grammar beyond user-defined Replacement Rules.
- Full semantic Markdown-to-speech rendering.
- HTML cleanup or structured XML parsing beyond preserving `<...>` spans as opaque text.
- Rule Presets.
- HA template replacement mode.
- Audio preview or a separate preview service/action.
- SSML generation.
- Provider-specific semantic parsing of square-bracket audio tags.
- Custom frontend beyond native Home Assistant config/options flow controls.

## Further Notes

The research note in `docs/research/home-assistant-tts-proxy.md` captures the Home Assistant source and documentation checked on 2026-07-20. The architectural decisions are recorded in ADRs under `docs/adr/`.

The configured issue tracker is GitHub.
