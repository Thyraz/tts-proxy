"""Stateful, tag-preserving insertion at logical message boundaries."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .rules import InsertionPlacement, RuleMode, TextProcessingRule

_CONTROL_TAG_RE = re.compile(r"(<[^>]*>|\[[^\]]*\])")
_CLOSING_QUOTES = "\"'’”»"


class TextInsertionProcessor:
    """Carry boundary and duplicate-prefix lookahead across stream flushes.

    Only source text advances boundary state: inserted text cannot create more
    insertion positions. Tags are opaque and do not count as speech text.
    """

    def __init__(self, rules: Iterable[TextProcessingRule]) -> None:
        self._rules = tuple(
            rule
            for rule in rules
            if rule.enabled and rule.condition is None and rule.mode is RuleMode.INSERT
        )
        self._pending = ""
        self._message_start = True
        self._line_start = True
        # 0: ordinary speech; 1: punctuation/closing quotes; 2: following whitespace.
        self._sentence = 2
        self._leading = ""
        self._existing: set[str] = set()
        self._prefix_limit = max((len(rule.replace) for rule in self._rules), default=0)

    def feed(self, text: str, *, final: bool = False) -> str:
        """Emit stable text, retaining only incomplete tags or possible prefixes."""
        if not self._rules:
            return text
        self._pending += text
        output: list[str] = []
        index = 0
        while index < len(self._pending):
            char = self._pending[index]
            if char in "[<":
                end = self._pending.find("]" if char == "[" else ">", index + 1)
                if end < 0 and not final:
                    break
                if end >= 0:
                    tag = self._pending[index : end + 1]
                    output.append(tag)
                    if self._message_start or self._line_start or self._sentence:
                        self._remember_leading(tag)
                    index = end + 1
                    continue

            if not char.isspace():
                placements = set()
                if self._message_start:
                    placements.add(InsertionPlacement.MESSAGE_START)
                if self._line_start:
                    placements.add(InsertionPlacement.LINE_START)
                if self._sentence == 2:
                    placements.add(InsertionPlacement.SENTENCE_START)
                additions: list[str] = []
                wait_for_prefix = False
                for rule in self._rules:
                    if not placements.intersection(rule.placements):
                        continue
                    exists = self._existing_prefix(
                        rule.replace, self._pending[index:], final
                    )
                    if exists is None:
                        wait_for_prefix = True
                        break
                    if not exists and rule.replace not in additions:
                        additions.append(rule.replace)
                if wait_for_prefix:
                    break
                output.extend(additions)
                self._message_start = False
                self._line_start = False
                self._leading = ""
                self._existing.clear()

            output.append(char)
            if char.isspace():
                if char in "\r\n":
                    self._line_start = True
                    self._leading = ""
                    self._existing.clear()
                if self._sentence == 1:
                    self._sentence = 2
                if self._message_start or self._line_start or self._sentence == 2:
                    self._remember_leading(char)
            elif char in ".!?":
                self._sentence = 1
            elif not (self._sentence == 1 and char in _CLOSING_QUOTES):
                self._sentence = 0
            index += 1

        self._pending = self._pending[index:]
        return "".join(output)

    def _remember_leading(self, text: str) -> None:
        """Retain enough of leading markup/whitespace for exact duplicate checks."""
        candidate = self._leading + text
        starts = {0}
        starts.update(match.start() for match in _CONTROL_TAG_RE.finditer(candidate))
        self._existing.update(
            rule.replace
            for rule in self._rules
            if any(candidate.startswith(rule.replace, start) for start in starts)
        )
        self._leading = candidate[-self._prefix_limit :]

    def _existing_prefix(self, prefix: str, remaining: str, final: bool) -> bool | None:
        """Check source copies without interpreting provider-specific tags."""
        if prefix in self._existing:
            return True
        candidate = self._leading + remaining
        starts = {0, len(self._leading)}
        starts.update(
            match.start() for match in _CONTROL_TAG_RE.finditer(self._leading)
        )
        need_more = False
        for start in starts:
            available = candidate[start:]
            if available.startswith(prefix):
                return True
            if not final and prefix.startswith(available):
                need_more = True
        return None if need_more else False
