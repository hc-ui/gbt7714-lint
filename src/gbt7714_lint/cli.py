"""Command-line interface: ``gbt7714-lint refs.txt [--fix] [--json]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .linter import fix_text, lint_text
from .report import render_json, render_text


def _read_input(path_arg: str) -> tuple[str, str]:
    """Return (text, source_name); tolerate Windows GBK files."""
    if path_arg == "-":
        return sys.stdin.read(), "<stdin>"
    path = Path(path_arg)
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return data.decode(encoding), str(path)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), str(path)


def main(argv: list[str] | None = None) -> int:
    # Chinese rule messages must not crash on non-UTF8 consoles (e.g. cp437)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(
        prog="gbt7714-lint",
        description="检查参考文献列表是否符合 GB/T 7714—2025《信息与文献 参考文献著录规则》，并可自动修复常见问题。",
        epilog="示例：gbt7714-lint refs.txt --fix -o refs_fixed.txt",
    )
    parser.add_argument("input", help="参考文献文本文件路径，使用 - 从标准输入读取")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    parser.add_argument("-o", "--output", help="修复结果输出到该文件（默认打印到标准输出）")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出检查结果")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        text, source_name = _read_input(args.input)
    except OSError as exc:
        print(f"无法读取输入：{exc}", file=sys.stderr)
        return 2

    if args.fix:
        fixed, remaining = fix_text(text)
        if args.output:
            Path(args.output).write_text(fixed, encoding="utf-8")
            print(f"已修复并写入 {args.output}", file=sys.stderr)
        else:
            print(fixed)
        report = render_json(remaining, source_name) if args.json else render_text(remaining, source_name)
        print(report, file=sys.stderr)
        return 1 if remaining.error_count else 0

    result = lint_text(text)
    print(render_json(result, source_name) if args.json else render_text(result, source_name))
    return 1 if result.error_count else 0


if __name__ == "__main__":
    sys.exit(main())
