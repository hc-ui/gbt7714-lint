"""Configuration for punctuation conventions.

GB/T 7714—2025 clause 6.2 lists the bibliographic separators but never says
whether they are half-width or full-width. From the examples, ``.`` ``[ ]``
``/`` and ``-`` are half-width, while ``,`` ``:`` ``;`` and ``( )`` appear
full-width in Chinese-language entries. Journals and universities follow at
least four different conventions, so the width of those ambiguous symbols is
not enforced unless the user opts in.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Do not touch the width of ambiguous separators (default).
PUNCT_KEEP = "keep"
#: Force every separator to half-width plus a space, the convention used by
#: many university thesis guidelines.
PUNCT_HALF = "half"

PUNCT_STYLES = (PUNCT_KEEP, PUNCT_HALF)


@dataclass(frozen=True)
class Config:
    punct: str = PUNCT_KEEP

    def __post_init__(self) -> None:
        if self.punct not in PUNCT_STYLES:
            raise ValueError(f"未知的标点风格：{self.punct}；可选：{'、'.join(PUNCT_STYLES)}")

    @property
    def normalize_separator_width(self) -> bool:
        return self.punct == PUNCT_HALF


DEFAULT_CONFIG = Config()
