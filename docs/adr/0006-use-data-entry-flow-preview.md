# Use Data Entry Flow Preview

Normalization Preview will use Home Assistant's Data Entry Flow preview mechanism on the configuration form instead of a separate preview wizard or custom frontend pane. This keeps preview tied to unsaved form values, avoids saving configuration just to test it, and avoids turning the integration into a custom frontend project.

**Consequences**

The preview may look like Home Assistant's generic preview component rather than the dedicated Voice Assistant preview pane. The tradeoff is acceptable because it gives the key workflow: edit normalization settings, preview the transformed text, then save or cancel.

Current Home Assistant frontend code only has dedicated preview renderers for selected built-in preview modules. Custom preview names fall back to the generic preview component, so TTS Proxy keeps the preview payload intentionally simple. Successful preview output is sent as a generic sensor-like entity state; websocket result errors remain validation errors.
