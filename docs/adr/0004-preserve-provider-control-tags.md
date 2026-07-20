# Preserve Provider Control Tags

The Proxy TTS Entity preserves Provider Control Tags as opaque input segments and applies Replacement Rules only to normal speech text around them. In the MVP, every `<...>` and `[...]` span is treated as a Provider Control Tag rather than trying to detect provider-specific semantics. This avoids corrupting SSML/XML-like markup and provider-specific controls such as ElevenLabs square-bracket audio tags, while keeping the MVP focused on text normalization rather than markup parsing or generation.
