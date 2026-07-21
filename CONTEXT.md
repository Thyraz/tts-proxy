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
A configured text normalization rule owned by a Proxy TTS Entity. In the MVP, rules use literal or regex matching to define what input text to match and what output text to emit before delegating to the Final TTS Entity. Rules run in user-configured order, and each rule sees the output of previous rules. Each rule is applied once per normalization pass, not recursively until stable. Matching is case-insensitive by default, with an optional per-rule case-sensitive flag. Each rule can be enabled or disabled without being deleted. Regex rules must compile successfully before Proxy Configuration or Proxy Reconfiguration is saved.
_Avoid_: per-call option

**Number Normalizer**:
An optional built-in normalizer owned by a Proxy TTS Entity that converts eligible numeric text into language-specific spoken words after Replacement Rules have run and before delegating to the Final TTS Entity. It is configured separately from Replacement Rules because it needs token classification and language-specific number grammar, not simple string matching.
_Avoid_: number replacement rule, regex number rule

**Eligible Numeric Text**:
Numeric text that the Number Normalizer may safely spell out without guessing a higher-level structure. Simple integers and one-separator decimals are eligible; grouped or structured tokens such as times, dates, versions, IP addresses, and alphanumeric identifiers are left for Replacement Rules or future dedicated normalizers.
_Avoid_: number-looking text, all numbers

**Number Spellout Language**:
The language selected for a Number Normalizer to spell numeric text as words. It may match the Output Language, but it is a separate configuration choice because number spellout support is not identical to Final TTS Entity language support.
_Avoid_: output language, TTS language

**Date Normalizer**:
An optional built-in normalizer owned by a Proxy TTS Entity that detects configured date strings, validates them as calendar dates, and replaces them with spoken date text before the Number Normalizer runs. Curated languages may use natural month-name output; other languages may fall back to numeric spoken date parts.
_Avoid_: date replacement rule, natural-language date parser

**Date Input Format**:
A configured date token format that the Date Normalizer is allowed to detect, such as a day-month-year, year-month-day, or day-month-without-year format. Date Input Formats are owned by Proxy Configuration and are not inferred from a Home Assistant frontend user's profile.
_Avoid_: user date format, locale guess

**Month-Name Date**:
A Date Input Format that contains a written month name rather than a numeric month, such as `15. August 2025`, `March 15, 2025`, or `15 March`. In the MVP, Month-Name Dates are curated for German and English only.
_Avoid_: natural-language date

**No-Year Date**:
A date string that contains a day and month but no year, such as `14.05.` or `15. August`. The Date Normalizer speaks only the day and month for No-Year Dates and does not infer or append the current year.
_Avoid_: incomplete date, implicit current-year date

**Date Boundary**:
A text boundary that allows the Date Normalizer to treat neighboring characters as outside a date token. Starts, ends, whitespace including newlines, and selected surrounding punctuation are Date Boundaries; letters, digits, underscores, and structural characters inside versions, IPs, times, or units are not. For `DD.MM.` No-Year Dates, the final dot is part of the date token, but may be preserved as sentence punctuation when the date ends a sentence or line.
_Avoid_: normal punctuation

**Date Locale**:
The locale selected for the Date Normalizer to choose default Date Input Formats and language-specific spoken date rendering. It may default from Output Language or Number Spellout Language, but remains separate because date ordering is regional while number spellout is primarily language-specific.
_Avoid_: output language, number spellout language

**Date Renderer**:
The Date Normalizer strategy that turns a validated date into spoken text for a Date Locale. German and English may use curated Date Renderers; other languages require an explicit Numeric Fallback Date Renderer until they are curated.
_Avoid_: date format, number normalizer

**Numeric Fallback Date Renderer**:
A Date Renderer that speaks day, month, and optional year as numeric parts without claiming language-specific natural date grammar. It is explicit and preview-driven for non-curated languages.
_Avoid_: generic date renderer, automatic locale support

**Normalization Preview**:
A configuration-time view of the text a Proxy TTS Entity would send to its Final TTS Entity after applying Replacement Rules and the Number Normalizer. It uses unsaved form values when available, does not synthesize audio, and does not change saved configuration.
_Avoid_: TTS preview, Assist preview, test playback

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
