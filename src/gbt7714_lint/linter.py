"""High-level API: lint or fix a whole bibliography text."""

from __future__ import annotations

from .config import DEFAULT_CONFIG, Config
from .models import LintResult
from .parser import parse_bibliography
from .rules import ENTRY_CHECKS, ENTRY_FIXES, check_numbering

# One rule's fix can expose work for a rule that runs earlier in the pipeline,
# so the pipeline is re-run until the text stops changing.
_MAX_FIX_PASSES = 5


def lint_text(text: str, config: Config = DEFAULT_CONFIG) -> LintResult:
    """Lint pasted bibliography text and return entries plus issues."""
    items = parse_bibliography(text)
    entries = [e for e in items if e.kind == "entry"]
    result = LintResult(entries=entries)
    for entry in entries:
        for check in ENTRY_CHECKS:
            result.issues.extend(check(entry, config))
    result.issues.extend(check_numbering(entries))
    result.issues.sort(key=lambda i: (i.line_no, i.rule_id))
    return result


def fix_entry_body(body: str, config: Config = DEFAULT_CONFIG) -> str:
    """Apply every deterministic fix to one entry body until it is stable."""
    for _ in range(_MAX_FIX_PASSES):
        fixed = body
        for fix in ENTRY_FIXES:
            fixed = fix(fixed, config)
        if fixed == body:
            break
        body = fixed
    return body


def fix_text(text: str, config: Config = DEFAULT_CONFIG) -> tuple[str, LintResult]:
    """Return the fixed text and a lint result of what remains unfixed.

    Entry labels, section headings and blank-line spacing are preserved;
    wrapped entries are joined onto a single line, which is also what Word
    expects when pasting the list back.
    """
    lines = []
    for item in parse_bibliography(text):
        lines.extend([""] * item.leading_blanks)
        if item.kind == "heading":
            lines.append(item.raw)
            continue
        prefix = f"{item.label} " if item.label else ""
        lines.append(f"{prefix}{fix_entry_body(item.body, config)}")
    fixed = "\n".join(lines)
    if text.endswith("\n") and fixed:
        fixed += "\n"
    return fixed, lint_text(fixed, config)
