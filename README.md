# TTS Proxy

TTS Proxy is a Home Assistant custom integration that exposes a TTS entity, allows replacements in the text, and forwards it to another TTS entity.

The main use case is adjusting text from an LLM Assist response before it is sent to the TTS service. This is often needed to improve audio output for dates, numbers, units, and similar text.

It can apply replacements based on:

- user-defined rules using string literals or regular expressions
- date detection
- number detection

This happens before the target TTS service receives the text.

TTS Proxy supports streaming and non-streaming TTS integrations.

## Install with HACS

1. Open HACS.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/Thyraz/tts-proxy`.
4. Select **Integration** as the category.
5. Install **TTS Proxy**.
6. Restart Home Assistant.

## Manual Install

Copy `custom_components/tts_proxy` into your Home Assistant config folder:

```text
<config>/custom_components/tts_proxy
```

Then restart Home Assistant.

## Configuration

1. Go to **Settings** -> **Devices & services**.
2. Add the **TTS Proxy** integration.
3. Choose the target TTS entity that should receive the processed text.
4. Select the output language.
5. Add replacement rules, optionally name them, and enable date or number detection if needed.

Use the preview area in the options dialog to test the processed text before saving.

After setup, select **TTS Proxy** anywhere Home Assistant lets you choose a TTS provider.

## Example

- LLM response: `Tomorrow 03/12/2026 the outside temperature will be 25°C.`
- Possible TTS Proxy output: `Tomorrow March twelfth, twenty twenty-six the outside temperature will be twenty-five degrees.`
