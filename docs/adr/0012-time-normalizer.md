# Time Normalizer

Time normalization is implemented as a separate optional normalizer that runs after Date Normalizer and before Unit Normalizer. It handles clock times, clock-time ranges, and opt-in durations before the Number Normalizer sees the remaining numeric text.

German and English use curated renderers. The MVP does not provide a generic fallback for other languages because time wording needs language-specific rules such as `ein Uhr`, `oh five`, and singular duration units.

Clock Time Detection and Time Range Detection are enabled by default inside the normalizer. Duration Detection is opt-in because bare two-part colon text such as `1:30` is treated as a clock time; elapsed durations require an `h` suffix or three-part `HH:MM:SS` shape.

The normalizer skips structured tokens such as IPs, identifiers, ratios, invalid clock values, and clock times with seconds. Provider Control Tags remain opaque.
