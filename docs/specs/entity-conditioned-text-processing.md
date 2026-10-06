# Entity-Conditioned Text Processing

Agreed first-version feature design from the grill-with-docs session, confirmed and implemented on 2026-10-05. Architectural rationale is recorded in [ADR-0014](../adr/0014-entity-conditioned-text-processing-rules.md); domain terms are defined in [CONTEXT.md](../../CONTEXT.md).

## Timing correction implemented on 2026-10-06

The first implementation captures conditions when Home Assistant prepares a TTS stream. Assist prepares that stream before speech recognition, so a sensor updated at the end of the user's speech can leave responses one interaction behind. An actual HA-manager reproduction with streamed input produced inactive, active, inactive rule results for current sensor states on, off, off; moving the snapshot later corrected that sequence in a diagnostic probe.

The agreed correction is to capture the Condition Snapshot on the first nonempty streamed response text, or immediately before processing a complete response, and retain it for the entire message, including any fallback to one-shot synthesis. Empty chunks do not capture conditions. No fixed delay or sensor-specific handling is needed.

An enabled rule with an Entity State Condition requires a unique private request marker in the proxy's default TTS options. It prevents reuse of previous HA audio even though conditions are not known when the stream is prepared. The marker is removed before delegation and contains no entity state. Proxies without enabled conditioned rules retain stable configuration-based cache keys. A diagnostic probe confirmed that moving condition evaluation alone can reuse incorrect audio on the one-shot cache path.

The marker prevents reuse between requests; it does not disable HA cache storage. With file caching enabled, complete responses can create distinct persistent files even for repeated text. The first fix accepts and documents HA's existing storage behavior; a proxy-owned cache and file-cleanup policy are deferred.

## Confirmed scope

- Each Proxy TTS Entity owns its own configuration and can have multiple Text Processing Rules using different entities and activating states.
- Text Processing Rules share the existing rule configuration list. Entity State Conditions are optional on both literal/regex Replacement Rules and Text Insertion Rules.
- In the first version, each rule has at most one condition: exact equality between one selected entity's state and its configured activating state. Combined conditions are deferred; multiple matching rules can apply together.
- A condition may additionally set `condition_max_age_seconds` to a positive whole number. Blank or absent means no age limit. The rule activates only if the state matches and its latest HA state report is no older than the limit, inclusive at the boundary. HA's `last_reported` is used so identical repeated reports count. Missing report timestamps or future timestamps cannot satisfy an age-limited condition.
- Each rule still selects one entity. Multiple speakers can share one Proxy TTS Entity by using separate age-limited rules. No newest-entity selection or source-dependent routing is added. If every such rule is inactive, those rules insert nothing; if several insert the same text at a placement, existing duplicate suppression emits one copy.
- At a shared insertion position, text from active rules appears in configuration order. For example, `Notice: ` followed by `Reminder: ` produces `Notice: Reminder: Hello.`. The Target TTS Entity interprets any control tags in the combined text; the proxy does not resolve provider-specific tag conflicts.
- A missing entity or a state mismatch skips only the affected rule; remaining processing and speech continue. `unknown` and `unavailable` are ordinary state values for equality matching and can activate a rule only if explicitly configured as its expected state.
- Text Insertion Rules accept arbitrary literal text, including Provider Control Tags and ordinary speech text. They do not recognize specific delivery styles.
- Insertion text is used verbatim, preserving leading and trailing whitespace without automatically adding a separator. Users can include a trailing space, for example `Notice: ` or `Attention: `.
- Conditions are evaluated once on the first nonempty streamed response chunk, or before processing a complete response. Empty streamed chunks do not capture conditions. The resulting Condition Snapshot applies throughout the message, including fallback to one-shot synthesis; stream preparation does not read conditions.
- Replacement Rules keep their existing processing position before Markdown Cleanup. Text Insertion Rules run after Markdown Cleanup and before Text Line Break Cleanup; ordering applies independently within each phase.
- One Text Insertion Rule may select message start, line starts, sentence starts, or several of these placements. It inserts once where placements overlap and skips empty lines.
- An insertion is skipped if an exact existing copy of its configured text is already present at that placement. Different Provider Control Tags are preserved without interpreting their meanings.
- Sentence insertion uses the first speech text and text after `.`, `!`, or `?` followed by whitespace or a newline, allowing intervening closing quotes. Abbreviations may produce extra insertions; language-aware sentence detection is deferred until real-world use demonstrates a need.
- Normalization Preview uses unsaved form values and the current Home Assistant entity states, evaluated once per preview run. Simulated preview states are deferred.

## Optional age limits for multiple speakers

Create one rule per speaker, with its own entity, activating state `on`, the same insertion text, and an optional maximum age such as 30 seconds. Age measures the latest report received by HA, not the latest transition from `off` to `on`; a new report with unchanged state refreshes freshness. The same option also applies to conditioned literal/regex replacements.

The integration must report the entity at each request for this to identify recent commands. Periodic reports unrelated to commands can keep an old value fresh. The chosen limit needs to cover the time from sensor reporting through speech recognition and agent processing until the first response text. Once captured, a matching rule remains active through the entire response, even if the limit is crossed while streaming or collecting fallback input.

This is a per-rule freshness heuristic. A recent `on` from another speaker can still match while a newer `off` arrives from the current speaker. The user accepts this limitation for rare closely spaced or overlapping requests; precise request-to-speaker routing is deferred.

For integrations that suppress unchanged reports, an age limit cannot identify repeated activity with the same value. Users can compose an external HA template helper combining an activity entity with the condition entity and target that helper with no age limit. The [README configuration guide](../../README.md#react-to-home-assistant-entity-states) describes this general composition mechanism. Such helpers do not bind a TTS response to its source; request-to-source routing remains deferred.

## Configuration example

An insertion rule named `State-dependent notice` could use entity `input_boolean.tts_notices`, activating state `on`, literal insertion text `Notice: `, and message-start placement. The entity ID and text are examples; users choose the entity, state, and text their setup requires.

With the condition matching, input `Done. Anything else?` becomes `Notice: Done. Anything else?`. With the condition not matching, this rule leaves the input unchanged. A second insertion rule can independently use another entity, state, and text.

## Cache integration

Cached audio must respect the Condition Snapshot, including repeated identical input under different entity states. Home Assistant's one-shot cache lookup precedes proxy synthesis, so reading the conditions later requires preventing cache reuse for enabled conditioned rules.

The integration supplies a stable `_tts_proxy_processing_fingerprint` and, when any enabled rule has an Entity State Condition, a fresh UUID in `_tts_proxy_request_id` through dynamic `default_options`. Home Assistant copies default options during stream preparation and includes options in the one-shot cache key ([option processing](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/tts/__init__.py#L808-L848), [cache lookup](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/components/tts/__init__.py#L938-L995)). No condition is evaluated in `default_options`. The request marker is used even if the eventual condition does not match or the entity is missing. Both private options are excluded from supported call options and removed before delegation to the Target TTS Entity.

Proxies with only unconditional or disabled conditioned rules retain cache reuse and configuration-based invalidation. Enabled conditioned rules cause fresh synthesis between requests. HA still manages memory and disk storage, so file caching can accumulate distinct files for identical conditioned responses until the HA cache is cleared. Actual Home Assistant 2026.9.4 manager tests verify these paths, delayed first text, fallback, concurrent requests, and cancellation before text.

## Acceptance scenarios

- Existing saved literal/regex rules without conditions keep their current behavior.
- Separate rules can use different entities; all matching rules apply, and missing or mismatched entities skip only their own rules.
- An old matching report skips an age-limited rule; a fresh identical report activates it without requiring a state transition. Without an age limit, old matching reports retain their previous behavior.
- Different age limits on rules referencing the same entity are evaluated at one snapshot time from one copied state report. Age-limited replacements and unsaved preview apply the same freshness criteria as insertions.
- A sensor changed after stream preparation but before the first response text affects the current reply. Matching, nonmatching, nonmatching sensor states produce active, inactive, inactive rule results, including repeated identical response text.
- State changes after the first response text do not change the selected rules. A later response takes a new snapshot. Waiting or empty streams do not read conditions, and cancellation while waiting for first text closes the source without synthesizing audio.
- Message-start insertion occurs once for the logical message. Line and sentence insertion positions remain consistent across different input chunk and buffer-flush boundaries.
- Selecting several placements produces one insertion at overlapping positions; empty and whitespace-only lines receive no insertion.
- Insertion text preserves whitespace, and texts at shared positions appear in rule order.
- An existing exact copy at a placement suppresses that insertion. Existing Provider Control Tags remain opaque and intact, including when they arrive across chunks.
- Markdown list cleanup followed by line insertion can produce `Notice: First item\nNotice: Second item`; optional line-break cleanup can then join the lines while preserving both prefixes.
- Sentence examples cover `.`, `!`, `?`, newlines after punctuation, closing quotes, and the accepted abbreviation limitation. The simple heuristic also splits dots in spaced dates, which can prevent those dates from being normalized; compact dates are covered by an interaction test.
- Identical original text cannot reuse earlier HA audio when any enabled rule has a condition, including with disk caching enabled. Unconditional rules and disabled conditioned rules retain cache reuse; a configuration change invalidates their previous audio.
- Preview evaluates the unsaved rules against one snapshot of current entity states, without saving settings or generating speech.

## Validation

- `python3 -m unittest discover -s tests -q`: 184 pure tests pass; 18 HA runtime tests are skipped when Home Assistant is not installed.
- The same command with `tests/requirements.txt` installed: all 202 tests pass, including the actual HA manager, cache, selector, and preview paths.
- Changed production modules and new test modules pass Ruff lint and formatting checks; `git diff --check` passes.

The test environment echoes processed text as audio bytes through real HA entity wrappers and cache management. It does not test a particular provider's interpretation of speech tags or play audio on a live Assist satellite.
