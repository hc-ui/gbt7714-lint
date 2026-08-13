"""Render lint results as human-readable text or JSON."""

from __future__ import annotations

import json

from .models import LintResult

_SEVERITY_TAG = {"error": "错误", "warning": "警告"}


def render_text(result: LintResult, source_name: str = "<stdin>") -> str:
    lines = [f"检查 {source_name}：共 {len(result.entries)} 条参考文献"]
    if not result.issues:
        lines.append("未发现问题，符合 GB/T 7714—2025。")
        return "\n".join(lines)

    for issue in result.issues:
        tag = _SEVERITY_TAG.get(issue.severity, issue.severity)
        fix_mark = "（可自动修复）" if issue.fixable else ""
        lines.append(f"  {issue.entry_label} 第{issue.line_no}行 [{issue.rule_id}] {tag}：{issue.message}{fix_mark}")
        if issue.before is not None and issue.after is not None:
            lines.append(f"      {issue.before!r} → {issue.after!r}")

    lines.append(
        f"合计：{result.error_count} 个错误，{result.warning_count} 个警告；"
        f"其中 {result.fixable_count} 处可用 --fix 自动修复"
    )
    return "\n".join(lines)


def render_json(result: LintResult, source_name: str = "<stdin>") -> str:
    payload = {
        "source": source_name,
        "entries": len(result.entries),
        "errors": result.error_count,
        "warnings": result.warning_count,
        "fixable": result.fixable_count,
        "issues": [i.to_dict() for i in result.issues],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
