# Grouped Number Detection

Grouped Number Detection is an optional Number Normalizer setting shared by the Number Normalizer and the Unit Normalizer. It is disabled by default.

When enabled, valid thousands-grouped numbers such as `20 222,2`, `20 222,2`, `20.222,2`, `20,222.2`, `1.234.567`, and `1,234,567` are treated as one numeric token. The detected token is normalized to a plain numeric value before spellout, while Unit Normalizer still leaves the written number text in place for the later Number Normalizer.

For ambiguous single-separator tokens such as `1.342` or `1,342`, the parser uses the best available locale hint: Number Spellout Language, then Unit Locale for Unit Normalizer matching, then Output Language. German treats `1.342` as grouped and `1,342` as decimal. English treats `1,342` as grouped and `1.342` as decimal. Without a useful hint, the existing decimal interpretation wins.

Valid IPv4 address text always wins over grouped-number interpretation and is left unchanged.
