# Curated Date Normalizer Renderers

Date normalization is implemented as a separate optional normalizer that runs after Replacement Rules and before the Number Normalizer. The MVP uses curated German and English renderers with month-name output and explicit Date Input Formats, while other languages fall back to numeric spoken date parts.

**Consequences**

The Date Normalizer does not use broad natural-language date parsing and does not infer Home Assistant frontend user date formats. Sloppy spaced numeric dates such as `23. 05. 2026` are separate Date Input Formats so users can disable them independently from compact numeric dates. Numeric No-Year Date candidates separated only by whitespace are left unchanged because they are too ambiguous without a visible separator or word. The German renderer may use deterministic immediate left-context rules for clear article and preposition patterns such as `der 14.05.`, `am 14.05.`, or `ab 14.05.`, but it does not attempt full sentence parsing. `unicode-rbnf` remains a candidate future spellout backend, but the MVP avoids adding it as a dependency because a renderer layer is still required to choose language-specific grammatical forms and the package has different coverage from `num2words`.
