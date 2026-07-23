# Emoji Normalizer

Emoji handling is implemented as a separate optional normalizer, not as part of Markdown Cleanup. Emoji are Unicode text rather than Markdown syntax, and users need a distinct choice between removing emoji and speaking emoji names.

The Emoji Normalizer runs after Markdown Cleanup and before Date Normalizer and Number Normalizer. It preserves Provider Control Tags as opaque text. Spellout uses the selected Emoji Language, falls back to English when a localized name is missing, and leaves unknown emoji unchanged. Spoken emoji names are separated from surrounding text with commas. Remove mode deletes emoji without adding punctuation.

The integration depends on the `emoji` package, pinned in `manifest.json`, instead of maintaining custom Unicode ranges or regexes. The package handles multi-codepoint emoji sequences such as flags, modifiers, and joined emoji more reliably than hand-written matching. Non-English emoji language data is loaded before replacement so callback metadata contains the selected language instead of falling back to English.
