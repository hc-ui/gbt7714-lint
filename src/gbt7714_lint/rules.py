"""Rule engine: checks and auto-fixes for GB/T 7714-2025.

Each rule has a ``check(entry) -> list[Issue]`` and, when the problem can be
repaired mechanically, a ``fix(body) -> str``. A fixable check always derives
its suggested replacement from the very same helper the fix uses, so the two
can never drift apart and ``--fix`` never leaves a "fixable" issue behind.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Callable, Optional

from .config import DEFAULT_CONFIG, Config
from .models import Entry, Issue
from .parser import (
    DOI_RE,
    MASK_CHAR,
    PAREN_DATE_RE,
    SQUARE_DATE_RE,
    TYPE_RE,
    URL_RE,
    VALID_CARRIERS,
    VALID_TYPES,
    authors_segment,
    find_type_marker,
    mask_protected,
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


def _replace_outside_urls(body: str, mapping: dict) -> str:
    """Replace characters per ``mapping`` everywhere except inside URLs/DOIs."""
    masked = mask_protected(body)
    return "".join(
        mapping.get(ch, ch) if mc != MASK_CHAR else ch for ch, mc in zip(body, masked)
    )


def _contains_outside_urls(body: str, chars: str) -> bool:
    masked = mask_protected(body)
    return any(ch in chars for ch, mc in zip(body, masked) if mc != MASK_CHAR)


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
    m = find_type_marker(entry.body)
    if not m:
        return []
    type_code = m.group("type")
    carrier = m.group("carrier")
    issues = []

    if type_code.upper() not in VALID_TYPES:
        issues.append(
            _issue(
                entry,
                "E002",
                "error",
                f"未知的文献类型标识 [{type_code}]。2025 版有效标识：{'、'.join(sorted(VALID_TYPES))}",
            )
        )
    if carrier and carrier.upper() not in VALID_CARRIERS:
        issues.append(
            _issue(
                entry,
                "E002",
                "error",
                f"未知的载体类型标识 /{carrier}。2025 版有效载体：{'、'.join(sorted(VALID_CARRIERS))}（新增 MM 缩微资料）",
            )
        )
    if issues:
        return issues

    # Both codes are known: report the marker as one unit so that the
    # reported text can actually be found in the user's document.
    marker = m.group(0)
    upper = f"[{type_code.upper()}/{carrier.upper()}]" if carrier else f"[{type_code.upper()}]"
    if marker != upper:
        issues.append(
            _issue(
                entry,
                "E002",
                "error",
                f"文献类型标识应使用大写字母：{marker} 应为 {upper}",
                fixable=True,
                before=marker,
                after=upper,
            )
        )
    return issues


def fix_type_case(body: str) -> str:
    masked = mask_protected(body)

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

    out = []
    last = 0
    for m in TYPE_RE.finditer(masked):
        out.append(body[last : m.start()])
        out.append(repl(m))
        last = m.end()
    out.append(body[last:])
    return "".join(out)


# ---------------------------------------------------------------------------
# W101: foreign surnames must be initial-caps in 2025 (were ALL CAPS in 2015)
# ---------------------------------------------------------------------------

# Organisations are legitimately all-caps and must survive the fix untouched.
_ORG_ACRONYMS = {
    "ACM", "ANSI", "APA", "ASTM", "BSI", "CAS", "CASS", "CCF", "CDC", "CEN",
    "CENELEC", "CNKI", "CNNIC", "DIN", "EPA", "ETSI", "EU", "FAO", "FDA",
    "IAEA", "IATA", "ICAO", "IEC", "IEEE", "IETF", "IFLA", "ILO", "IMF",
    "IPCC", "ISO", "ITU", "JIS", "MIIT", "NASA", "NATO", "NIH", "NIST",
    "NOAA", "NSFC", "OECD", "OMG", "SAC", "UN", "UNDP", "UNEP", "UNESCO",
    "UNICEF", "USDA", "USGS", "W3C", "WHO", "WIPO", "WMO", "WTO",
}

# Generational suffixes and roman numerals must not become "Jr" / "Iii".
_NAME_SUFFIXES = {"JR", "SR", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}


def _keep_uppercase(word: str, segment: str) -> bool:
    """Decide whether an ALL-CAPS token should stay all-caps."""
    upper = word.upper()
    if is_pinyin_surname(upper) or upper in _ORG_ACRONYMS or upper in _NAME_SUFFIXES:
        return True
    # A lone all-caps token forming the whole author group is an organisation:
    # a personal author in GB/T 7714 is always "SURNAME Initials".
    return len(upper) >= 3 and segment.strip() == word


def _normalize_surname_case(segment: str) -> str:
    def repl(m: re.Match) -> str:
        word = m.group(0)
        return word if _keep_uppercase(word, segment) else word.capitalize()

    return _ALLCAPS_WORD_RE.sub(repl, segment)


def check_surname_case(entry: Entry) -> list[Issue]:
    seg = authors_segment(entry.body)
    if not seg:
        return []
    fixed = _normalize_surname_case(seg)
    if fixed != seg:
        return [
            _issue(
                entry,
                "W101",
                "warning",
                "外文作者姓氏全大写是 2015 版写法，2025 版改为仅首字母大写（汉语拼音姓氏与机构缩写保持全大写）",
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
    return _normalize_surname_case(seg) + body[len(seg) :]


# ---------------------------------------------------------------------------
# W102: "等译." -> "等，译." (2025 adds the comma before the role word)
# ---------------------------------------------------------------------------

_ETAL_ROLE_RE = re.compile(r"(等)\s*(译|编译|编|校|注)(?=[.。．,，;；\s]|$)")


def _role_comma(config: Config) -> str:
    return ", " if config.normalize_separator_width else "，"


def check_et_al_role(entry: Entry, config: Config = DEFAULT_CONFIG) -> list[Issue]:
    m = _ETAL_ROLE_RE.search(entry.body)
    if not m:
        return []
    comma = _role_comma(config)
    return [
        _issue(
            entry,
            "W102",
            "warning",
            f"其他责任者著录 2025 版要求“等”与“{m.group(2)}”之间加逗号："
            f"“等{m.group(2)}”应为“等{comma}{m.group(2)}”",
            fixable=True,
            before=m.group(0),
            after=f"{m.group(1)}{comma}{m.group(2)}",
        )
    ]


def fix_et_al_role(body: str, config: Config = DEFAULT_CONFIG) -> str:
    return _ETAL_ROLE_RE.sub(rf"\1{_role_comma(config)}\2", body)


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
    """Only square-bracket dates are cited dates; parenthesised dates are
    publish/update dates and belong to a different rule set."""
    if find_type_marker(entry.body) is None:
        return []
    cited = SQUARE_DATE_RE.search(entry.body)
    online = _is_online(entry.body)
    if not online and cited:
        return [
            _issue(
                entry,
                "W103",
                "warning",
                "2025 版规定非在线资源不著录引用日期，应删除方括号引用日期",
                fixable=True,
                before=cited.group(0),
                after="",
            )
        ]
    if online and not cited:
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
    body = SQUARE_DATE_RE.sub("", body)
    return re.sub(r"\s+([.。．,，;；])", r"\1", body)


# ---------------------------------------------------------------------------
# W105: more than 3 authors must be truncated with 等 / et al
# ---------------------------------------------------------------------------

def _is_cjk_segment(seg: str) -> bool:
    """Judge the language of an author group by the names themselves."""
    return bool(_CJK_RE.search(seg.replace("等", "")))


def _detect_separator(seg: str) -> str:
    """Reuse the separator the author already used, spacing included.

    The standard does not settle the width of ``,``, so a rewrite must not
    silently switch the user from one convention to the other.
    """
    found = re.findall(r"\s*[,，;；]\s*", seg)
    if found:
        return Counter(found).most_common(1)[0][0]
    return "，" if _is_cjk_segment(seg) else ", "


def _truncate_authors(seg: str) -> str:
    if not seg or _ET_AL_RE.search(seg):
        return seg
    authors = split_authors(seg)
    if len(authors) <= 3:
        return seg
    sep = _detect_separator(seg)
    return sep.join(authors[:3]) + sep + ("等" if _is_cjk_segment(seg) else "et al")


def check_author_count(entry: Entry) -> list[Issue]:
    seg = authors_segment(entry.body)
    fixed = _truncate_authors(seg)
    if fixed != seg:
        count = len(split_authors(seg))
        etal = "等" if _is_cjk_segment(seg) else "et al"
        return [
            _issue(
                entry,
                "W105",
                "warning",
                f"著者超过 3 人（共 {count} 人），应只著录前 3 人后加“{etal}”",
                fixable=True,
                before=seg,
                after=fixed,
            )
        ]
    return []


def fix_author_count(body: str) -> str:
    seg = authors_segment(body)
    fixed = _truncate_authors(seg)
    return body if fixed == seg else fixed + body[len(seg) :]


# ---------------------------------------------------------------------------
# W106: dates must be YYYY-MM-DD, keeping the original bracket kind
# ---------------------------------------------------------------------------

_DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _normalize_date(date_str: str) -> Optional[str]:
    m = re.match(
        r"^\s*(\d{4})\s*[-–—./年]\s*(\d{1,2})\s*[-–—./月]\s*(\d{1,2})\s*日?\s*$", date_str
    )
    if not m:
        return None
    year, month, day = m.group(1), int(m.group(2)), int(m.group(3))
    if not 1 <= month <= 12 or not 1 <= day <= _DAYS_IN_MONTH[month - 1]:
        return None
    return f"{year}-{month:02d}-{day:02d}"


_DATE_KINDS = (
    (SQUARE_DATE_RE, "[", "]", "引用日期"),
    (PAREN_DATE_RE, "(", ")", "更新/发布日期"),
)


def _rewrite_date(m: re.Match, half_open: str, half_close: str, config: Config) -> Optional[str]:
    """Return the corrected date mark, or ``None`` if it is already right.

    The bracket characters the author used are preserved unless the user
    asked for half-width punctuation: only the date format itself is
    unambiguously mandated (GB/T 7408, ``YYYY-MM-DD``).
    """
    normalized = _normalize_date(m.group("date"))
    if normalized is None:
        return None
    if config.normalize_separator_width:
        open_ch, close_ch = half_open, half_close
    else:
        open_ch, close_ch = m.group("open"), m.group("close")
    expected = f"{open_ch}{normalized}{close_ch}"
    return None if m.group(0) == expected else expected


def check_date_format(entry: Entry, config: Config = DEFAULT_CONFIG) -> list[Issue]:
    issues = []
    for regex, open_ch, close_ch, kind in _DATE_KINDS:
        for m in regex.finditer(entry.body):
            expected = _rewrite_date(m, open_ch, close_ch, config)
            if expected is None:
                continue
            issues.append(
                _issue(
                    entry,
                    "W106",
                    "warning",
                    f"{kind}应采用 GB/T 7408 格式 YYYY-MM-DD",
                    fixable=True,
                    before=m.group(0),
                    after=expected,
                )
            )
    return issues


def fix_date_format(body: str, config: Config = DEFAULT_CONFIG) -> str:
    for regex, open_ch, close_ch, _ in _DATE_KINDS:

        def repl(m: re.Match, o=open_ch, c=close_ch) -> str:
            return _rewrite_date(m, o, c, config) or m.group(0)

        body = regex.sub(repl, body)
    return body


# ---------------------------------------------------------------------------
# W107: bibliographic separators must be half-width
# ---------------------------------------------------------------------------

# Only the symbols the standard is unambiguous about are always normalised:
# the period is half-width per GB/T 7714, and square brackets follow the
# same reading. Commas, colons and round brackets are style-dependent.
_FULLWIDTH_MAP = {"．": ".", "［": "[", "］": "]"}
_SEPARATOR_MAP = {"，": ", ", "；": "; ", "：": ": ", "（": "(", "）": ")"}


def _normalize_author_separators(seg: str, config: Config) -> str:
    """Normalise separators inside an author group, if the style asks for it."""
    if not seg or not config.normalize_separator_width:
        return seg
    return re.sub(r"\s*[,，;；]\s*", ", ", seg).strip()


def check_fullwidth_punct(entry: Entry, config: Config = DEFAULT_CONFIG) -> list[Issue]:
    issues = []
    seg = authors_segment(entry.body)
    normalized_seg = _normalize_author_separators(seg, config)
    if seg and normalized_seg != seg:
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "按半角标点风格，著者之间应使用半角逗号加空格“, ”",
                fixable=True,
                before=seg,
                after=normalized_seg,
            )
        )
    if config.normalize_separator_width and _contains_outside_urls(entry.body, "，；：（）"):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "按半角标点风格，著录用的逗号、分号、冒号、圆括号应使用半角形式",
                fixable=True,
            )
        )
    if _contains_outside_urls(entry.body, "．"):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "著录符号应使用半角句点“.”而非全角“．”",
                fixable=True,
            )
        )
    if _contains_outside_urls(entry.body, "［］"):
        issues.append(
            _issue(
                entry,
                "W107",
                "warning",
                "方括号应使用半角“[ ]”而非全角“［ ］”",
                fixable=True,
            )
        )
    if _ends_with_chinese_period(entry.body):
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
    return issues


def _ends_with_chinese_period(body: str) -> bool:
    stripped = body.rstrip()
    if not stripped.endswith("。"):
        return False
    # Do not touch a "。" that is part of a URL
    masked = mask_protected(body).rstrip()
    return bool(masked) and masked[-1] != MASK_CHAR


def fix_fullwidth_punct(body: str, config: Config = DEFAULT_CONFIG) -> str:
    seg = authors_segment(body)
    if seg:
        body = _normalize_author_separators(seg, config) + body[len(seg) :]
    mapping = dict(_FULLWIDTH_MAP)
    if config.normalize_separator_width:
        mapping.update(_SEPARATOR_MAP)
    body = _replace_outside_urls(body, mapping)
    if config.normalize_separator_width:
        body = re.sub(r"([,;:])\s+", r"\1 ", body)
    if _ends_with_chinese_period(body):
        body = body.rstrip()[:-1] + "."
    return body


# ---------------------------------------------------------------------------
# W112: the ideographic comma is not a bibliographic separator
# ---------------------------------------------------------------------------

_IDEOGRAPHIC_COMMA_RE = re.compile(r"\s*、\s*")


def _normalize_ideographic_comma(seg: str, config: Config) -> str:
    """Replace "、" between authors with a comma.

    Clause 6.2 prescribes "," between responsible parties, so the ideographic
    comma is unambiguously wrong here. Its width follows the chosen style; a
    segment written with "、" is Chinese-punctuated, hence the full-width
    comma by default. Titles may legitimately contain "、" and are untouched.
    """
    if not seg or "、" not in seg:
        return seg
    return _IDEOGRAPHIC_COMMA_RE.sub(", " if config.normalize_separator_width else "，", seg)


def check_ideographic_comma(entry: Entry, config: Config = DEFAULT_CONFIG) -> list[Issue]:
    seg = authors_segment(entry.body)
    fixed = _normalize_ideographic_comma(seg, config)
    if fixed == seg:
        return []
    return [
        _issue(
            entry,
            "W112",
            "warning",
            "著者之间应使用逗号分隔，不应使用顿号“、”",
            fixable=True,
            before=seg,
            after=fixed,
        )
    ]


def fix_ideographic_comma(body: str, config: Config = DEFAULT_CONFIG) -> str:
    seg = authors_segment(body)
    fixed = _normalize_ideographic_comma(seg, config)
    return body if fixed == seg else fixed + body[len(seg) :]


# ---------------------------------------------------------------------------
# W110: 等 / et al. must match the entry language
# ---------------------------------------------------------------------------

_ET_AL_WORD_RE = re.compile(r"et\s+al\.?", re.IGNORECASE)


def _normalize_etal_language(seg: str) -> str:
    """Swap 等 and "et al" to match the language, keeping the user's separator."""
    if not seg:
        return seg
    if _is_cjk_segment(seg):
        if _ET_AL_WORD_RE.search(seg):
            return _ET_AL_WORD_RE.sub("等", seg)
    elif "等" in seg:
        sep = _detect_separator(seg.replace("等", ""))
        return re.sub(r"\s*[,，]?\s*等", sep + "et al", seg)
    return seg


def check_etal_language(entry: Entry) -> list[Issue]:
    seg = authors_segment(entry.body)
    fixed = _normalize_etal_language(seg)
    if fixed == seg:
        return []
    message = (
        "中文文献的著者省略应使用“等”而非“et al.”"
        if _is_cjk_segment(seg)
        else "外文文献的著者省略应使用“et al.”而非“等”"
    )
    return [_issue(entry, "W110", "warning", message, fixable=True, before=seg, after=fixed)]


def fix_etal_language(body: str) -> str:
    seg = authors_segment(body)
    fixed = _normalize_etal_language(seg)
    return body if fixed == seg else fixed + body[len(seg) :]


# ---------------------------------------------------------------------------
# W111: no space between the title and the document type marker
# ---------------------------------------------------------------------------

_SPACE_BEFORE_TYPE_RE = re.compile(
    r"[ \t\u3000]+(?=[\[［]\s*[A-Za-z]{1,2}\s*(?:/\s*[A-Za-z]{2})?\s*[\]］])"
)


def check_space_before_type(entry: Entry) -> list[Issue]:
    if fix_space_before_type(entry.body) != entry.body:
        return [
            _issue(
                entry,
                "W111",
                "warning",
                "文献类型标识应紧跟题名，之间不应有空格（如“标题 [J]”应为“标题[J]”）",
                fixable=True,
            )
        ]
    return []


def fix_space_before_type(body: str) -> str:
    masked = mask_protected(body)
    out = []
    last = 0
    for m in _SPACE_BEFORE_TYPE_RE.finditer(masked):
        out.append(body[last : m.start()])
        last = m.end()
    out.append(body[last:])
    return "".join(out)


# ---------------------------------------------------------------------------
# W109: entries end with a period (unless ending with a URL/DOI)
# ---------------------------------------------------------------------------

def _needs_trailing_period(body: str) -> bool:
    stripped = body.rstrip()
    if not stripped or stripped.endswith((".", "。", "．")):
        return False
    tail = stripped.split()[-1]
    return not (URL_RE.search(tail) or DOI_RE.search(tail))


def check_trailing_period(entry: Entry) -> list[Issue]:
    if not _needs_trailing_period(entry.body):
        return []
    tail = entry.body.rstrip()[-12:]
    return [
        _issue(
            entry,
            "W109",
            "warning",
            "条目结尾缺少句点“.”",
            fixable=True,
            before=tail,
            after=tail + ".",
        )
    ]


def fix_trailing_period(body: str) -> str:
    return body.rstrip() + "." if _needs_trailing_period(body) else body


# ---------------------------------------------------------------------------
# W108 (list-level): numbering must be continuous
# ---------------------------------------------------------------------------

def check_numbering(entries: list[Entry]) -> list[Issue]:
    numbered = [e for e in entries if e.kind == "entry" and e.number is not None]
    if len(numbered) < 2:
        return []
    issues = []
    expected = numbered[0].number
    seen: set = set()
    for e in numbered:
        if e.number in seen:
            issues.append(_issue(e, "W108", "warning", f"序号 {e.number} 重复"))
        elif e.number != expected:
            issues.append(
                _issue(
                    e,
                    "W108",
                    "warning",
                    f"序号不连续：期望 [{expected}]，实际 [{e.number}]",
                )
            )
            expected = e.number
        seen.add(e.number)
        expected += 1
    return issues


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _with_config(func: Callable) -> Callable:
    """Adapt a rule that ignores the config to the two-argument protocol."""

    def wrapper(target, config: Config = DEFAULT_CONFIG):
        return func(target)

    wrapper.__name__ = func.__name__
    return wrapper


# Checks and fixes are all called as ``f(target, config)``.
ENTRY_CHECKS: list[Callable] = [
    _with_config(check_missing_type),
    _with_config(check_unknown_type),
    _with_config(check_surname_case),
    check_et_al_role,
    _with_config(check_cited_date),
    _with_config(check_author_count),
    check_date_format,
    check_fullwidth_punct,
    check_ideographic_comma,
    _with_config(check_etal_language),
    _with_config(check_space_before_type),
    _with_config(check_trailing_period),
]

# Applied in order; punctuation first so later rules see normalised text
ENTRY_FIXES: list[Callable] = [
    fix_fullwidth_punct,
    fix_ideographic_comma,
    _with_config(fix_space_before_type),
    _with_config(fix_type_case),
    _with_config(fix_surname_case),
    fix_et_al_role,
    _with_config(fix_author_count),
    _with_config(fix_etal_language),
    fix_date_format,
    _with_config(fix_cited_date),
    _with_config(fix_trailing_period),
]

# Which fix repairs which rule. Used to verify that a rule's advertised
# replacement is what its own fix produces.
RULE_FIXES: dict = {
    "E002": _with_config(fix_type_case),
    "W101": _with_config(fix_surname_case),
    "W102": fix_et_al_role,
    "W103": _with_config(fix_cited_date),
    "W105": _with_config(fix_author_count),
    "W106": fix_date_format,
    "W107": fix_fullwidth_punct,
    "W109": _with_config(fix_trailing_period),
    "W110": _with_config(fix_etal_language),
    "W111": _with_config(fix_space_before_type),
    "W112": fix_ideographic_comma,
}

ALL_RULE_IDS = (
    "E001", "E002",
    "W101", "W102", "W103", "W104", "W105", "W106",
    "W107", "W108", "W109", "W110", "W111", "W112",
)
