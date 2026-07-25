# Text Cleanup Normalizer

Text Cleanup is implemented as a separate optional normalizer that runs after Markdown Cleanup and before Emoji Normalizer, Date Normalizer, Time Normalizer, Unit Normalizer, and Number Normalizer. It is not part of Markdown Cleanup because plain text can contain line breaks without being Markdown.

The MVP supports an opt-in line-break cleanup rule that replaces one or more Unix or Windows line breaks, including surrounding spaces and tabs, with a single space. Provider Control Tags remain protected.
