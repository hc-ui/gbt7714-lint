from gbt7714_lint.config import Config
from gbt7714_lint.linter import fix_entry_body, lint_text
from gbt7714_lint.models import Entry
from gbt7714_lint.rules import (
    check_author_count,
    check_cited_date,
    check_date_format,
    check_et_al_role,
    check_etal_language,
    check_fullwidth_punct,
    check_ideographic_comma,
    check_missing_type,
    check_numbering,
    check_space_before_type,
    check_surname_case,
    check_trailing_period,
    check_unknown_type,
    fix_author_count,
    fix_cited_date,
    fix_date_format,
    fix_et_al_role,
    fix_etal_language,
    fix_fullwidth_punct,
    fix_ideographic_comma,
    fix_space_before_type,
    fix_surname_case,
    fix_type_case,
)


def entry(body: str) -> Entry:
    return Entry(raw=body, body=body, line_no=1, label="[1]", number=1)


# E001 -----------------------------------------------------------------

def test_missing_type_marker():
    issues = check_missing_type(entry("张三. 标题. 学报, 2020."))
    assert issues and issues[0].rule_id == "E001"


def test_type_marker_present():
    assert check_missing_type(entry("张三. 标题[J]. 学报, 2020.")) == []


def test_date_bracket_not_mistaken_for_type():
    issues = check_missing_type(entry("张三. 标题. 学报, 2020[2024-05-06]."))
    assert issues and issues[0].rule_id == "E001"


# E002 -----------------------------------------------------------------

def test_unknown_type_code():
    issues = check_unknown_type(entry("张三. 标题[X]. 学报, 2020."))
    assert issues and issues[0].rule_id == "E002" and not issues[0].fixable


def test_lowercase_type_fixable():
    issues = check_unknown_type(entry("张三. 标题[j]. 学报, 2020."))
    assert issues and issues[0].fixable
    assert fix_type_case("张三. 标题[j]. 学报, 2020.") == "张三. 标题[J]. 学报, 2020."


def test_new_2025_types_accepted():
    for code in ("PP", "DS", "A"):
        assert check_unknown_type(entry(f"某某. 标题[{code}]. 来源, 2026.")) == []


def test_lowercase_carrier_fixable():
    body = "张三. 标题[EB/ol]. (2026-01-01)[2026-08-01]. https://example.com."
    assert "[EB/OL]" in fix_type_case(body)


def test_marker_reported_as_a_whole_unit():
    """The reported text must be findable in the user's document."""
    issues = check_unknown_type(entry("赵敏. 某数据集[ds/ol]. [2025-01-01]. https://e.org/d"))
    assert len(issues) == 1
    assert issues[0].before == "[ds/ol]"
    assert issues[0].after == "[DS/OL]"


def test_unknown_carrier_not_reported_as_case_problem():
    issues = check_unknown_type(entry("张三. 标题[J/zz]. 学报, 2020."))
    assert len(issues) == 1
    assert not issues[0].fixable


# W101 -----------------------------------------------------------------

def test_foreign_allcaps_surname_flagged_and_fixed():
    body = "EINSTEIN A. Relativity[M]. New York: Crown, 1961."
    issues = check_surname_case(entry(body))
    assert issues and issues[0].fixable
    assert fix_surname_case(body).startswith("Einstein A.")


def test_pinyin_surname_kept_allcaps():
    body = "ZHANG S Q, LI M. Some title[J]. Journal, 2020, 1(2): 3-4."
    assert check_surname_case(entry(body)) == []


def test_mixed_authors_only_foreign_fixed():
    body = "SMITH J, ZHANG W. Title[J]. Journal, 2021, 2(3): 10-20."
    fixed = fix_surname_case(body)
    assert fixed.startswith("Smith J, ZHANG W.")


def test_organisation_author_kept_uppercase():
    for org in ("WHO", "UNESCO", "IEEE", "OECD", "CNNIC"):
        body = f"{org}. Some official report[R]. Geneva: {org}, 2024."
        assert check_surname_case(entry(body)) == []
        assert fix_surname_case(body).startswith(f"{org}.")


def test_unknown_lone_acronym_treated_as_organisation():
    body = "ZZZTOP. Annual report[R]. Somewhere: ZZZTOP, 2024."
    assert fix_surname_case(body).startswith("ZZZTOP.")


def test_generational_suffix_not_mangled():
    body = "SMITH J III. Legacy systems[M]. Boston: Addison, 1999."
    assert fix_surname_case(body).startswith("Smith J III.")


def test_jr_suffix_preserved():
    body = "BROWN K JR. A book[M]. New York: Norton, 2001."
    assert fix_surname_case(body).startswith("Brown K JR.")


# W102 -----------------------------------------------------------------

def test_et_al_translator_comma():
    body = "皮亚杰. 结构主义[M]. 倪连生, 王琳, 等译. 北京: 商务印书馆, 1984."
    issues = check_et_al_role(entry(body))
    assert issues and issues[0].fixable
    assert "等，译" in fix_et_al_role(body)


def test_et_al_role_already_correct():
    body = "皮亚杰. 结构主义[M]. 倪连生, 等，译. 北京: 商务印书馆, 1984."
    assert check_et_al_role(entry(body)) == []


# W103 / W104 ----------------------------------------------------------

def test_print_resource_with_cited_date():
    body = "李强. 计算机应用[M]. 北京: 高教出版社, 2019[2024-05-06]."
    issues = check_cited_date(entry(body))
    assert issues and issues[0].rule_id == "W103"
    fixed = fix_cited_date(body)
    assert "[2024-05-06]" not in fixed
    assert fixed.endswith("2019.")


def test_online_resource_missing_cited_date():
    body = "王芳. 某报告[EB/OL]. https://example.com/report"
    issues = check_cited_date(entry(body))
    assert issues and issues[0].rule_id == "W104"


def test_online_resource_with_cited_date_ok():
    body = "王芳. 某报告[EB/OL]. [2026-08-01]. https://example.com/report."
    assert check_cited_date(entry(body)) == []


# W105 -----------------------------------------------------------------

def test_four_authors_truncated():
    body = "张三,李四,王五,赵六. 某研究[J]. 某学报, 2020, 12(3): 45-50."
    issues = check_author_count(entry(body))
    assert issues and issues[0].fixable
    assert fix_author_count(body).startswith("张三,李四,王五,等.")


def test_three_authors_untouched():
    body = "张三,李四,王五. 某研究[J]. 某学报, 2020, 12(3): 45-50."
    assert check_author_count(entry(body)) == []


def test_existing_et_al_untouched():
    body = "张三,李四,王五,等. 某研究[J]. 某学报, 2020, 12(3): 45-50."
    assert check_author_count(entry(body)) == []


def test_english_authors_truncated_with_et_al():
    body = "Smith J, Brown K, Lee M, Davis R. Title[J]. Journal, 2021, 2(3): 1-9."
    assert fix_author_count(body).startswith("Smith J, Brown K, Lee M, et al.")


# W106 -----------------------------------------------------------------

def test_dot_date_normalized():
    body = "王芳. 某报告[EB/OL]. [2024.5.6]. https://example.com."
    issues = check_date_format(entry(body))
    assert issues and issues[0].after == "[2024-05-06]"
    assert "[2024-05-06]" in fix_date_format(body)


def test_chinese_date_normalized():
    body = "王芳. 某报告[EB/OL]. [2024年5月6日]. https://example.com."
    assert "[2024-05-06]" in fix_date_format(body)


def test_impossible_date_left_alone():
    body = "王芳. 某报告[EB/OL]. [2024.2.30]. https://example.com."
    assert check_date_format(entry(body)) == []
    assert fix_date_format(body) == body


def test_leap_day_accepted():
    body = "国家统计局. 公报[EB/OL]. （2024.2.29）. https://example.gov.cn/x"
    assert "（2024-02-29）" in fix_date_format(body)


# W106: bracket kinds are preserved -------------------------------------

def test_paren_update_date_stays_parenthesised():
    """Only the date format is normalised; the bracket kind and width stay."""
    body = "王芳. 某报告[EB/OL]. （2024.5.6）[2024.6.1]. https://example.com."
    fixed = fix_date_format(body)
    assert "（2024-05-06）" in fixed
    assert "[2024-06-01]" in fixed


def test_half_punct_forces_halfwidth_date_brackets():
    body = "王芳. 某报告[EB/OL]. （2024.5.6）. https://example.com."
    assert "(2024-05-06)" in fix_date_format(body, Config(punct="half"))


def test_paren_date_not_removed_as_cited_date():
    # print resource with a parenthesised publish date: W103 must not fire
    body = "李强. 某图书[M]. 北京: 出版社, (2019-01-01)."
    assert check_cited_date(entry(body)) == []
    assert "(2019-01-01)" in fix_cited_date(body)


# W110 -----------------------------------------------------------------

def test_chinese_entry_with_et_al():
    body = "张三,李四,王五,et al. 某研究[J]. 某学报, 2020, 12(3): 45-50."
    issues = check_etal_language(entry(body))
    assert issues and issues[0].fixable
    assert fix_etal_language(body).startswith("张三,李四,王五,等.")


def test_english_entry_with_deng():
    body = "Smith J, Brown K, Lee M, 等. Title[J]. Journal, 2021, 2(3): 1-9."
    issues = check_etal_language(entry(body))
    assert issues and issues[0].fixable
    assert fix_etal_language(body).startswith("Smith J, Brown K, Lee M, et al.")


def test_matching_language_untouched():
    assert check_etal_language(entry("张三,李四,王五,等. 某研究[J]. 学报, 2020.")) == []
    assert check_etal_language(entry("Smith J, et al. Title[J]. Journal, 2021.")) == []


# W111 -----------------------------------------------------------------

def test_space_before_type_marker():
    body = "张三. 某研究 [J]. 某学报, 2020, 12(3): 45-50."
    issues = check_space_before_type(entry(body))
    assert issues and issues[0].fixable
    assert "某研究[J]." in fix_space_before_type(body)


def test_space_before_date_bracket_untouched():
    body = "王芳. 某报告[EB/OL]. [2026-08-01]. https://example.com."
    assert check_space_before_type(entry(body)) == []


# W107 -----------------------------------------------------------------

def test_fullwidth_author_comma_kept_by_default():
    """GB/T 7714-2025 does not settle comma width, so it is left alone."""
    body = "张三，李四. 某研究[J]. 某学报, 2020, 12(3): 45-50."
    assert check_fullwidth_punct(entry(body)) == []
    assert fix_fullwidth_punct(body) == body


def test_fullwidth_author_comma_fixed_in_half_style():
    half = Config(punct="half")
    body = "张三，李四. 某研究[J]. 某学报, 2020, 12(3): 45-50."
    assert check_fullwidth_punct(entry(body), half)
    assert fix_fullwidth_punct(body, half).startswith("张三, 李四.")


def test_english_authors_get_spaced_comma():
    body = "Smith J，Brown K. Title[J]. Journal, 2021, 2(3): 1-9."
    fixed = fix_fullwidth_punct(body, Config(punct="half"))
    assert fixed.startswith("Smith J, Brown K.")


def test_trailing_chinese_period():
    body = "张三. 某研究[J]. 某学报, 2020, 12(3): 45-50。"
    assert fix_fullwidth_punct(body).endswith("45-50.")


def test_fullwidth_dot_replaced_but_url_protected():
    body = "张三．某研究[EB/OL]．[2026-01-01]. https://example．com/x"
    fixed = fix_fullwidth_punct(body)
    assert fixed.startswith("张三.某研究[EB/OL].")
    # URL content must not be altered
    assert "https://example．com/x" in fixed


def test_fullwidth_inside_url_is_not_reported():
    """Reporting it would advertise a fix that can never be applied."""
    body = "某作者. 页面[EB/OL]. [2026-01-01]. https://example．com/路径．html"
    assert check_fullwidth_punct(entry(body)) == []
    assert fix_fullwidth_punct(body) == body


def test_fullwidth_brackets_replaced():
    body = "张三. 某研究［J］. 某学报, 2020."
    assert "[J]" in fix_fullwidth_punct(body)


# W109 -----------------------------------------------------------------

def test_missing_trailing_period():
    body = "张三. 某研究[J]. 某学报, 2020, 12(3): 45-50"
    issues = check_trailing_period(entry(body))
    assert issues and issues[0].fixable


def test_url_ending_needs_no_period():
    body = "王芳. 某报告[EB/OL]. [2026-08-01]. https://example.com/report"
    assert check_trailing_period(entry(body)) == []


# W108 -----------------------------------------------------------------

def test_numbering_gap_detected():
    text = "[1] 张三. 标题[J]. 学报, 2020.\n[3] 李四. 标题[M]. 出版社, 2021.\n"
    result = lint_text(text)
    assert any(i.rule_id == "W108" for i in result.issues)


def test_numbering_duplicate_detected():
    text = "[1] 张三. 标题[J]. 学报, 2020.\n[1] 李四. 标题[M]. 出版社, 2021.\n"
    result = lint_text(text)
    assert any("重复" in i.message for i in result.issues if i.rule_id == "W108")


def test_duplicate_number_reported_once():
    """A duplicate must not also be reported as a gap."""
    text = "[1] 张三. 标题[J]. 学报, 2020.\n[1] 李四. 标题[M]. 出版社, 2021.\n"
    w108 = [i for i in lint_text(text).issues if i.rule_id == "W108"]
    assert len(w108) == 1


def test_headings_are_not_linted():
    text = "参考文献\n[1] 张三. 标题[J]. 学报, 2020, 1(2): 3-4.\n"
    result = lint_text(text)
    assert len(result.entries) == 1
    assert not [i for i in result.issues if i.rule_id == "E001"]


# Fix pipeline ---------------------------------------------------------

def test_fix_entry_body_combined():
    body = "EINSTEIN A，NEWTON I，BOHR N，PLANCK M. Physics[m]. Berlin: Springer, 1950。"
    fixed = fix_entry_body(body)
    # Surnames, type marker and the closing period are fixed; the author's
    # own full-width separator is preserved.
    assert fixed.startswith("Einstein A，Newton I，Bohr N，et al.")
    assert "[M]" in fixed
    assert fixed.endswith(".")


def test_fix_entry_body_combined_half_style():
    body = "EINSTEIN A，NEWTON I，BOHR N，PLANCK M. Physics[m]. Berlin: Springer, 1950。"
    fixed = fix_entry_body(body, Config(punct="half"))
    assert fixed.startswith("Einstein A, Newton I, Bohr N, et al.")
    assert "，" not in fixed


def test_truncation_reuses_existing_separator():
    body = "张三, 李四, 王五, 赵六. 某研究[J]. 某学报, 2020."
    assert fix_author_count(body).startswith("张三, 李四, 王五, 等.")


# W112 -----------------------------------------------------------------

def test_ideographic_comma_between_authors():
    body = "孙杨、钱进、周涛、吴迪. 某研究[J]. 某学报, 2023."
    issues = check_ideographic_comma(entry(body))
    assert issues and issues[0].fixable
    assert fix_ideographic_comma(body).startswith("孙杨，钱进，周涛，吴迪.")


def test_ideographic_comma_half_style():
    body = "孙杨、钱进. 某研究[J]. 某学报, 2023."
    assert fix_ideographic_comma(body, Config(punct="half")).startswith("孙杨, 钱进.")


def test_ideographic_comma_in_title_untouched():
    body = "周涛. 人工智能、大数据与未来[M]. 北京: 科学出版社, 2023."
    assert check_ideographic_comma(entry(body)) == []
    assert fix_ideographic_comma(body) == body


def test_authors_split_on_ideographic_comma():
    body = "孙杨、钱进、周涛、吴迪. 某研究[J]. 某学报, 2023."
    issues = check_author_count(entry(body))
    assert issues and "共 4 人" in issues[0].message
