"""Data models shared by the parser, rules and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Entry:
    """One bibliography entry.

    ``body`` is the entry text without the leading ``[1]``-style label; all
    rules operate on it. ``raw`` keeps the original text for display.
    """

    raw: str
    body: str
    line_no: int
    label: Optional[str] = None
    number: Optional[int] = None

    @property
    def display_label(self) -> str:
        return self.label if self.label else f"第{self.line_no}行"


@dataclass
class Issue:
    """A single finding reported by a rule."""

    rule_id: str
    severity: str  # "error" | "warning"
    message: str
    line_no: int
    entry_label: str
    fixable: bool = False
    before: Optional[str] = None
    after: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "rule": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "line": self.line_no,
            "entry": self.entry_label,
            "fixable": self.fixable,
        }
        if self.before is not None:
            d["before"] = self.before
        if self.after is not None:
            d["after"] = self.after
        return d


@dataclass
class LintResult:
    entries: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.issues if i.fixable)
