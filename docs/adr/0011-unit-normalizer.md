# Unit Normalizer

Unit normalization is implemented as a separate optional normalizer that runs after Date Normalizer and before Number Normalizer. It detects eligible numeric text followed by curated unit symbols or technical abbreviations, replaces only the unit with spoken text, and leaves the number for Number Normalizer.

German and English use curated unit forms with limited singular/plural handling. Other Unit Locales use a conservative English fallback rather than pretending to provide full language-specific grammar. Temperature scale wording is fixed by Unit Locale: German treats Celsius as the everyday scale, `en-US` treats Fahrenheit as everyday, and other English locales treat Celsius as everyday; the other scale is spoken explicitly.

The MVP includes common smart-home units such as `°C`, `°F`, `%`, `W`, `kW`, `Wh`, `kWh`, `V`, `A`, `mA`, `km`, `km/h`, `kmh`, `m/s`, `hPa`, `mbar`, `bar`, `lx`, `lm`, `B`, `KB`, `MB`, `GB`, and `Mbit/s`. It intentionally excludes bare `m` because `5m` is too easily confused with minutes in Assist responses.
