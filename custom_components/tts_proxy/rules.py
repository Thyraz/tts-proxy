"""Text Processing Rules and entity-state activation, independent of HA."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .const import (
    PLACEMENT_LINE_START,
    PLACEMENT_MESSAGE_START,
    PLACEMENT_SENTENCE_START,
    RULE_CASE_SENSITIVE,
    RULE_CONDITION_ENTITY,
    RULE_CONDITION_MAX_AGE,
    RULE_CONDITION_STATE,
    RULE_DISABLED,
    RULE_ENABLED,
    RULE_FIND,
    RULE_IGNORE_CASE,
    RULE_MODE,
    RULE_MODE_INSERT,
    RULE_MODE_LITERAL,
    RULE_MODE_REGEX,
    RULE_NAME,
    RULE_PLACEMENTS,
    RULE_REPLACE,
)


class RuleMode(StrEnum):
    """Supported Text Processing Rule modes."""

    LITERAL = RULE_MODE_LITERAL
    REGEX = RULE_MODE_REGEX
    INSERT = RULE_MODE_INSERT


class InsertionPlacement(StrEnum):
    """Logical message boundaries eligible for insertion."""

    MESSAGE_START = PLACEMENT_MESSAGE_START
    LINE_START = PLACEMENT_LINE_START
    SENTENCE_START = PLACEMENT_SENTENCE_START


class RuleValidationError(ValueError):
    """Raised when a Text Processing Rule is invalid."""


@dataclass(frozen=True, slots=True)
class EntityStateCondition:
    """One exact entity-state comparison with an optional report-age limit."""

    entity_id: str
    state: str
    max_age_seconds: int | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", self.entity_id):
            raise RuleValidationError("Condition entity must be a valid entity ID")
        if not self.state:
            raise RuleValidationError("Condition activating state cannot be empty")
        if self.max_age_seconds is not None:
            try:
                seconds = float(self.max_age_seconds)
            except (TypeError, ValueError, OverflowError) as err:
                raise RuleValidationError(
                    "Condition maximum age must be a positive whole number of seconds"
                ) from err
            if (
                isinstance(self.max_age_seconds, bool)
                or not math.isfinite(seconds)
                or seconds <= 0
                or not seconds.is_integer()
            ):
                raise RuleValidationError(
                    "Condition maximum age must be a positive whole number of seconds"
                )
            object.__setattr__(self, "max_age_seconds", int(seconds))


@dataclass(frozen=True, slots=True)
class EntityStateReport:
    """A copied entity state and the time HA last received a report for it."""

    state: str
    last_reported: datetime | None = None


@dataclass(frozen=True, slots=True)
class TextProcessingRule:
    """A replacement or insertion with an optional Entity State Condition."""

    find: str = ""
    replace: str = ""
    mode: RuleMode = RuleMode.LITERAL
    ignore_case: bool = False
    enabled: bool = True
    name: str = ""
    condition: EntityStateCondition | None = None
    placements: tuple[InsertionPlacement, ...] = ()

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "mode", RuleMode(self.mode))
            object.__setattr__(
                self,
                "placements",
                tuple(dict.fromkeys(InsertionPlacement(p) for p in self.placements)),
            )
        except ValueError as err:
            raise RuleValidationError(str(err)) from err
        self.validate()

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> TextProcessingRule:
        """Parse current and legacy config-flow rule fields."""
        try:
            mode = RuleMode(str(raw.get(RULE_MODE) or RULE_MODE_LITERAL))
        except ValueError as err:
            raise RuleValidationError(
                f"Unsupported rule mode: {raw.get(RULE_MODE)!r}"
            ) from err
        entity_id = str(raw.get(RULE_CONDITION_ENTITY, "") or "").strip()
        state = raw.get(RULE_CONDITION_STATE)
        max_age = raw.get(RULE_CONDITION_MAX_AGE)
        condition = None
        if entity_id or state not in (None, "") or max_age not in (None, ""):
            if not entity_id or state in (None, ""):
                raise RuleValidationError(
                    "A condition needs both an entity and an activating state"
                )
            condition = EntityStateCondition(
                entity_id, str(state), None if max_age in (None, "") else max_age
            )
        placements = raw.get(RULE_PLACEMENTS, []) or []
        if mode is RuleMode.INSERT and not isinstance(placements, list):
            raise RuleValidationError("Insertion placements must be a list")
        return cls(
            find=str(raw.get(RULE_FIND, "") or ""),
            replace=str(raw.get(RULE_REPLACE, "") or ""),
            mode=mode,
            ignore_case=(
                not bool(raw[RULE_CASE_SENSITIVE])
                if RULE_CASE_SENSITIVE in raw
                else bool(raw.get(RULE_IGNORE_CASE, True))
            ),
            enabled=(
                not bool(raw[RULE_DISABLED])
                if RULE_DISABLED in raw
                else bool(raw.get(RULE_ENABLED, True))
            ),
            name=str(raw.get(RULE_NAME, "") or "").strip(),
            condition=condition,
            placements=tuple(placements) if mode is RuleMode.INSERT else (),
        )

    def validate(self) -> None:
        """Reject incomplete actions, conditions, and invalid regexes."""
        if self.mode is RuleMode.INSERT:
            if not self.replace:
                raise RuleValidationError("Insertion text cannot be empty")
            if not self.placements:
                raise RuleValidationError("Select at least one insertion placement")
        elif not self.find:
            raise RuleValidationError("Replacement rule find value cannot be empty")
        if self.mode is RuleMode.REGEX:
            try:
                re.compile(self.find, self._flags)
            except re.error as err:
                raise RuleValidationError(
                    f"Invalid regex rule {self.find!r}: {err}"
                ) from err

    @property
    def _flags(self) -> int:
        return re.IGNORECASE if self.ignore_case else 0

    def apply(self, text: str) -> str:
        """Apply a resolved replacement once to a speech-text segment."""
        if (
            not self.enabled
            or self.condition is not None
            or self.mode is RuleMode.INSERT
        ):
            return text
        if self.mode is RuleMode.REGEX:
            return re.sub(self.find, self.replace, text, flags=self._flags)
        if self.ignore_case:
            return re.sub(
                re.escape(self.find),
                lambda _match: self.replace,
                text,
                flags=self._flags,
            )
        return text.replace(self.find, self.replace)


# Keep the existing import and construction API for replacement-only callers.
ReplacementRule = TextProcessingRule


def condition_snapshot(
    rules: Iterable[TextProcessingRule],
    state_getter: Callable[[str], str | EntityStateReport | None],
    *,
    now: datetime | None = None,
) -> tuple[bool, ...]:
    """Capture state and age matches at one time, reading each entity once."""
    now = now or datetime.now(UTC)
    states: dict[str, EntityStateReport | None] = {}
    results: list[bool] = []
    for rule in rules:
        condition = rule.condition
        if condition is None:
            results.append(rule.enabled)
        elif not rule.enabled:
            results.append(False)
        else:
            if condition.entity_id not in states:
                state = state_getter(condition.entity_id)
                states[condition.entity_id] = (
                    EntityStateReport(state) if isinstance(state, str) else state
                )
            report = states[condition.entity_id]
            if report is None or report.state != condition.state:
                results.append(False)
                continue
            active = True
            if condition.max_age_seconds is not None:
                active = report.last_reported is not None and (
                    0
                    <= (now - report.last_reported).total_seconds()
                    <= condition.max_age_seconds
                )
            results.append(active)
    return tuple(results)


def rules_from_snapshot(
    rules: Iterable[TextProcessingRule], snapshot: Iterable[bool]
) -> tuple[TextProcessingRule, ...]:
    """Resolve active rules without further entity-state reads."""
    return tuple(
        replace(rule, condition=None)
        for rule, active in zip(rules, snapshot, strict=True)
        if active and rule.enabled
    )


def resolve_rules(
    rules: Iterable[TextProcessingRule],
    entity_states: Mapping[str, str | EntityStateReport] | None = None,
) -> tuple[TextProcessingRule, ...]:
    """Resolve conditions for pure normalization and configuration preview."""
    rules = tuple(rules)
    return rules_from_snapshot(
        rules, condition_snapshot(rules, (entity_states or {}).get)
    )
