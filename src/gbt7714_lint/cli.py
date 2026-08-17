"""Command-line interface: ``gbt7714-lint refs.txt [--fix] [--json]``."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import PUNCT_KEEP, PUNCT_STYLES, Config
from .linter import fix_text, lint_text
from .models import LintResult
from .report import render_json, render_text
from .rules import ALL_RULE_IDS

_ENCODINGS = ("utf-8-sig", "utf-8", "gbk")


def _decode(data: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_clipboard() -> str:
    """Read the system clipboard. Windows uses PowerShell; macOS uses pbpaste."""
    if sys.platform == "win32":
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            err = _decode(completed.stderr).strip() or "Get-Clipboard failed"
            raise OSError(err)
        return _decode(completed.stdout)
    for command in (["pbpaste"], ["xclip", "-selection", "clipboard", "-o"]):
        try:
            completed = subprocess.run(command, capture_output=True, check=False)
        except OSError:
            continue
        if completed.returncode == 0:
            return _decode(completed.stdout)
    raise OSError("clipboard is not available on this system")


def _read_input(path_arg: str) -> tuple[str, str]:
    """Return (text, source_name), tolerating UTF-8 and GBK input."""
    if path_arg == "-":
        buffer = getattr(sys.stdin, "buffer", None)
        if buffer is not None:
            return _decode(buffer.read()), "<stdin>"
        return sys.stdin.read(), "<stdin>"
    path = Path(path_arg)
    return _decode(path.read_bytes()), str(path)


def _write_fixed(text: str) -> None:
    """Write fixed text to stdout without lossy re-encoding.

    When stdout is redirected the text is emitted as UTF-8 bytes, so that
    ``--fix > out.txt`` on a GBK console cannot turn characters into "?".
    """
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None and not sys.stdout.isatty():
        buffer.write(text.encode("utf-8"))
        if not text.endswith("\n"):
            buffer.write(b"\n")
        buffer.flush()
    else:
        print(text)


def _parse_rule_list(raw: str, option: str) -> set:
    rules = {r.strip().upper() for r in raw.split(",") if r.strip()}
    unknown = rules - set(ALL_RULE_IDS)
    if unknown:
        raise argparse.ArgumentTypeError(
            f"{option} 含有未知规则：{'、'.join(sorted(unknown))}；"
            f"可用规则：{'、'.join(ALL_RULE_IDS)}"
        )
    return rules


def _filter_issues(result: LintResult, ignore: set, select: set) -> LintResult:
    if not ignore and not select:
        return result
    kept = [
        i
        for i in result.issues
        if i.rule_id not in ignore and (not select or i.rule_id in select)
    ]
    return LintResult(entries=result.entries, issues=kept)


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
        epilog=(
            "示例：\n"
            "  gbt7714-lint refs.txt\n"
            "  gbt7714-lint --clip\n"
            "  gbt7714-lint refs.txt --fix -o refs_fixed.txt\n"
            "  gbt7714-lint refs.txt --ignore W104,W108\n"
            f"可用规则：{'、'.join(ALL_RULE_IDS)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="参考文献文本文件路径，使用 - 从标准输入读取",
    )
    parser.add_argument(
        "--clip",
        action="store_true",
        help="从系统剪贴板读取（适合从 Word 复制后直接检查）",
    )
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    parser.add_argument(
        "-o", "--output", help="修复结果输出到该文件（UTF-8 编码，默认打印到标准输出）"
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出检查结果")
    parser.add_argument("--ignore", metavar="规则", help="忽略这些规则，逗号分隔，如 W104,W108")
    parser.add_argument("--select", metavar="规则", help="只检查这些规则，逗号分隔")
    parser.add_argument(
        "--punct",
        choices=PUNCT_STYLES,
        default=PUNCT_KEEP,
        help=(
            "标点风格：keep 保留逗号/冒号/圆括号原有的全角或半角形式（默认，"
            "因为 2025 版国标未明确规定）；half 统一改为半角，适用于要求半角的学位论文格式"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        ignore = _parse_rule_list(args.ignore, "--ignore") if args.ignore else set()
        select = _parse_rule_list(args.select, "--select") if args.select else set()
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    if args.clip:
        try:
            text, source_name = _read_clipboard(), "<clipboard>"
        except OSError as exc:
            print(f"无法读取剪贴板：{exc}", file=sys.stderr)
            return 2
    elif args.input:
        try:
            text, source_name = _read_input(args.input)
        except OSError as exc:
            print(f"无法读取输入：{exc}", file=sys.stderr)
            return 2
    else:
        parser.error("请提供参考文献文件，或使用 --clip / -")

    if not text.strip():
        print("没有可检查的文本（文件或剪贴板是空的）。", file=sys.stderr)
        return 2

    config = Config(punct=args.punct)

    if args.fix:
        fixed, remaining = fix_text(text, config)
        remaining = _filter_issues(remaining, ignore, select)
        if args.output:
            Path(args.output).write_text(fixed, encoding="utf-8")
            print(f"已修复并写入 {args.output}", file=sys.stderr)
        else:
            _write_fixed(fixed)
        report = render_json(remaining, source_name) if args.json else render_text(remaining, source_name)
        print(report, file=sys.stderr)
        return 1 if remaining.error_count else 0

    result = _filter_issues(lint_text(text, config), ignore, select)
    print(render_json(result, source_name) if args.json else render_text(result, source_name))
    return 1 if result.error_count else 0


if __name__ == "__main__":
    sys.exit(main())
