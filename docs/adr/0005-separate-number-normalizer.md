# Separate Number Normalizer

Number spellout is implemented as an optional normalizer that runs after Replacement Rules instead of as another Replacement Rule mode. The Number Normalizer uses an explicit Number Spellout Language from the supported `num2words` languages and converts simple integers, leading-zero integers, and one-separator decimals. It can optionally treat valid thousands-grouped numbers as one numeric token. Decimal formatting zeroes are removed before spellout, while leading-zero integers are spoken digit by digit so the written zeroes remain audible. Structured numeric tokens such as times, dates, IP addresses, versions, and alphanumeric identifiers are skipped unless an earlier normalizer or Replacement Rule first turns them into plain speech text.

**Consequences**

Replacement Rules remain the user-controlled preparation phase for ambiguous formats outside the dedicated normalizers. The built-in Number Normalizer can stay conservative and language-focused without guessing every higher-level numeric structure.
