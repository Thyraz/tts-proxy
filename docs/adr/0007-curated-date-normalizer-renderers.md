# Curated Date Normalizer Renderers

Date normalization is implemented as a separate optional normalizer that runs after Replacement Rules and before the Number Normalizer. The MVP uses curated German and English renderers with month-name output and explicit Date Input Formats, while other languages fall back to numeric spoken date parts.

**Consequences**

The Date Normalizer does not use broad natural-language date parsing and does not infer Home Assistant frontend user date formats. `unicode-rbnf` remains a candidate future spellout backend, but the MVP avoids adding it as a dependency because a renderer layer is still required to choose language-specific grammatical forms and the package has different coverage from `num2words`.
