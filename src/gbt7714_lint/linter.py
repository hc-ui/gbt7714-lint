"""High-level API: lint or fix a whole bibliography text."""

from __future__ import annotations

from .models import Entry, LintResult
from .parser import parse_bibliography
from .rules import ENTRY_CHECKS, ENTRY_FIXES, check_numbering


def lint_text(text: str) -> LintResult:
    """Lint pasted bibliography text and return entries plus issues."""
    entries = parse_bibliography(text)
    result = LintResult(entries=entries)
    for entry in entries:
        for check in ENTRY_CHECKS:
            result.issues.extend(check(entry))
    result.issues.extend(check_numbering(entries))
    result.issues.sort(key=lambda i: (i.line_no, i.rule_id))
    return result


def fix_entry_body(body: str) -> str:
    """Apply every deterministic fix to one entry body."""
    for fix in ENTRY_FIXES:
        body = fix(body)
    return body


def fix_text(text: str) -> tuple[str, LintResult]:
    """Return the fixed text and a lint result of what remains unfixed.

    Entry labels and blank lines are preserved; wrapped entries are joined
    onto a single line (which is also what Word expects when pasting back).
    """
    entries = parse_bibliography(text)
    lines = []
    for entry in entries:
        fixed_body = fix_entry_body(entry.body)
        prefix = f"{entry.label} " if entry.label else ""
        lines.append(f"{prefix}{fixed_body}")
    fixed = "\n".join(lines)
    if text.endswith("\n"):
        fixed += "\n"
    return fixed, lint_text(fixed)
