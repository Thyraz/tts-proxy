# TTS Proxy

TTS Proxy is a Home Assistant custom integration that exposes a TTS entity, allows replacements in the text, and forwards it to another TTS entity.

The main use case is adjusting text from an LLM Assist response before it is sent to the TTS service. This is often needed to improve audio output for dates, numbers, units, and similar text.

It can apply replacements based on:

- user-defined rules using string literals or regular expressions
- Markdown cleanup
- text cleanup
- emoji detection
- date detection
- time detection
- unit detection
- number detection

This happens before the target TTS service receives the text.

Date detection can also spell standalone years within a configured range.
Some sanity checks are done, to identify numbers that are clearly no years (like 1920 Watts).

German date output also uses a few simple context rules for endings like `dreizehnte` vs `dreizehnter`.

Time detection can spell German and English clock times, time ranges, and optional durations such as `13:40 Uhr`, `2:30pm-3:30pm`, or `01:30:00`.

Unit detection covers common smart-home symbols like `°C`, `%`, `W`, `kWh`, `km/h`, `kmh`, `hPa`, and `Mbit/s`. German and English have curated wording; other locales use a conservative fallback.

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
5. Add replacement rules, optionally name them, and enable Markdown cleanup, text cleanup, emoji handling, date detection, time detection, unit detection, or number detection if needed.

Use the preview area in the options dialog to test the processed text before saving.

After setup, select **TTS Proxy** anywhere Home Assistant lets you choose a TTS provider.

## Example

- LLM response: `Tomorrow 03/12/2026 the outside temperature will be 25°C.`
- Possible TTS Proxy output: `Tomorrow March twelfth, twenty twenty-six the outside temperature will be twenty-five degrees.`
