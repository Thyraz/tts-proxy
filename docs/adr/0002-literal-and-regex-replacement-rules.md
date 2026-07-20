# Literal and Regex Replacement Rules

Replacement Rules use plain literal string replacement or Python-style regular expression substitution in the MVP. This keeps text normalization deterministic, compatible with streaming-safe buffering, and simple enough for Home Assistant's native config/options flow UI, while leaving room to add template-based rule modes later if their streaming and caching semantics are explicitly designed.
