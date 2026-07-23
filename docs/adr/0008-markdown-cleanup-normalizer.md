# Markdown Cleanup Normalizer

Markdown Cleanup is implemented as a separate optional normalizer that runs after Replacement Rules and before Date Normalizer and Number Normalizer. It is disabled by default, its options section is collapsed by default, and each cleanup behavior has its own option so users can keep Markdown syntax that their Target TTS Entity already handles well.

The MVP uses conservative text rules instead of a full CommonMark or GitHub Flavored Markdown parser. It strips or simplifies common LLM output syntax such as emphasis, headings, list markers, Markdown links, images, inline code backticks, blockquotes, divider lines, strikethrough markers, and table separators. Plain URL removal and fenced code block removal are opt-in because those can remove information the user may still want spoken.

Table handling is cleanup-only: separator lines are removed and cell separators become punctuation. The proxy does not announce table structure, infer headers, or render rows with column labels because that would require language-specific phrasing and semantic interpretation.

This keeps Markdown cleanup streaming-compatible and preview-driven while avoiding a broad Markdown-to-speech renderer in the MVP.
