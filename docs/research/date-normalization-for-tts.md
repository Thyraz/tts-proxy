# Date Normalization for TTS

Research date: 2026-07-21

Question: how should TTS Proxy normalize date strings such as `14.09.2026` or `14.05.` into spoken text across multiple languages, without overfitting to German or to the current `num2words` library?

## Short Answer

There is no single Python library, CLDR API, or Home Assistant API that turns arbitrary localized date strings into natural spoken dates for all languages.

The hard part is not only parsing `14.09.2026` as a date. The hard part is rendering the date in the grammatical form a language expects in that sentence. German `vierzehnte` vs. `vierzehnter` is an example of a general problem: ordinal words often depend on gender, case, number, and sentence context. CLDR explicitly warns that rule-based number spellout data is insufficient without additional software that chooses the right grammatical rule from context ([CLDR LDML Numbers, Rule-Based Number Formatting](https://unicode.org/reports/tr35/tr35-numbers.html#Rule-Based_Number_Formatting)).

Recommended approach for this integration:

```text
Replacement Rules
-> Date Normalizer
-> Number Normalizer
```

The Date Normalizer should be a separate optional normalizer with conservative format detection, explicit input-format settings, and a renderer registry. It should not rely on Home Assistant's frontend user date format, because the backend TTS entity only receives text/language/options, while frontend date formatting uses per-user profile settings ([HA TTS Entity docs](https://developers.home-assistant.io/docs/core/entity/tts/), [HA frontend data docs](https://developers.home-assistant.io/docs/frontend/data/)).

For the first useful implementation, keep `num2words` for cardinal/year spellout, add a small date renderer layer, and implement a German renderer explicitly instead of accepting `num2words`' default German ordinal form. `unicode-rbnf` is a promising alternative backend for CLDR-style rule sets, but should be treated as a candidate dependency, not an automatic replacement for `num2words`.

## Source Map

Primary/high-trust sources checked:

- Home Assistant developer docs:
  - [Text-to-speech entity](https://developers.home-assistant.io/docs/core/entity/tts/), last updated 2026-07-09.
  - [Frontend data](https://developers.home-assistant.io/docs/frontend/data/), last updated 2026-07-18.
- Unicode/CLDR/ICU:
  - [CLDR LDML Part 4: Dates](https://unicode.org/reports/tr35/tr35-dates.html), version 48.2.
  - [CLDR LDML Part 3: Numbers](https://unicode.org/reports/tr35/tr35-numbers.html), version 48.2.
  - [ICU RuleBasedNumberFormat user guide](https://unicode-org.github.io/icu/userguide/format_parse/numbers/rbnf.html).
  - [ICU4J RuleBasedNumberFormat API](https://unicode-org.github.io/icu-docs/apidoc/released/icu4j/com/ibm/icu/text/RuleBasedNumberFormat.html).
- Python libraries:
  - [Babel introduction](https://babel.pocoo.org/en/stable/intro.html).
  - [Babel date/time API](https://babel.pocoo.org/en/latest/api/dates.html).
  - [Babel number formatting docs](https://babel.pocoo.org/en/stable/numbers.html).
  - [Python `datetime` docs](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior).
  - [Python `locale` docs](https://docs.python.org/3/library/locale.html).
  - [`dateparser` docs](https://dateparser.readthedocs.io/en/stable/index.html) and [settings docs](https://dateparser.readthedocs.io/en/stable/settings.html).
  - [`dateutil.parser` docs](https://dateutil.readthedocs.io/en/2.8.2/parser.html).
  - [`parsedatetime` docs](https://bear.im/code/parsedatetime/docs/parsedatetime.Constants-class.html).
  - [`num2words` README](https://github.com/savoirfairelinux/num2words/blob/master/README.rst), [`num2words/__init__.py`](https://github.com/savoirfairelinux/num2words/blob/master/num2words/__init__.py), [`num2words/lang_DE.py`](https://github.com/savoirfairelinux/num2words/blob/master/num2words/lang_DE.py), and [`tests/test_de.py`](https://github.com/savoirfairelinux/num2words/blob/master/tests/test_de.py).
  - [`unicode-rbnf` PyPI page](https://pypi.org/project/unicode-rbnf/).

## Parsing Localized Dates

### Python stdlib

`datetime.strptime` is useful for exact configured formats and validation. It parses a string against one explicit format and raises when invalid. It is not a localized natural-language parser and does not solve month names across locales by itself ([Python datetime docs](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior)).

`locale` should not be used as the main solution. Python's locale support is process-wide, and the docs warn that changing locale is not thread-safe on most systems and affects the entire program ([Python locale docs](https://docs.python.org/3/library/locale.html)). That is a poor fit for Home Assistant's async runtime and multi-user frontend.

Implication: use `datetime.date(...)` or exact `strptime`-style parsing for numeric date tokens, but do not switch process locale.

### Babel

Babel provides a Python interface to CLDR locale data, including localized date formatting, parsing hints, date patterns, and month/day names ([Babel introduction](https://babel.pocoo.org/en/stable/intro.html), [Babel date/time API](https://babel.pocoo.org/en/latest/api/dates.html)).

Relevant APIs:

- `format_date(date, format=..., locale=...)` returns a localized written date such as German full/long forms ([Babel date/time API](https://babel.pocoo.org/en/latest/api/dates.html)).
- `parse_date(text, locale=..., format=...)` can parse explicit formats and otherwise uses ISO-8601 plus the locale date format as a field-order hint ([Babel date/time API](https://babel.pocoo.org/en/latest/api/dates.html#basic-parsing)).
- `get_month_names(width, context, locale)` returns CLDR month names, including `format` vs. `stand-alone` context ([Babel date/time API](https://babel.pocoo.org/en/latest/api/dates.html#data-access)).

Babel does not spell out numbers as words. Its number APIs format and parse localized decimal/currency/percent values; they do not provide full number spellout or date speech ([Babel number formatting docs](https://babel.pocoo.org/en/stable/numbers.html)).

Implication: Babel is useful for month names and localized written date patterns. It is not sufficient to produce `vierzehnter` or `fourteenth` by itself.

### dateparser

`dateparser` can parse human-readable dates in more than 200 language locales, supports language detection, explicit `languages`/`locales`, explicit `date_formats`, non-Gregorian calendars, and searching dates inside larger text ([dateparser docs](https://dateparser.readthedocs.io/en/stable/index.html)).

However, its own docs warn that broad parsing can produce false positives and recommend passing only valid date strings and known languages/locales to reduce that risk ([dateparser false positives](https://dateparser.readthedocs.io/en/stable/index.html#false-positives)). It also fills missing date parts from current/default context unless configured otherwise, and provides settings such as `STRICT_PARSING` and `REQUIRE_PARTS` to reject incomplete dates ([dateparser settings](https://dateparser.readthedocs.io/en/stable/settings.html#handling-incomplete-dates)).

Implication: do not run `dateparser.search_dates()` over arbitrary TTS text by default. It is too broad for a streaming normalizer. It may be useful later behind a strict opt-in mode for month-name input, but the first Date Normalizer should detect well-defined date tokens itself.

### dateutil and parsedatetime

`dateutil.parser` supports ambiguous numeric date ordering via `dayfirst` and `yearfirst`, and allows custom `parserinfo` subclasses for accepted words. Its default parser info is English-oriented (`MONTHS`, `WEEKDAYS`, suffixes like `st`, `nd`, `rd`, `th`) ([dateutil parser docs](https://dateutil.readthedocs.io/en/2.8.2/parser.html)).

`parsedatetime` is a natural-language date/time parser. Its docs show a small built-in locale set plus optional PyICU usage/fallback to `en_US` ([parsedatetime Constants docs](https://bear.im/code/parsedatetime/docs/parsedatetime.Constants-class.html)).

Implication: neither is a better primary parser for this integration than exact token detection plus `datetime.date` validation.

## Spelling Spoken Dates

### CLDR and ICU

CLDR date data is excellent for written formatting and localized month names. It distinguishes format vs. stand-alone month contexts. For example, the format month form is used with a day number, while the stand-alone form is for independent month display. CLDR also explicitly says these forms are not meant to determine sentence-level case such as a dative form after a preposition ([CLDR LDML Dates](https://unicode.org/reports/tr35/tr35-dates.html)).

ICU RuleBasedNumberFormat can spell out numbers and ordinals, and supports locale-specific predefined rule selectors such as spellout and ordinal where available ([ICU RBNF guide](https://unicode-org.github.io/icu/userguide/format_parse/numbers/rbnf.html), [ICU4J API](https://unicode-org.github.io/icu-docs/apidoc/released/icu4j/com/ibm/icu/text/RuleBasedNumberFormat.html)).

But CLDR's own number specification says RBNF data may miss grammatical forms and that choosing among available forms requires extra language-specific context ([CLDR LDML Numbers](https://unicode.org/reports/tr35/tr35-numbers.html#Rule-Based_Number_Formatting)).

Implication: CLDR/ICU is the right conceptual model, but still does not remove the need for a Date Normalizer renderer layer.

### num2words

`num2words` supports multiple languages and conversion types including `cardinal`, `ordinal`, `ordinal_num`, `year`, and `currency` ([num2words README](https://github.com/savoirfairelinux/num2words/blob/master/README.rst)). Its README explicitly notes that ordinal generation is buggy for some languages ([num2words README](https://github.com/savoirfairelinux/num2words/blob/master/README.rst)).

German source and tests confirm the current behavior:

- `num2words(14, to="ordinal", lang="de")` -> `vierzehnte`.
- `num2words(5, to="ordinal", lang="de")` -> `fünfte`.
- `num2words(2026, to="year", lang="de")` -> `zweitausendsechsundzwanzig`.

The German implementation appends a default ordinal ending and does not expose a German gender/case parameter ([German source](https://github.com/savoirfairelinux/num2words/blob/master/num2words/lang_DE.py), [German tests](https://github.com/savoirfairelinux/num2words/blob/master/tests/test_de.py)).

Some other `num2words` languages expose language-specific kwargs. For example, local inspection of version 0.5.14 showed Russian `to_ordinal(..., gender=..., case=...)` and Hebrew `to_ordinal(..., gender=...)`, while German does not have that API. Therefore the API is not uniform enough for a generic date renderer.

Implication: `num2words` is fine as a cardinal/year backend and generic fallback. It should not be the only abstraction for date speech.

### unicode-rbnf

`unicode-rbnf` is a pure Python implementation of CLDR rule-based number formatting. Its docs say it uses Unicode CLDR data, supports different formatting purposes, and exposes all texts by ruleset when a locale has multiple gender/case forms. Its docs also say not every RBNF feature is implemented ([unicode-rbnf PyPI](https://pypi.org/project/unicode-rbnf/)).

Local smoke test with `unicode-rbnf==2.4.0`:

```text
de 14 ordinal:
  text: vierzehnte
  spellout-ordinal-r: vierzehnter
  spellout-ordinal-n: vierzehnten
  spellout-ordinal-s: vierzehntes
  spellout-ordinal-m: vierzehntem

de 2026 year:
  zweitausendsechsundzwanzig
```

That is much closer to what we need for German short numeric dates. But the same smoke test also found missing rulesets for some languages where `num2words` has support, for example Polish and Ukrainian in this installed package. It also returned default `text` values that are not necessarily the date form we would want, so we would still need curated ruleset selection per language.

Implication: `unicode-rbnf` is a strong candidate for a future date spellout backend, especially because it exposes German `vierzehnter` directly. It should not replace `num2words` globally without a coverage comparison and fallback plan.

## Dates Without Year

German has common no-year dates such as `14.05.`. Other languages have similar date-month forms, but punctuation/order differs.

These must be treated as first-class date candidates, not as normal numeric text. If the Date Normalizer runs before the Number Normalizer, it can consume `14.05.` before the decimal normalizer sees `14.05`.

The risk is ambiguity:

- `14.05.` can mean a German date.
- `14.05` can mean a decimal number.
- `04/05` can be DMY or MDY.
- `1.2` can be a version, decimal, short date, or section number.

Recommended no-year handling:

- Support `DD.MM.` as a German/DMY-style no-year format, with the trailing dot required.
- Support `DD/MM` and `MM/DD` only when the user explicitly enables one order.
- Do not infer a missing year. Output only day/month.
- Validate day/month with `datetime.date(2000, month, day)` so `29.02.` can be accepted without choosing a real year.
- Do not support two-digit years initially.

## Ambiguous Formats

Automatic format guessing should stay conservative.

Recommended initial input formats:

- `YYYY-MM-DD`: safe and unambiguous.
- `DD.MM.YYYY`: safe for German and many European outputs when enabled.
- `DD.MM.`: no-year DMY, only with trailing dot and only when enabled.
- `DD/MM/YYYY`: only when DMY slash is enabled.
- `MM/DD/YYYY`: only when MDY slash is enabled.
- `DD/MM` or `MM/DD`: optional, but only one slash no-year order should be enabled at a time.

When both date parts are `<= 12`, slash dates are ambiguous. If the configured order is explicit, parse according to it. If no explicit order is configured, skip.

The normalizer should reject candidates that are embedded in structured tokens:

- IPs: `192.168.1.1`
- versions: `1.2.3`
- times/ranges: `12:30`, `12:30-13:00`
- IDs: `AB-2026-09-14`, `sensor_14.05.`
- decimals with units: `14.05°C`

The safest implementation is not a generic date parser. It is a token scanner with enabled-format regexes, numeric validation, and boundary checks.

## Home Assistant Constraints

The Proxy TTS Entity should not try to detect the Home Assistant user's date format.

Home Assistant frontend helpers localize entity state/attributes using user profile settings such as language, number format, date format, and timezone ([HA frontend data docs](https://developers.home-assistant.io/docs/frontend/data/)). The TTS entity backend API receives `message`, `language`, `options`, or a streaming request with `language`, `options`, and `message_gen`; it does not receive a frontend user profile date-format object ([HA TTS Entity docs](https://developers.home-assistant.io/docs/core/entity/tts/)).

Implication: date input formats should be configured per Proxy Configuration, just like Replacement Rules and Number Spellout Language.

## Recommended Design

### Domain model addition

Add a new optional **Date Normalizer**:

> A built-in normalizer that detects configured date string formats, validates them as calendar dates, and replaces them with spoken date text before the Number Normalizer runs.

It should be separate from Replacement Rules and Number Normalizer because it combines token classification, calendar validation, output style, and language-specific grammar.

### Pipeline

Use this order:

```text
Replacement Rules
-> Date Normalizer
-> Number Normalizer
```

This preserves the current model where user rules can prepare text before built-in normalization. It also prevents `14.09.2026` or `14.05.` from being partially consumed as ordinary numbers.

### Settings

Suggested MVP options:

```text
Enable Date Normalizer: off by default
Date Spellout Language: default to Number Spellout Language when available
Input Date Formats:
  - YYYY-MM-DD
  - DD.MM.YYYY
  - DD.MM.
  - DD/MM/YYYY
  - MM/DD/YYYY
  - DD/MM
  - MM/DD
Date Output Style:
  - numeric ordinal
  - numeric cardinal fallback
German Ordinal Form:
  - standalone short: vierzehnter fünfter
  - dative short: vierzehnten fünften
```

For the first German implementation, `numeric ordinal` with `German Ordinal Form = standalone short` would produce:

```text
14.09.2026 -> vierzehnter neunter zweitausendsechsundzwanzig
14.05.     -> vierzehnter fünfter
2026-09-14 -> vierzehnter neunter zweitausendsechsundzwanzig
```

For languages without a supported date renderer, use an explicit fallback:

```text
day cardinal + month cardinal + optional year
```

That is less natural, but it avoids silently producing wrong ordinal grammar. The preview UI is important here, because users can hear/check the exact transformed output.

### Renderer Strategy

Do not let the Date Normalizer call `num2words(..., to="ordinal")` blindly.

Use a small renderer registry:

```text
DateRenderer(language, style) -> spoken date parts
```

Initial renderers:

- `de`: custom German renderer.
  - Use `num2words(..., to="year")` for year.
  - For standalone numeric ordinals, either:
    - transform `num2words(..., to="ordinal")` from final `e` to `er`, or
    - use `unicode-rbnf` and select `spellout-ordinal-r`.
  - For dative numeric ordinals, final `e` to `en`, or `unicode-rbnf` `spellout-ordinal-n`.
- `generic`: use cardinal day/month/year or `num2words` ordinal only when a language is explicitly marked as acceptable.

Potential later renderers:

- `en`: month-name style may be more natural than numeric-month ordinal.
- `fr`: day usually cardinal except special cases like first day; month names likely better.
- `es`/`it`/`pt`: gendered ordinal forms exist; month names may avoid some numeric-month weirdness.
- `ru`/`uk`/`pl`: case/gender matters heavily. Use curated rules or keep cardinal fallback.

### Library Recommendation

Short term:

- Keep `num2words` for the existing Number Normalizer.
- Implement Date Normalizer with exact numeric date detection plus German renderer.
- Do not add `dateparser` for the MVP.
- Do not use Python `locale`.
- Add Babel only if we implement month-name output or localized month-name input.

Medium term:

- Evaluate `unicode-rbnf` as a date-rendering backend, not necessarily as the global number backend.
- If adopted, still keep `num2words` fallback because `unicode-rbnf` coverage differs.
- Add an internal adapter that can choose a named RBNF ruleset such as German `spellout-ordinal-r`, instead of using the package's default `text`.

Long term:

- Add month-name output using Babel month names.
- Add curated language renderers for the languages users actually test.
- Optionally add strict month-name input parsing using Babel month dictionaries, not broad natural-language searching.

## Direct Answers

1. What libraries can parse localized/user-formatted dates?

Babel can parse exact/localized written dates with CLDR format hints. `dateparser` can parse many localized natural-language date strings and search longer text, but it is too broad for default TTS preprocessing. `dateutil` and `parsedatetime` are not better default choices for multilingual HA TTS text.

2. What libraries can spell dates as spoken words?

No checked library spells complete spoken dates correctly across languages. ICU/CLDR RBNF and `unicode-rbnf` can spell numbers/ordinals. Babel can provide localized month names and date patterns. A Date Normalizer still needs a renderer layer that decides day/month/year grammar.

3. Does `num2words` ordinal support solve this?

No. It helps, but German `vierzehnte` vs. `vierzehnter` shows the problem. Some `num2words` languages have gender/case options, but the API is language-specific and not uniform. `num2words` is a useful backend, not the complete date solution.

4. How should dates without year be handled?

Support them explicitly as date formats, not as incomplete dates inferred by a parser. For German-style dates, support `DD.MM.` with a required trailing dot. Do not infer a year. Validate day/month and output only day/month.

5. Recommended design for TTS Proxy?

Add a separate Date Normalizer between Replacement Rules and Number Normalizer. Start conservative, user-configured, and preview-driven. Implement German well first, provide generic fallback for other languages, and keep the renderer interface open for `unicode-rbnf` or Babel month-name support later.
