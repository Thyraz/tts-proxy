"""Markdown cleanup for the TTS Proxy integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

from .const import (
    CONF_MARKDOWN_CLEANUP_ENABLED,
    CONF_MARKDOWN_REMOVE_CODE_BLOCKS,
    CONF_MARKDOWN_REMOVE_DIVIDER_LINES,
    CONF_MARKDOWN_REMOVE_PLAIN_URLS,
    CONF_MARKDOWN_STRIP_BLOCKQUOTES,
    CONF_MARKDOWN_STRIP_EMPHASIS,
    CONF_MARKDOWN_STRIP_HEADINGS,
    CONF_MARKDOWN_STRIP_IMAGES,
    CONF_MARKDOWN_STRIP_INLINE_CODE,
    CONF_MARKDOWN_STRIP_LINKS,
    CONF_MARKDOWN_STRIP_LIST_MARKERS,
    CONF_MARKDOWN_STRIP_STRIKETHROUGH,
    CONF_MARKDOWN_STRIP_TABLES,
)

_CODE_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_IMAGE_RE = re.compile(r"!\[([^\]\n]*)\]\(((?:https?://|mailto:)[^)\s]+)(?:\s+[^)]*)?\)")
_MARKDOWN_LINK_RE = re.compile(
    r"(?<!!)\[([^\]\n]+)\]\(((?:https?://|mailto:)[^)\s]+)(?:\s+[^)]*)?\)"
)
_PLAIN_URL_RE = re.compile(r"(?<!\]\()(?:(?:https?://|mailto:)\S+)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_STRIKETHROUGH_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_STRONG_ASTERISK_RE = re.compile(r"(?<!\*)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\*)")
_STRONG_UNDERSCORE_RE = re.compile(r"(?<!_)__(?=\S)(.+?)(?<=\S)__(?!_)")
_EM_ASTERISK_RE = re.compile(r"(?<!\*)\*(?=\S)(.+?)(?<=\S)\*(?!\*)")
_EM_UNDERSCORE_RE = re.compile(r"(?<![A-Za-z0-9_])_(?=\S)(.+?)(?<=\S)_(?![A-Za-z0-9_])")
_ATX_HEADING_RE = re.compile(r"^( {0,3})#{1,6}\s+(.+?)(?:\s+#+)?\s*$")
_SETEXT_HEADING_RE = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
_DIVIDER_LINE_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_BLOCKQUOTE_RE = re.compile(r"^ {0,3}> ?")
_TASK_LIST_RE = re.compile(r"^ {0,3}[-+*]\s+\[[ xX]\]\s+")
_UNORDERED_LIST_RE = re.compile(r"^ {0,3}[-+*]\s+")
_ORDERED_LIST_RE = re.compile(r"^ {0,3}\d{1,9}[.)]\s+")
_PROVIDER_CONTROL_TAG_RE = re.compile(r"(<[^>]*>|\[[^\]\n]*\])")
_LINK_TARGET_AFTER_LABEL_RE = re.compile(
    r"\(((?:https?://|mailto:)[^)\s]+)(?:\s+[^)]*)?\)"
)


@dataclass(frozen=True, slots=True)
class MarkdownCleanupNormalizer:
    """A configured Markdown Cleanup Normalizer."""

    enabled: bool = False
    strip_emphasis: bool = True
    strip_headings: bool = True
    strip_list_markers: bool = True
    strip_tables: bool = True
    strip_links: bool = True
    remove_plain_urls: bool = False
    strip_inline_code: bool = True
    remove_code_blocks: bool = False
    strip_blockquotes: bool = True
    remove_divider_lines: bool = True
    strip_strikethrough: bool = True
    strip_images: bool = True

    def normalize(self, text: str) -> str:
        """Remove configured Markdown syntax from text."""
        if not self.enabled or not text:
            return text

        text, protected_code_blocks = _extract_code_blocks(
            text,
            remove=self.remove_code_blocks,
        )
        text, protected_provider_tags = _extract_provider_control_tags(text)
        if self.remove_divider_lines:
            text = _remove_divider_lines(text)
        if self.strip_headings:
            text = _strip_headings(text)
        if self.strip_blockquotes:
            text = _strip_blockquotes(text)
        if self.strip_list_markers:
            text = _strip_list_markers(text)
        if self.strip_tables:
            text = _strip_tables(text)
        if self.strip_images:
            text = _strip_images(text)
        if self.strip_links:
            text = _strip_links(text)
        if self.remove_plain_urls:
            text = _remove_plain_urls(text)
        if self.strip_inline_code:
            text = _strip_inline_code(text)
        if self.strip_strikethrough:
            text = _STRIKETHROUGH_RE.sub(r"\1", text)
        if self.strip_emphasis:
            text = _strip_emphasis(text)
        text = _restore_protected_text(text, protected_provider_tags)
        return _restore_code_blocks(text, protected_code_blocks)


def parse_markdown_cleanup_normalizer(
    raw_config: Mapping[str, Any],
) -> MarkdownCleanupNormalizer:
    """Parse Markdown Cleanup Normalizer configuration."""
    return MarkdownCleanupNormalizer(
        enabled=bool(raw_config.get(CONF_MARKDOWN_CLEANUP_ENABLED, False)),
        strip_emphasis=bool(raw_config.get(CONF_MARKDOWN_STRIP_EMPHASIS, True)),
        strip_headings=bool(raw_config.get(CONF_MARKDOWN_STRIP_HEADINGS, True)),
        strip_list_markers=bool(raw_config.get(CONF_MARKDOWN_STRIP_LIST_MARKERS, True)),
        strip_tables=bool(raw_config.get(CONF_MARKDOWN_STRIP_TABLES, True)),
        strip_links=bool(raw_config.get(CONF_MARKDOWN_STRIP_LINKS, True)),
        remove_plain_urls=bool(raw_config.get(CONF_MARKDOWN_REMOVE_PLAIN_URLS, False)),
        strip_inline_code=bool(raw_config.get(CONF_MARKDOWN_STRIP_INLINE_CODE, True)),
        remove_code_blocks=bool(raw_config.get(CONF_MARKDOWN_REMOVE_CODE_BLOCKS, False)),
        strip_blockquotes=bool(raw_config.get(CONF_MARKDOWN_STRIP_BLOCKQUOTES, True)),
        remove_divider_lines=bool(
            raw_config.get(CONF_MARKDOWN_REMOVE_DIVIDER_LINES, True)
        ),
        strip_strikethrough=bool(
            raw_config.get(CONF_MARKDOWN_STRIP_STRIKETHROUGH, True)
        ),
        strip_images=bool(raw_config.get(CONF_MARKDOWN_STRIP_IMAGES, True)),
    )


def _extract_code_blocks(text: str, *, remove: bool) -> tuple[str, dict[str, str]]:
    """Remove or protect fenced code blocks."""
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    protected: dict[str, str] = {}
    index = 0
    block_index = 0

    while index < len(lines):
        match = _CODE_FENCE_RE.match(lines[index])
        if match is None:
            output.append(lines[index])
            index += 1
            continue

        fence = match.group(1)
        block_lines = [lines[index]]
        index += 1
        while index < len(lines):
            block_lines.append(lines[index])
            closing = _CODE_FENCE_RE.match(lines[index])
            if closing is not None and closing.group(1)[0] == fence[0]:
                index += 1
                break
            index += 1

        if remove:
            continue

        placeholder = f"\0TTS_PROXY_CODE_BLOCK_{block_index}\0"
        protected[placeholder] = "".join(block_lines)
        output.append(placeholder)
        block_index += 1

    return "".join(output), protected


def _restore_code_blocks(text: str, protected: Mapping[str, str]) -> str:
    """Restore protected fenced code blocks."""
    return _restore_protected_text(text, protected)


def _extract_provider_control_tags(text: str) -> tuple[str, dict[str, str]]:
    """Protect Provider Control Tags that are not Markdown constructs."""
    output: list[str] = []
    protected: dict[str, str] = {}
    cursor = 0

    for match in _PROVIDER_CONTROL_TAG_RE.finditer(text):
        control_tag = match.group(0)
        if control_tag.startswith("[") and not _is_provider_square_tag(text, match):
            continue

        output.append(text[cursor : match.start()])
        placeholder = f"\0TTS_PROXY_CONTROL_TAG_{len(protected)}\0"
        protected[placeholder] = control_tag
        output.append(placeholder)
        cursor = match.end()

    output.append(text[cursor:])
    return "".join(output), protected


def _is_provider_square_tag(text: str, match: re.Match[str]) -> bool:
    """Return if a square-bracket span should be protected as provider markup."""
    if _is_markdown_link_or_image_label(text, match):
        return False
    if _is_task_list_marker(text, match):
        return False
    return True


def _is_markdown_link_or_image_label(text: str, match: re.Match[str]) -> bool:
    """Return if a square-bracket span starts a supported Markdown link/image."""
    return _LINK_TARGET_AFTER_LABEL_RE.match(text, match.end()) is not None


def _is_task_list_marker(text: str, match: re.Match[str]) -> bool:
    """Return if a square-bracket span is a Markdown task-list marker."""
    if match.group(0).lower() not in ("[ ]", "[x]"):
        return False

    line_start = text.rfind("\n", 0, match.start()) + 1
    prefix = text[line_start : match.start()]
    return re.fullmatch(r" {0,3}[-+*]\s+", prefix) is not None


def _restore_protected_text(text: str, protected: Mapping[str, str]) -> str:
    """Restore protected text placeholders."""
    for placeholder, protected_text in protected.items():
        text = text.replace(placeholder, protected_text)
    return text


def _strip_tables(text: str) -> str:
    """Remove Markdown table separator rows and replace cell separators."""
    lines = text.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if _is_table_separator_line(line):
            if output and "|" in output[-1]:
                output[-1] = _table_row_to_text(output[-1])
            index += 1
            while index < len(lines) and "|" in lines[index].strip():
                output.append(_table_row_to_text(lines[index]))
                index += 1
            continue

        output.append(line)
        index += 1

    return "\n".join(output)


def _is_table_separator_line(line: str) -> bool:
    """Return if a line looks like a Markdown table separator."""
    stripped = line.strip()
    if "|" not in stripped or "-" not in stripped:
        return False
    return all(char in "|:- \t" for char in stripped)


def _table_row_to_text(line: str) -> str:
    """Return a speech-friendly table row."""
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    text = ". ".join(cell for cell in cells if cell)
    if text and text[-1] not in ".!?:;":
        text += "."
    return text


def _remove_divider_lines(text: str) -> str:
    """Remove Markdown divider lines."""
    return "\n".join(
        line for line in text.splitlines() if _DIVIDER_LINE_RE.match(line) is None
    )


def _strip_headings(text: str) -> str:
    """Remove Markdown heading markers."""
    lines = text.splitlines()
    output: list[str] = []
    for line in lines:
        if _SETEXT_HEADING_RE.match(line) is not None and output:
            continue
        output.append(_ATX_HEADING_RE.sub(r"\2", line))
    return "\n".join(output)


def _strip_blockquotes(text: str) -> str:
    """Remove Markdown blockquote markers."""
    return "\n".join(_BLOCKQUOTE_RE.sub("", line) for line in text.splitlines())


def _strip_list_markers(text: str) -> str:
    """Remove Markdown list markers."""
    stripped_lines: list[str] = []
    for line in text.splitlines():
        line = _TASK_LIST_RE.sub("", line)
        line = _UNORDERED_LIST_RE.sub("", line)
        line = _ORDERED_LIST_RE.sub("", line)
        stripped_lines.append(line)
    return "\n".join(stripped_lines)


def _strip_images(text: str) -> str:
    """Replace Markdown image syntax with alt text."""
    return _IMAGE_RE.sub(lambda match: match.group(1), text)


def _strip_links(text: str) -> str:
    """Replace Markdown links with visible link text."""
    return _MARKDOWN_LINK_RE.sub(lambda match: match.group(1), text)


def _remove_plain_urls(text: str) -> str:
    """Remove plain URLs."""
    return _PLAIN_URL_RE.sub("", text)


def _strip_inline_code(text: str) -> str:
    """Remove inline code backticks while keeping the code text."""
    return _INLINE_CODE_RE.sub(r"\1", text)


def _strip_emphasis(text: str) -> str:
    """Remove Markdown emphasis markers."""
    text = _STRONG_ASTERISK_RE.sub(r"\1", text)
    text = _STRONG_UNDERSCORE_RE.sub(r"\1", text)
    text = _EM_ASTERISK_RE.sub(r"\1", text)
    return _EM_UNDERSCORE_RE.sub(r"\1", text)
