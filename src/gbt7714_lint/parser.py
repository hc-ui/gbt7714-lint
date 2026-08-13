"""Split pasted bibliography text into entries and extract common fields.

The input is what Chinese students actually have: a plain-text reference
list copied out of Word / WPS, one entry per line or wrapped across lines,
usually numbered ``[1]`` / ``1.`` / ``1、``.
"""

from __future__ import annotations

import re
from typing import Optional

from .models import Entry

# [1] / 【1】 / 1. / 1、 / (1) at the start of a line
_LABEL_RE = re.compile(
    r"^\s*(?:(?P<bracket>[\[［【]\s*(?P<n1>\d{1,3})\s*[\]］】])"
    r"|(?P<paren>[\(（]\s*(?P<n2>\d{1,3})\s*[\)）])"
    r"|(?P<plain>(?P<n3>\d{1,3})\s*[.、．]))\s*"
)

# A line that is only a section heading, e.g. "参考文献" or "References:"
_HEADING_RE = re.compile(
    r"^(?:参\s*考\s*文\s*献|引\s*用\s*文\s*献|参\s*考\s*书\s*目|注\s*释"
    r"|references?|bibliography|works\s+cited)\s*[:：]?\s*$",
    re.IGNORECASE,
)

# Document type / carrier marker, e.g. [J], [EB/OL], [M/OL]
TYPE_RE = re.compile(r"[\[［]\s*(?P<type>[A-Za-z]{1,2})\s*(?:/\s*(?P<carrier>[A-Za-z]{2}))?\s*[\]］]")

# GB/T 7714 distinguishes two dated marks: "(update/publish date)" in
# parentheses and "[cited date]" in square brackets. Keep them separate so
# fixes never turn one into the other.
_DATE_INNER = r"\d{4}\s*[-–—./年]\s*\d{1,2}\s*[-–—./月]\s*\d{1,2}\s*日?"
SQUARE_DATE_RE = re.compile(
    rf"(?P<open>[\[［])\s*(?P<date>{_DATE_INNER})\s*(?P<close>[\]］])"
)
PAREN_DATE_RE = re.compile(
    rf"(?P<open>[(（])\s*(?P<date>{_DATE_INNER})\s*(?P<close>[)）])"
)
# Matches either kind (read-only helpers)
DATE_BRACKET_RE = re.compile(rf"[\[［(（]\s*(?P<date>{_DATE_INNER})\s*[\]］)）]")

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
DOI_RE = re.compile(r"\bDOI\s*[:：]\s*\S+|\bdoi\.org/\S+", re.IGNORECASE)

# Placeholder used by :func:`mask_protected`; cannot occur in real input.
MASK_CHAR = "\x00"

# GB/T 7714-2025 Appendix A document types
VALID_TYPES = {
    "A": "档案",
    "C": "会议录",
    "CM": "地图",
    "CP": "计算机程序",
    "D": "学位论文",
    "DB": "数据库",
    "DS": "数据集",
    "EB": "网站、网页",
    "G": "汇编",
    "J": "期刊",
    "M": "图书",
    "N": "报纸",
    "P": "专利",
    "PP": "预印本",
    "R": "报告",
    "S": "标准",
    "Z": "其他",
}

# GB/T 7714-2025 Appendix A electronic-resource carriers
VALID_CARRIERS = {
    "CD": "光盘",
    "DK": "磁盘",
    "MT": "磁带",
    "MM": "缩微资料",
    "OL": "联机网络",
}


def mask_protected(body: str) -> str:
    """Return ``body`` with URL and DOI spans blanked to :data:`MASK_CHAR`.

    Length and indices are preserved, so a rule can search the masked string
    and slice the original with the same offsets. Checks and fixes both go
    through this, which is what keeps them from disagreeing about whether a
    character inside a URL is a bibliographic separator.
    """
    if not body:
        return body
    chars = list(body)
    for regex in (URL_RE, DOI_RE):
        for m in regex.finditer(body):
            for i in range(m.start(), m.end()):
                chars[i] = MASK_CHAR
    return "".join(chars)


def parse_bibliography(text: str) -> list[Entry]:
    """Parse pasted text into entries.

    Lines starting with a numbering label begin a new entry; continuation
    lines are appended to the previous entry. Without labels, every
    non-empty line is one entry. Section headings are kept as items so that
    ``--fix`` can echo them back untouched instead of dropping them.
    """
    lines = text.splitlines()
    has_labels = any(_LABEL_RE.match(ln) for ln in lines if ln.strip())

    entries: list[Entry] = []
    pending_blanks = 0
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            pending_blanks += 1
            continue

        if _HEADING_RE.match(line.strip()):
            entries.append(
                Entry(
                    raw=line.rstrip(),
                    body=line.strip(),
                    line_no=idx,
                    kind="heading",
                    leading_blanks=pending_blanks,
                )
            )
            pending_blanks = 0
            continue

        m = _LABEL_RE.match(line)
        if has_labels and not m and entries and entries[-1].kind == "entry":
            prev = entries[-1]
            prev.raw += " " + line.strip()
            prev.body += " " + line.strip()
            continue

        if m:
            number = int(m.group("n1") or m.group("n2") or m.group("n3"))
            label = line[m.start() : m.end()].strip()
            body = line[m.end() :].strip()
            entries.append(
                Entry(
                    raw=line.strip(),
                    body=body,
                    line_no=idx,
                    label=label,
                    number=number,
                    leading_blanks=pending_blanks,
                )
            )
        else:
            entries.append(
                Entry(
                    raw=line.strip(),
                    body=line.strip(),
                    line_no=idx,
                    leading_blanks=pending_blanks,
                )
            )
        pending_blanks = 0
    return entries


def find_type_marker(body: str) -> Optional[re.Match]:
    """Return the first document-type marker outside URLs, if any."""
    masked = mask_protected(body)
    for m in TYPE_RE.finditer(masked):
        return m
    return None


_TERMINATORS = ".。．"


def _looks_like_initial_period(masked: str, i: int) -> bool:
    """True if the period at ``i`` belongs to an initial such as ``J.A.``.

    ``Smith J.A., Brown K. Title`` must not have its author segment cut at
    the first period, while ``Einstein A. Relativity`` must.
    """
    if masked[i] != ".":
        return False
    if i == 0:
        return False
    prev = masked[i - 1]
    if not (prev.isascii() and prev.isupper()):
        return False
    # The letter must stand alone (an initial), not end a word like "USA."
    if i >= 2 and masked[i - 2].isalpha():
        return False
    rest = masked[i + 1 :].lstrip(" \t")
    if not rest:
        return False
    if rest[0] in ",，":
        return True
    # Another initial directly follows, e.g. "J.A." or "J. A."
    return len(rest) >= 2 and rest[0].isascii() and rest[0].isupper() and rest[1] == "."


def authors_segment(body: str) -> str:
    """Return the author segment (text before the terminating period).

    GB/T 7714 places a ``.`` after the author group. Periods that are part of
    an initial are skipped. An entry whose leading segment already contains a
    type marker has no author group (anonymous work) and yields ``""``.
    """
    masked = mask_protected(body)
    end = len(masked)
    for i, ch in enumerate(masked):
        if ch in _TERMINATORS and not _looks_like_initial_period(masked, i):
            end = i
            break
    seg = body[:end]
    if TYPE_RE.search(masked[:end]):
        return ""
    return seg


def split_authors(segment: str) -> list[str]:
    """Split an author segment into individual names.

    The ideographic comma is included because Chinese authors habitually
    write "张三、李四" even though the standard prescribes a comma.
    """
    parts = re.split(r"[,，;；、]", segment)
    return [p.strip() for p in parts if p.strip()]
