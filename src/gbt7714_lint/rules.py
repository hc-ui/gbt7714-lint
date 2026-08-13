"""Rule engine: checks and auto-fixes for GB/T 7714-2025.

Each rule has a ``check(entry) -> list[Issue]`` and optionally a
``fix(body) -> str`` that rewrites the entry body. Fixes are deterministic
text transforms; anything ambiguous stays a warning without a fix.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from .models import Entry, Issue
from .parser import (
    DATE_BRACKET_RE,
    DOI_RE,
    TYPE_RE,
    URL_RE,
    VALID_CARRIERS,
    VALID_TYPES,
    authors_segment,
    find_type_marker,
    split_authors,
)
from .pinyin import is_pinyin_surname

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ALLCAPS_WORD_RE = re.compile(r"\b[A-Z]{2,}\b")
_ET_AL_RE = re.compile(r"等|et\s+al\b", re.IGNORECASE)


def _issue(
    entry: Entry,
    rule_id: str,
    severity: str,
    message: str,
    fixable: bool = False,
    before: Optional[str] = None,
    after: Optional[str] = None,
) -> Issue:
    return Issue(
        rule_id=rule_id,
        severity=severity,
        message=message,
        line_no=entry.line_no,
        entry_label=entry.display_label,
        fixable=fixable,
        before=before,
        after=after,
    )


# ---------------------------------------------------------------------------
# E001: document type marker is mandatory in GB/T 7714-2025
# ---------------------------------------------------------------------------

def check_missing_type(entry: Entry) -> list[Issue]:
    if find_type_marker(entry.body) is None:
        return [
            _issue(
                entry,
                "E001",
                "error",
                "缺少文献类型标识（如 [J]、[M]、[D]）。2025 版将文献类型标识改为必备著录项",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# E002: unknown type / carrier code (2025 Appendix A)
# ---------------------------------------------------------------------------

def check_unknown_type(entry: Entry) -> list[Issue]:
    issues = []
    m = find_type_marker(entry.body)
    if not m:
        return issues
    type_code = m.group("type")
    carrier = m.group("carrier")
    if type_code.upper() not in VALID_TYPES:
        issues.append(
            _issue(
                entry,
                "E002",
                "error",
                f"未知的文献类型标识 [{type_code}]。2025 版有效标识：{'、'.join(sorted(VALID_TYPES))}",
            )
        )
    elif type_code != type_code.upper():
        issues.append(
            _issue(
                entry,
                "E002",
                "error",
                f"文献类型标识应使用大写字母：[{type_code}] 应为 [{type_code.upper()}]",
                fixable=True,
                before=f"[{type_code}]",
                after=f"[{type_code.upper()}]",
            )
        )
    if carrier:
        if carrier.upper() not in VALID_CARRIERS:
            issues.append(
                _issue(
                    entry,
                    "E002",
                    "error",
                    f"未知的载体类型标识 /{carrier}。2025 版有效载体：{'、'.join(sorted(VALID_CARRIERS))}（新增 MM 缩微资料）",
                )
            )
        elif carrier != carrier.upper():
            issues.append(
                _issue(
                    entry,
                    "E002",
                    "error",
                    f"载体类型标识应使用大写字母：/{carrier} 应为 /{carrier.upper()}",
                    fixable=True,
                    before=f"/{carrier}",
                    after=f"/{carrier.upper()}",
                )
            )
    return issues


def fix_type_case(body: str) -> str:
    def repl(m: re.Match) -> str:
        type_code = m.group("type").upper()
        carrier = m.group("carrier")
        if type_code not in VALID_TYPES:
            return m.group(0)
        if carrier:
            if carrier.upper() not in VALID_CARRIERS:
                return m.group(0)
            return f"[{type_code}/{carrier.upper()}]"
        return f"[{type_code}]"

    return TYPE_RE.sub(repl, body)


# ---------------------------------------------------------------------------
# W101: foreign surnames must be initial-caps in 2025 (were ALL CAPS in 2015)
# ---------------------------------------------------------------------------

def _fix_surname_case_in_segment(segment: str) -> str:
    def repl(m: re.Match) -> str:
        word = m.group(0)
        if is_pinyin_surname(word):
            return word
        return word.capitalize()

    return _ALLCAPS_WORD_RE.sub(repl, segment)


def check_surname_case(entry: Entry) -> list[Issue]:
    seg = authors_segment(entry.body)
    if not seg:
        return []
    fixed = _fix_surname_case_in_segment(seg)
    if fixed != seg:
        return [
            _issue(
                entry,
                "W101",
                "warning",
                "外文作者姓氏全大写是 2015 版写法，2025 版改为仅首字母大写（汉语拼音姓氏仍全大写）",
                fixable=True,
                before=seg,
                after=fixed,
            )
        ]
    return []


def fix_surname_case(body: str) -> str:
    seg = authors_segment(body)
    if not seg:
        return body
    fixed = _fix_surname_case_in_segment(seg)
    if fixed == seg:
        return body
    return fixed + body[len(seg):]


# ---------------------------------------------------------------------------
# W102: "，等译." -> "，等，译." (2025 adds the comma before the role word)
# ---------------------------------------------------------------------------

_ETAL_ROLE_RE = re.compile(r"(等)\s*(译|编译|编|校|注)(?=[.。．,，;；\s]|$)")


def check_et_al_role(entry: Entry) -> list[Issue]:
    m = _ETAL_ROLE_RE.search(entry.body)
    if m:
        return [
            _issue(
                entry,
                "W102",
                "warning",
                f"其他责任者著录 2025 版要求“等”与“{m.group(2)}”之间加逗号：“等{m.group(2)}”应为“等，{m.group(2)}”",
                fixable=True,
                before=m.group(0),
                after=f"{m.group(1)}，{m.group(2)}",
            )
        ]
    return []


def fix_et_al_role(body: str) -> str:
    return _ETAL_ROLE_RE.sub(r"\1，\2", body)


# ---------------------------------------------------------------------------
# W103: non-online resources must NOT carry a cited date in 2025
# W104: online resources still require one
# ---------------------------------------------------------------------------

def _is_online(body: str) -> bool:
    m = find_type_marker(body)
    if m and m.group("carrier") and m.group("carrier").upper() == "OL":
        return True
    return bool(URL_RE.search(body) or DOI_RE.search(body))


def check_cited_date(entry: Entry) -> list[Issue]:
    has_date = bool(DATE_BRACKET_RE.search(entry.body))
    m = find_type_marker(entry.body)
    if not m:
        return []
    online = _is_online(entry.body)
    if not online and has_date:
        d = DATE_BRACKET_RE.search(entry.body)
        return [
            _issue(
                entry,
                "W103",
                "warning",
                "2025 版规定非在线资源不著录引用日期，应删除方括号引用日期",
                fixable=True,
                before=d.group(0),
                after="",
            )
        ]
    if online and not has_date:
        return [
            _issue(
                entry,
                "W104",
                "warning",
                "在线资源（/OL）应著录引用日期，如 [2026-08-13]",
            )
        ]
    return []


def fix_cited_date(body: str) -> str:
    if _is_online(body) or find_type_marker(body) is None:
        return body
    body = DATE_BRACKET_RE.sub("", body)
    body = re.sub(r"\s+([.。．,，;；])", r"\1", body)
    return body


# ---------------------------------------------------------------------------
# W105: more than 3 authors must be truncated with 等 / et al
# ---------------------------------------------------------------------------

def check_author_count(entry: Entry) -> list[Issue]:
    seg = authors_segment(entry.body)
    if not seg or _ET_AL_RE.search(seg):
        return []
    authors = split_authors(seg)
    if len(authors) > 3:
        etal = "等" if _CJK_RE.search(seg) else "et al"
        sep = "," if _CJK_RE.search(seg) else ", "
        fixed = sep.join(authors[:3]) + sep + etal
        return [
            _issue(
                entry,
                "W105",
                "warning",
                f"著者超过 3 人（共 {len(authors)} 人），应只著录前 3 人后加“{etal}”",
                fixable=True,
                before=seg,
                after=fixed,
            )
        ]
    return []


def fix_author_count(body: str) -> str:
    seg = authors_segment(body)
    if not seg or _ET_AL_RE.search(seg):
        return body
    authors = split_authors(seg)
    if len(authors) <= 3:
        return body
    etal = "等" if _CJK_RE.search(seg) else "et al"
    sep = "," if _CJK_RE.search(seg) else ", "
    fixed = sep.join(authors[:3]) + sep + etal
    return fixed + body[len(seg):]


# ---------------------------------------------------------------------------
# W106: dates must be YYYY-MM-DD
# ---------------------------------------------------------------------------

def _normalize_date(date_str: str) -> Optional[str]:
    m = re.match(
        r"^\s*(\d{4})\s*[-–—./年]\s*(\d{1,2})\s*[-–—./月]\s*(\d{1,2})\s*日?\s*$", date_str
    )
    if not m:
        return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y}-{mo:02d}-{d:02d}"


def check_date_format(entry: Entry) -> list[Issue]:
    issues = []
    for m in DATE_BRACKET_RE.finditer(entry.body):
        normalized = _normalize_date(m.group("date"))
        if normalized and m.group(0) != f"[{normalized}]":
            issues.append(
                _issue(
                    entry,
                    "W106",
                    "warning",
                    "日期应采用 GB/T 7408 格式 YYYY-MM-DD 并置于半角方括号内",
                    fixable=True,
                    before=m.group(0),
                    after=f"[{normalized}]",
                )
            )
    return issues


def fix_date_format(body: str) -> str:
    def repl(m: re.Match) -> str:
        normalized = _normalize_date(m.group("date"))
        return f"[{normalized}]" if normalized else m.group(0)

    return DATE_BRACKET_RE.sub(repl, body)


# ---------------------------------------------------------------------------
# W107: bibliographic separators must be half-width
# ---------------------------------------------------------------------------

def check_fullwidth_punct(entry: Entry) -> list[Issue]:
    issues = []
    seg = authors_segment(entry.body)
    if seg and re.search(r"[，；]", seg):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "著者之间的分隔符应使用半角逗号“,”而非全角“，”",
                fixable=True,
                before=seg,
                after=re.sub(r"\s*[，；]\s*", ",", seg),
            )
        )
    if re.search(r"[．]", entry.body):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "著录符号应使用半角句点“.”而非全角“．”",
                fixable=True,
            )
        )
    if entry.body.rstrip().endswith("。"):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "条目结尾应使用半角句点“.”而非句号“。”",
                fixable=True,
                before="。",
                after=".",
            )
        )
    if re.search(r"[［］]", entry.body):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "方括号应使用半角“[ ]”而非全角“［ ］”",
                fixable=True,
            )
        )
    return issues


def fix_fullwidth_punct(body: str) -> str:
    seg = authors_segment(body)
    if seg:
        fixed_seg = re.sub(r"\s*[，；]\s*", ",", seg)
        body = fixed_seg + body[len(seg):]
    # Full-width period used as a bibliographic separator (protect URLs)
    parts = URL_RE.split(body)
    urls = URL_RE.findall(body)
    parts = [p.replace("．", ".") for p in parts]
    rebuilt = parts[0]
    for url, part in zip(urls, parts[1:]):
        rebuilt += url + part
    body = rebuilt
    body = body.replace("［", "[").replace("］", "]")
    if body.rstrip().endswith("。"):
        body = body.rstrip()[:-1] + "."
    return body


# ---------------------------------------------------------------------------
# W109: entries end with a period (unless ending with a URL/DOI)
# ---------------------------------------------------------------------------

def check_trailing_period(entry: Entry) -> list[Issue]:
    body = entry.body.rstrip()
    if not body:
        return []
    if body.endswith((".", "。", "．")):
        return []
    tail = body.split()[-1] if body.split() else ""
    if URL_RE.search(tail) or DOI_RE.search(tail):
        return []
    return [
        _issue(
            entry,
            "W109",
            "warning",
            "条目结尾缺少句点“.”",
            fixable=True,
            before=body[-12:],
            after=body[-12:] + ".",
        )
    ]


def fix_trailing_period(body: str) -> str:
    stripped = body.rstrip()
    if not stripped or stripped.endswith((".", "。", "．")):
        return body
    tail = stripped.split()[-1] if stripped.split() else ""
    if URL_RE.search(tail) or DOI_RE.search(tail):
        return body
    return stripped + "."


# ---------------------------------------------------------------------------
# W108 (list-level): numbering must be continuous from [1]
# ---------------------------------------------------------------------------

def check_numbering(entries: list[Entry]) -> list[Issue]:
    numbered = [e for e in entries if e.number is not None]
    if len(numbered) < 2:
        return []
    issues = []
    expected = numbered[0].number
    seen: set[int] = set()
    for e in numbered:
        if e.number in seen:
            issues.append(
                _issue(e, "W108", "warning", f"序号 {e.number} 重复")
            )
        seen.add(e.number)
        if e.number != expected:
            issues.append(
                _issue(
                    e,
                    "W108",
                    "warning",
                    f"序号不连续：期望 [{expected}]，实际 [{e.number}]",
                )
            )
            expected = e.number
        expected += 1
    return issues


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ENTRY_CHECKS: list[Callable[[Entry], list[Issue]]] = [
    check_missing_type,
    check_unknown_type,
    check_surname_case,
    check_et_al_role,
    check_cited_date,
    check_author_count,
    check_date_format,
    check_fullwidth_punct,
    check_trailing_period,
]

# Applied in order; punctuation first so later rules see normalized text
ENTRY_FIXES: list[Callable[[str], str]] = [
    fix_fullwidth_punct,
    fix_type_case,
    fix_surname_case,
    fix_et_al_role,
    fix_author_count,
    fix_date_format,
    fix_cited_date,
    fix_trailing_period,
]
