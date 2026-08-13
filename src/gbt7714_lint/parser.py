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

# Document type / carrier marker, e.g. [J], [EB/OL], [M/OL]
TYPE_RE = re.compile(r"[\[［]\s*(?P<type>[A-Za-z]{1,2})\s*(?:/\s*(?P<carrier>[A-Za-z]{2}))?\s*[\]］]")

# A cited/updated date bracket, e.g. [2024-05-06] or [2024.5.6] or （2024-05-06）
DATE_BRACKET_RE = re.compile(
    r"[\[［(（]\s*(?P<date>\d{4}\s*[-–—./年]\s*\d{1,2}\s*[-–—./月]\s*\d{1,2}\s*日?)\s*[\]］)）]"
)

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
DOI_RE = re.compile(r"\bDOI\s*[:：]\s*\S+|\bdoi\.org/\S+", re.IGNORECASE)

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


def parse_bibliography(text: str) -> list[Entry]:
    """Parse pasted text into entries.

    Lines starting with a numbering label begin a new entry; continuation
    lines are appended to the previous entry. Without labels, every
    non-empty line is one entry.
    """
    lines = text.splitlines()
    has_labels = any(_LABEL_RE.match(ln) for ln in lines if ln.strip())

    entries: list[Entry] = []
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        m = _LABEL_RE.match(line)
        if has_labels and not m and entries:
            # wrapped continuation of the previous entry
            prev = entries[-1]
            prev.raw += " " + line.strip()
            prev.body += " " + line.strip()
            continue
        if m:
            number = int(m.group("n1") or m.group("n2") or m.group("n3"))
            label = line[m.start() : m.end()].strip()
            body = line[m.end() :].strip()
            entries.append(Entry(raw=line.strip(), body=body, line_no=idx, label=label, number=number))
        else:
            entries.append(Entry(raw=line.strip(), body=line.strip(), line_no=idx))
    return entries


def find_type_marker(body: str) -> Optional[re.Match]:
    """Return the match for the document-type marker, skipping date brackets."""
    for m in TYPE_RE.finditer(body):
        return m
    return None


def authors_segment(body: str) -> str:
    """Heuristically return the author segment (text before the first period).

    GB/T 7714 puts a ``.`` after the author group and does not use periods
    inside names, so the first period reliably ends the segment.
    """
    m = re.search(r"[.。．]", body)
    seg = body[: m.start()] if m else body
    # An entry may legitimately start with a title (anonymous works); if the
    # segment already contains the type marker it is not an author segment.
    if TYPE_RE.search(seg):
        return ""
    return seg


def split_authors(segment: str) -> list[str]:
    """Split an author segment into individual names."""
    parts = re.split(r"[,，;；]", segment)
    return [p.strip() for p in parts if p.strip()]
