"""Invariants every rule must satisfy, checked over a messy corpus.

These catch the class of bug where a check advertises "可自动修复" but the
corresponding fix declines to touch the text, which would make ``--fix``
report the same warning forever.
"""

import pytest

from gbt7714_lint.config import Config
from gbt7714_lint.linter import fix_entry_body, fix_text, lint_text
from gbt7714_lint.parser import URL_RE
from gbt7714_lint.rules import RULE_FIXES

CORPUS = [
    # 2015-style foreign surname
    "[1] EINSTEIN A. Relativity: the special and the general theory[M]. New York: Crown, 1961.",
    # full-width separators, four authors, Chinese full stop
    "[2] 张三，李四，王五，赵六. 深度学习综述[J]. 计算机学报，2020, 43(3): 45-58。",
    # translator role word
    "[3] 皮亚杰. 结构主义[M]. 倪连生, 王琳, 等译. 北京: 商务印书馆, 1984.",
    # cited date on a print resource
    "[4] 李强. 数据库系统概论[M]. 北京: 高等教育出版社, 2019[2024-05-06].",
    # dotted date, online resource
    "[5] 王芳. 人工智能白皮书[EB/OL]. [2024.5.6]. https://example.com/report",
    # pinyin surnames, already correct
    "[6] ZHANG S Q, LI M, WANG H. Survey on LLMs[J]. Journal of Software, 2025, 36(2): 1-20.",
    # organisation as author
    "[7] WHO. World health statistics 2024[R]. Geneva: WHO, 2024.",
    "[8] UNESCO. Global education monitoring report[R]. Paris: UNESCO, 2023.",
    # organisation acronym alongside other text
    "[9] IEEE. IEEE standard for floating-point arithmetic[S]. New York: IEEE, 2019.",
    # initials written with periods
    "[10] Smith J.A., Brown K. A study of things[J]. Nature, 2021, 590(1): 1-9.",
    # language mismatch, both directions
    "[11] 张三,李四,王五,et al. 某研究[J]. 某学报, 2020, 12(3): 45-50.",
    "[12] Smith J, Brown K, Lee M, 等. Another title[J]. Science, 2022, 3(4): 5-6.",
    # space before type marker, missing trailing period
    "[13] 陈明. 某个题名 [J]. 某学报, 2021, 5(2): 10-15",
    # full-width brackets and period
    "[14] 刘伟．某研究［J］．某学报, 2022, 6(1): 1-8.",
    # parenthesised update date plus cited date
    "[15] 国家统计局. 统计公报[EB/OL]. （2024.2.29）[2024.3.1]. https://example.gov.cn/x.html",
    # generational suffix
    "[16] SMITH J III. Legacy systems[M]. Boston: Addison, 1999.",
    # lowercase type and carrier
    "[17] 赵敏. 某数据集[ds/ol]. [2025-01-01]. https://example.org/data",
    # anonymous work, no author group
    "[18] 中国互联网络发展状况统计报告[R]. 北京: CNNIC, 2024.",
    # url containing a full-width character must never be rewritten
    "[19] 某作者. 某页面[EB/OL]. [2026-01-01]. https://example．com/路径．html",
    # ideographic comma between authors
    "[20] 孙杨、钱进、周涛、吴迪. 某某研究[J]. 某学报, 2023, 72(1): 1-12.",
    # ideographic comma inside a title must survive
    "[21] 周涛. 人工智能、大数据与未来[M]. 北京: 科学出版社, 2023.",
    # already perfect entry
    "[22] 周涛. 复杂网络研究[J]. 物理学报, 2023, 72(1): 1-12.",
]

CORPUS_TEXT = "\n".join(CORPUS) + "\n"

CONFIGS = [Config(punct="keep"), Config(punct="half")]
CONFIG_IDS = ["keep", "half"]


@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("entry", CORPUS)
def test_fix_is_idempotent(entry, config):
    body = entry.split("] ", 1)[1]
    once = fix_entry_body(body, config)
    assert fix_entry_body(once, config) == once


@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("entry", CORPUS)
def test_no_fixable_issue_survives_fix(entry, config):
    """After --fix, nothing may still be advertised as auto-fixable."""
    _, remaining = fix_text(entry + "\n", config)
    leftover = [i for i in remaining.issues if i.fixable]
    assert not leftover, [f"{i.rule_id}: {i.message}" for i in leftover]


@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("entry", CORPUS)
def test_urls_are_never_rewritten(entry, config):
    body = entry.split("] ", 1)[1]
    before = URL_RE.findall(body)
    after = URL_RE.findall(fix_entry_body(body, config))
    assert before == after


@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
@pytest.mark.parametrize("entry", CORPUS)
def test_reported_replacement_matches_own_fix_per_style(entry, config):
    body = entry.split("] ", 1)[1]
    for issue in lint_text(entry + "\n", config).issues:
        if not (issue.fixable and issue.after):
            continue
        fix = RULE_FIXES[issue.rule_id]
        assert issue.after in fix(body, config)


@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
def test_whole_corpus_converges(config):
    fixed, remaining = fix_text(CORPUS_TEXT, config)
    assert not [i for i in remaining.issues if i.fixable]
    refixed, _ = fix_text(fixed, config)
    assert refixed == fixed


@pytest.mark.parametrize("config", CONFIGS, ids=CONFIG_IDS)
def test_fix_preserves_entry_count(config):
    fixed, _ = fix_text(CORPUS_TEXT, config)
    assert len(lint_text(fixed, config).entries) == len(CORPUS)


@pytest.mark.parametrize("entry", CORPUS)
def test_default_style_never_changes_separator_width(entry):
    """The default must not switch the author between the two conventions."""
    body = entry.split("] ", 1)[1]
    if "、" in body:
        return  # W112 legitimately introduces a comma
    fixed = fix_entry_body(body)
    for ch in "，；：（）":
        # 等，译 is added by W102 and is the one deliberate exception
        if ch == "，" and "等，" in fixed:
            continue
        assert body.count(ch) == fixed.count(ch), ch


def test_ideographic_comma_in_title_is_untouched():
    body = "周涛. 人工智能、大数据与未来[M]. 北京: 科学出版社, 2023."
    assert fix_entry_body(body) == body


def test_reported_replacement_matches_own_fix():
    """A rule's advertised replacement must be what its own fix produces."""
    for entry_text in CORPUS:
        body = entry_text.split("] ", 1)[1]
        for issue in lint_text(entry_text + "\n").issues:
            if not (issue.fixable and issue.after):
                continue
            fix = RULE_FIXES.get(issue.rule_id)
            assert fix is not None, f"{issue.rule_id} is fixable but has no fix"
            assert issue.after in fix(body), (
                f"{issue.rule_id} suggested {issue.after!r} "
                f"but its fix produced {fix(body)!r}"
            )


def test_every_fixable_rule_has_a_registered_fix():
    seen = set()
    for entry_text in CORPUS:
        for issue in lint_text(entry_text + "\n").issues:
            if issue.fixable:
                seen.add(issue.rule_id)
    assert seen, "corpus triggered no fixable rule"
    assert seen <= set(RULE_FIXES), seen - set(RULE_FIXES)
