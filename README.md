# TTS Proxy

TTS Proxy is a Home Assistant custom integration that exposes a TTS entity, processes text, and forwards it to another TTS entity.

The main use case is adjusting text from an LLM Assist response before it is sent to the TTS service. This is often needed to improve audio output for dates, numbers, units, and similar text.

It can process text using:

- user-defined rules using string literals or regular expressions
- text insertion at message, line, or sentence starts
- replacement and insertion rules activated by Home Assistant entity states
- Markdown cleanup
- text cleanup
- emoji detection
- date detection
- time detection
- unit detection
- number detection

This happens before the target TTS service receives the text.

TTS Proxy can adapt its text processing to Home Assistant entity states. Choose an entity and an activating state for a rule to control when its replacements or insertions apply.

Date detection can also spell standalone years within a configured range.
Some sanity checks are done, to identify numbers that are clearly no years (like 1920 Watts).

German date output also uses a few simple context rules for endings like `dreizehnte` vs `dreizehnter`.

Time detection can spell German and English clock times, time ranges, and optional durations such as `13:40 Uhr`, `2:30pm-3:30pm`, or `01:30:00`.

Unit detection covers common smart-home symbols like `°C`, `%`, `W`, `kWh`, `km/h`, `kmh`, `hPa`, and `Mbit/s`. German and English have curated wording; other locales use a conservative fallback.

Number detection can optionally handle grouped values such as `20 222,2 kWh` or `20,222.2 kWh`.
For German number spellout, it can also separate number word parts, for example `2395` -> `zwei-tausend-drei-hundert-fünf-und-neunzig`.

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
5. Add Text Processing Rules, optionally name them, and enable Markdown cleanup, text cleanup, emoji handling, date detection, time detection, unit detection, or number detection if needed.

Use the preview area in the options dialog to test the processed text before saving.

After setup, select **TTS Proxy** anywhere Home Assistant lets you choose a TTS provider.

### React to Home Assistant entity states

In **Text Processing Rules**, add an optional entity/state condition to a literal replacement, regex replacement, or text insertion rule. Each rule selects one entity and applies only when that entity has the configured state.

| Field | Purpose |
| --- | --- |
| Name | Optional label for the rule |
| Mode | Literal replacement, regex replacement, or text insertion |
| Find | Text or regex to replace; leave empty for insertion rules |
| Replacement / insertion text | Literal text to insert, or the replacement text |
| Insertion placements | Message start, line starts, sentence starts, or a combination |
| Condition entity | Any Home Assistant entity whose state should control the rule |
| Activating state | Exact raw entity state, such as `on`, `off`, or `below_horizon` |
| Maximum report age (seconds, optional) | Positive whole seconds; leave empty for no age limit |

Insertion text can contain ordinary text or control tags supported by your Target TTS Entity. It is inserted verbatim, so include any spaces or other separators you want.

When a condition does not match, only that rule is skipped; other rules and normalizers continue. Leave the condition fields empty to make a rule unconditional. State matching uses raw HA values rather than translated display labels.

Each proxy can have several independently conditioned rules. Conditions are captured when the first nonempty response text arrives, or before processing a complete response. Home Assistant can prepare a TTS stream before speech recognition, but that preparation does not capture conditions. A sensor updated before the first response text therefore affects the current reply. Later state changes do not switch rules midway. Missing entities skip their affected rules; `unknown` and `unavailable` match only when explicitly configured as the activating state. Preview uses unsaved settings and current entity states.

The optional maximum report age uses HA's `last_reported` timestamp. A repeated report with the same state counts as fresh if the source integration writes it to HA. If the integration reports only state changes, unchanged values do not refresh that timestamp. An older report skips only its affected rule. Choose a limit long enough to cover any processing before the text reaches TTS. The limit is checked once, so it does not stop insertions or replacements midway through a response. Preview checks report age too.

Each rule is evaluated independently. To combine several entity states into one condition, create a [Home Assistant template binary sensor](https://www.home-assistant.io/integrations/template/#state-based-template-entities) and use that helper as the rule's condition entity with activating state `on`.

If any enabled rule has an entity/state condition, repeated identical responses require fresh synthesis to avoid reusing audio generated under earlier conditions. This also applies when the condition does not match. Home Assistant can still store the audio; with file caching enabled, complete responses can accumulate distinct persistent files until you clear the HA TTS cache. Proxies without enabled conditioned rules retain cache reuse.

Placements can be combined. Overlapping starts get one insertion, blank lines get none, and an exact existing copy of the insertion text at the same placement is skipped. Text from active insertion rules appears in configuration order, with existing provider tags preserved.

Replacement rules run before Markdown cleanup. Insertions run after Markdown cleanup and before line-break cleanup and the other normalizers. Ordering applies separately within each phase, so replacement rules do not rewrite inserted text.

Sentence starts use a simple `.`, `!`, or `?` followed by whitespace/newlines, allowing closing quotes in between. This can also recognize abbreviations or dots within spaced dates as boundaries; inserted tags can prevent those spaced dates from being normalized. Use preview to check your text, or select message/line starts when sentence insertion is unsuitable.

## Example

- LLM response: `Tomorrow 03/12/2026 the outside temperature will be 25°C.`
- Possible TTS Proxy output: `Tomorrow March twelfth, twenty twenty-six the outside temperature will be twenty-five degrees.`

## Tests

Run the pure normalization and configuration tests with `python3 -m unittest discover -s tests -q`.
To also run the actual Home Assistant TTS-manager, cache, and preview tests, install `tests/requirements.txt` into an isolated environment and run the same command with that environment's Python. The requirements target Home Assistant 2026.9.4 and Python 3.14.
