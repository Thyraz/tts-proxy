# TTS Proxy

TTS Proxy is a Home Assistant custom integration that exposes a TTS entity, normalizes the text, and forwards it to another TTS entity.

It can apply replacement rules, date normalization, and number spellout before the final TTS service receives the text.

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
3. Choose the final TTS entity that should receive the processed text.
4. Select the output language.
5. Add replacement rules and enable date or number normalization if needed.

Use the preview field in the options flow to check the transformed text before saving.

After setup, select **TTS Proxy** anywhere Home Assistant lets you choose a TTS provider.
