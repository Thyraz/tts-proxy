# TTS Proxy

This context covers text normalization before Home Assistant text-to-speech synthesis.

## Language

**Proxy TTS Entity**:
A selectable Home Assistant text-to-speech entity that receives text, applies configured replacements, and delegates final speech synthesis to another TTS entity. It is not aware of whether it is used by Assist, automations, media players, or any other caller. It is unavailable when its Final TTS Entity is unavailable or missing.
_Avoid_: middleware, wrapper service, global interceptor

**Final TTS Entity**:
The non-proxy Home Assistant text-to-speech entity selected in a Proxy TTS Entity's configuration to perform the actual speech synthesis after replacements have been applied.
_Avoid_: backend, downstream service

**Output Language**:
The single TTS language exposed by a Proxy TTS Entity and passed to its Final TTS Entity during synthesis.
_Avoid_: replacement language, input language

**Proxy Configuration**:
The required setup data for one Proxy TTS Entity: display name, Final TTS Entity, Output Language, and replacement rules. The Output Language must be supported by the Final TTS Entity when the configuration is saved. Each config entry owns exactly one Proxy TTS Entity.
_Avoid_: runtime selector

**Proxy Reconfiguration**:
Changing a Proxy TTS Entity's Final TTS Entity, Output Language, or replacement rules through Home Assistant configuration flows after the entity has been created.
_Avoid_: per-call routing

**Passthrough TTS Option**:
A per-call Home Assistant TTS option accepted by the Proxy TTS Entity only because it is supported by the Final TTS Entity or is one of Home Assistant's preferred audio output options.
_Avoid_: replacement option

**Replacement Rule**:
A configured text normalization rule owned by a Proxy TTS Entity. In the MVP, rules use literal or regex matching to define what input text to match and what output text to emit before delegating to the Final TTS Entity. Rules run in user-configured order, and each rule sees the output of previous rules. Each rule is applied once per normalization pass, not recursively until stable. Matching is case-sensitive by default, with an optional per-rule ignore-case flag. Each rule can be enabled or disabled without being deleted. Regex rules must compile successfully before Proxy Configuration or Proxy Reconfiguration is saved.
_Avoid_: per-call option

**Rule Preset**:
A future package of suggested Replacement Rules for a common language or use case. Rule Presets are not part of the MVP.
_Avoid_: built-in grammar

**Provider Control Tag**:
Inline markup in TTS input that a Final TTS Entity may interpret as voice, pronunciation, pause, or delivery control. Provider Control Tags are preserved by the Proxy TTS Entity and are not changed by Replacement Rules unless a future feature explicitly allows that.
_Avoid_: replacement target

**Streaming Safety Tail**:
The configurable number of trailing characters a Proxy TTS Entity keeps unflushed while normalizing streamed text, so replacements can still match text that arrives across chunk boundaries.
_Avoid_: chunk size

**Streaming Buffer Limit**:
The configurable maximum pending text size a Proxy TTS Entity allows before flushing at a safe whitespace boundary while keeping the Streaming Safety Tail.
_Avoid_: timeout
