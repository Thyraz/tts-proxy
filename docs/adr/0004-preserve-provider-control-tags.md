# Preserve Provider Control Tags

The Proxy TTS Entity preserves Provider Control Tags as opaque input segments for Replacement Rules, Date Normalizer, and Number Normalizer. XML-like `<...>` spans and isolated square-bracket spans such as `[whispers]` remain protected rather than trying to detect provider-specific semantics.

Markdown Cleanup is the narrow exception. It runs after Replacement Rules and before Date Normalizer and Number Normalizer so it can simplify explicit Markdown constructs such as `[label](https://example.com)`, `![alt](https://example.com/image.png)`, and task-list markers. Isolated square-bracket spans remain Provider Control Tags and are not stripped as generic Markdown.

This avoids corrupting SSML/XML-like markup and provider-specific controls such as ElevenLabs square-bracket audio tags, while still making common LLM Markdown safer for TTS services that speak formatting characters.
