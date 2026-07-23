# TTS Proxy

This context covers text replacement and date/number detection before Home Assistant text-to-speech synthesis.

## Language

**Proxy TTS Entity**:
A selectable Home Assistant text-to-speech entity that receives text, applies configured text processing, and delegates speech synthesis to another TTS entity. It is not aware of whether it is used by Assist, automations, media players, or any other caller. It is unavailable when its Target TTS Entity is unavailable or missing.
_Avoid_: middleware, wrapper service, global interceptor

**Target TTS Entity**:
The non-proxy Home Assistant text-to-speech entity selected in a Proxy TTS Entity's configuration to perform the actual speech synthesis after text processing has been applied.
_Avoid_: backend, downstream service

**Output Language**:
The single TTS language exposed by a Proxy TTS Entity and passed to its Target TTS Entity during synthesis.
_Avoid_: replacement language, input language

**Proxy Configuration**:
The setup and options data for one Proxy TTS Entity: display name, Target TTS Entity, Output Language, Replacement Rules, Markdown Cleanup settings, Emoji Normalizer settings, Date Normalizer settings, Number Normalizer settings, and streaming buffer settings. The Output Language must be supported by the Target TTS Entity when the configuration is saved. Each config entry owns exactly one Proxy TTS Entity.
_Avoid_: runtime selector

**Proxy Reconfiguration**:
Changing a Proxy TTS Entity's Target TTS Entity, Output Language, or replacement rules through Home Assistant configuration flows after the entity has been created.
_Avoid_: per-call routing

**Passthrough TTS Option**:
A per-call Home Assistant TTS option accepted by the Proxy TTS Entity only because it is supported by the Target TTS Entity or is one of Home Assistant's preferred audio output options.
_Avoid_: replacement option

**Replacement Rule**:
A user-defined text replacement rule owned by a Proxy TTS Entity. Rules use literal or regex matching to define what input text to match and what output text to emit before delegating to the Target TTS Entity. Rules run in user-configured order, and each rule sees the output of previous rules. Each rule is applied once per normalization pass, not recursively until stable. Matching is case-insensitive by default, with an optional per-rule case-sensitive flag. Each rule can be enabled or disabled without being deleted. Regex rules must compile successfully before Proxy Configuration or Proxy Reconfiguration is saved.
_Avoid_: per-call option

**Replacement Rule Name**:
An optional display-only label for a Replacement Rule. It helps identify a rule in Home Assistant's collapsed options-flow row, but does not affect matching, replacement output, ordering, validation, or runtime behavior.
_Avoid_: rule id, rule condition

**Markdown Cleanup Normalizer**:
An optional built-in normalizer owned by a Proxy TTS Entity that removes or simplifies configured Markdown syntax before Emoji Normalizer, Date Normalizer, and Number Normalizer processing. It is cleanup-oriented rather than a semantic Markdown-to-speech renderer, and each supported Markdown feature can be enabled separately. The MVP supports common emphasis, heading, list, table, link, image, inline-code, code-block, blockquote, divider-line, strikethrough, and plain-URL cleanup, but not reference-style links, footnotes, definition lists, HTML cleanup, escaped Markdown punctuation, or nested Markdown edge cases.
_Avoid_: Markdown renderer, audio formatter

**Emoji Normalizer**:
An optional built-in normalizer owned by a Proxy TTS Entity that either removes emoji or replaces them with localized spoken names. It is separate from Markdown Cleanup because emoji are Unicode text, not Markdown syntax, and because removing emoji is a different user choice from speaking their names.
_Avoid_: emoji cleanup rule, emoji renderer

**Emoji Handling**:
The configured Emoji Normalizer mode. It either removes emoji or spells emoji out as localized names separated from surrounding speech text with commas.
_Avoid_: emoji action, emoji mode

**Emoji Language**:
The language selected for Emoji Normalizer spellout names. It may default from Output Language, but remains a separate configuration choice because emoji name support comes from the emoji package and does not match Target TTS Entity language support exactly.
_Avoid_: output language, TTS language

**Number Normalizer**:
An optional built-in normalizer owned by a Proxy TTS Entity that converts eligible numeric text into language-specific spoken words after Replacement Rules have run and before delegating to the Target TTS Entity. It is configured separately from Replacement Rules because it needs token classification and language-specific number grammar, not simple string matching.
_Avoid_: number replacement rule, regex number rule

**Markdown Link Text**:
The visible label of a Markdown link, such as `Description` in `[Description](https://example.com)`. Markdown Cleanup may keep this text while removing the URL target.
_Avoid_: URL, Provider Control Tag

**Markdown Provider Tag Boundary**:
The boundary between Markdown syntax and Provider Control Tags. Markdown Cleanup may rewrite specific Markdown constructs such as `[label](url)`, `![alt](url)`, and task-list markers, but isolated square-bracket spans such as `[whispers]` remain Provider Control Tags.
_Avoid_: square bracket cleanup, generic bracket stripping

**Plain URL Text**:
A visible URL that is not wrapped in Markdown link syntax. Plain URL cleanup is configured separately from Markdown Link Text because URLs may sometimes be intentional spoken content.
_Avoid_: Markdown link, provider URL

**Markdown Table Cleanup**:
A Markdown Cleanup behavior that removes table separator lines and replaces table cell separators with speech-friendly punctuation. It does not announce table structure, infer column meaning, or render rows with header labels.
_Avoid_: table renderer, spoken table

**Markdown Code Cleanup**:
A Markdown Cleanup behavior that removes inline code markers while keeping inline code text, and may remove fenced code blocks only when explicitly enabled.
_Avoid_: code reader, code explanation

**Markdown Image Cleanup**:
A Markdown Cleanup behavior that replaces image syntax with its alt text and removes the image entirely when no alt text is present.
_Avoid_: image reader, URL cleanup

**Markdown Divider Line**:
A Markdown Cleanup behavior for visual separator lines such as `---`, `***`, or `___`. The CommonMark term is thematic break, but the user-facing label should describe it as a divider line.
_Avoid_: horizontal rule, table separator

**Eligible Numeric Text**:
Numeric text that the Number Normalizer may safely spell out without guessing a higher-level structure. Simple integers, leading-zero integers, and one-separator decimals are eligible; grouped or structured tokens such as times, dates, versions, IP addresses, and alphanumeric identifiers are left for Replacement Rules or dedicated normalizers.
_Avoid_: number-looking text, all numbers

**Leading-Zero Integer Text**:
A simple integer token that starts with one or more zeroes and is spoken as individual digits instead of as a mathematical integer, so the written zeroes remain audible.
_Avoid_: zero-padded number, numeric code

**Number Spellout Language**:
The language selected for a Number Normalizer to spell numeric text as words. It may match the Output Language, but it is a separate configuration choice because number spellout support is not identical to Target TTS Entity language support.
_Avoid_: output language, TTS language

**Date Normalizer**:
An optional built-in normalizer owned by a Proxy TTS Entity that detects configured date strings, validates them as calendar dates, and replaces them with spoken date text before the Number Normalizer runs. Curated languages may use natural month-name output; other languages may fall back to numeric spoken date parts.
_Avoid_: date replacement rule, natural-language date parser

**Date Input Format**:
A configured date token format that the Date Normalizer is allowed to detect, such as a day-month-year, year-month-day, or day-month-without-year format. Date Input Formats are owned by Proxy Configuration and are not inferred from a Home Assistant frontend user's profile.
_Avoid_: user date format, locale guess

**Sloppy Spaced Numeric Date**:
A tolerated Date Input Format where whitespace appears after numeric date punctuation, such as `23. 05. 2026`. It is separate from the compact numeric Date Input Format so users can disable it independently.
_Avoid_: standard date spelling, inferred LLM typo

**Month-Name Date**:
A Date Input Format that contains a written month name rather than a numeric month, such as `15. August 2025`, `March 15, 2025`, or `15 March`. In the MVP, Month-Name Dates are curated for German and English only.
_Avoid_: natural-language date

**No-Year Date**:
A date string that contains a day and month but no year, such as `14.05.` or `15. August`. The Date Normalizer speaks only the day and month for No-Year Dates and does not infer or append the current year.
_Avoid_: incomplete date, implicit current-year date

**Adjacent No-Year Date Text**:
Two numeric No-Year Date candidates separated only by whitespace. This text is too ambiguous to normalize automatically; a visible separator or word between the candidates makes them separate dates.
_Avoid_: date range, date list

**Date Boundary**:
A text boundary that allows the Date Normalizer to treat neighboring characters as outside a date token. Starts, ends, whitespace including newlines, Markdown emphasis wrappers, and selected surrounding punctuation are Date Boundaries; letters, digits, underscores inside words, and structural characters inside versions, IPs, times, or units are not. For `DD.MM.` No-Year Dates, the final dot is part of the date token, but may be preserved as sentence punctuation when the date ends a sentence or line.
_Avoid_: normal punctuation

**Date Locale**:
The locale selected for the Date Normalizer to choose default Date Input Formats and language-specific spoken date rendering. It may default from Output Language or Number Spellout Language, but remains separate because date ordering is regional while number spellout is primarily language-specific.
_Avoid_: output language, number spellout language

**Date Renderer**:
The Date Normalizer strategy that turns a validated date into spoken text for a Date Locale. German and English may use curated Date Renderers; other languages require an explicit Numeric Fallback Date Renderer until they are curated.
_Avoid_: date format, number normalizer

**German Date Context**:
The immediate left-side word context a German Date Renderer may use to choose the spoken ordinal ending for a date. It is limited to clear article and preposition patterns such as `der`, `den`, `am`, or `ab`, and does not attempt full sentence parsing.
_Avoid_: NLP date grammar, automatic German parser

**Numeric Fallback Date Renderer**:
A Date Renderer that speaks day, month, and optional year as numeric parts without claiming language-specific natural date grammar. It is explicit and preview-driven for non-curated languages.
_Avoid_: generic date renderer, automatic locale support

**Normalization Preview**:
A configuration-time view of the text a Proxy TTS Entity would send to its Target TTS Entity after applying Replacement Rules, Markdown Cleanup, the Emoji Normalizer, the Date Normalizer, and the Number Normalizer. It uses unsaved form values when available, does not synthesize audio, and does not change saved configuration.
_Avoid_: TTS preview, Assist preview, test playback

**Rule Preset**:
A future package of suggested Replacement Rules for a common language or use case. Rule Presets are not part of the MVP.
_Avoid_: built-in grammar

**Provider Control Tag**:
Inline markup in TTS input that a Target TTS Entity may interpret as voice, pronunciation, pause, or delivery control. Provider Control Tags are preserved by the Proxy TTS Entity and are not changed by Replacement Rules, Emoji Normalizer, Date Normalizer, or Number Normalizer. Markdown Cleanup may rewrite explicit Markdown constructs, but isolated Provider Control Tags stay opaque.
_Avoid_: replacement target

**Minimal Lookahead Buffer Length**:
The configurable number of trailing characters a Proxy TTS Entity keeps unflushed while normalizing streamed text, so replacements can still match text that arrives across chunk boundaries.
_Avoid_: chunk size

**Maximal Buffer Limit**:
The configurable maximum pending text size a Proxy TTS Entity allows before flushing at a safe whitespace boundary while keeping the Minimal Lookahead Buffer Length.
_Avoid_: timeout
