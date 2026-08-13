from gbt7714_lint.parser import (
    authors_segment,
    mask_protected,
    parse_bibliography,
    split_authors,
)


def test_mask_preserves_length_and_hides_urls():
    body = "见 https://example.com/a.html 结束"
    masked = mask_protected(body)
    assert len(masked) == len(body)
    assert "example" not in masked
    assert masked.startswith("见 ") and masked.endswith(" 结束")


def test_parse_numbered_entries():
    text = "[1] 张三. 标题[J]. 学报, 2020.\n[2] 李四. 标题2[M]. 出版社, 2021.\n"
    entries = parse_bibliography(text)
    assert len(entries) == 2
    assert entries[0].number == 1
    assert entries[0].label == "[1]"
    assert entries[0].body.startswith("张三")
    assert entries[1].line_no == 2


def test_parse_alternative_numbering_styles():
    text = "1. 张三. 标题[J]. 学报, 2020.\n（2）李四. 标题[M]. 出版社, 2021.\n【3】王五. 标题[D]. 大学, 2022.\n"
    entries = parse_bibliography(text)
    assert [e.number for e in entries] == [1, 2, 3]


def test_wrapped_entry_joined():
    text = "[1] 张三. 一个很长的标题\n    跨行了[J]. 学报, 2020.\n[2] 李四. 标题[M]. 出版社, 2021.\n"
    entries = parse_bibliography(text)
    assert len(entries) == 2
    assert "跨行了[J]" in entries[0].body


def test_unnumbered_lines_are_entries():
    text = "张三. 标题[J]. 学报, 2020.\n李四. 标题[M]. 出版社, 2021.\n"
    entries = parse_bibliography(text)
    assert len(entries) == 2
    assert entries[0].number is None


def test_blank_lines_ignored():
    text = "[1] 张三. 标题[J]. 学报, 2020.\n\n[2] 李四. 标题[M]. 出版社, 2021.\n"
    assert len(parse_bibliography(text)) == 2


def test_authors_segment_and_split():
    body = "张三,李四,王五. 标题[J]. 学报, 2020."
    seg = authors_segment(body)
    assert seg == "张三,李四,王五"
    assert split_authors(seg) == ["张三", "李四", "王五"]


def test_authors_segment_empty_when_no_authors():
    body = "某标题[EB/OL]. https://example.com."
    assert authors_segment(body) == ""


def test_authors_segment_survives_dotted_initials():
    body = "Smith J.A., Brown K. A study of things[J]. Nature, 2021, 590(1): 1-9."
    seg = authors_segment(body)
    assert seg == "Smith J.A., Brown K"
    assert len(split_authors(seg)) == 2


def test_authors_segment_spaced_initials():
    body = "Smith J. A., Brown K. Title[J]. Journal, 2021."
    assert authors_segment(body) == "Smith J. A., Brown K"


def test_authors_segment_stops_at_last_initial():
    body = "Einstein A. Relativity: the special and the general theory[M]. Crown, 1961."
    assert authors_segment(body) == "Einstein A"


def test_authors_segment_ignores_periods_inside_urls():
    body = "某作者. 页面[EB/OL]. https://a.b.c/x.html"
    assert authors_segment(body) == "某作者"


def test_heading_line_is_not_an_entry():
    text = "参考文献\n[1] 张三. 标题[J]. 学报, 2020.\n"
    items = parse_bibliography(text)
    assert items[0].kind == "heading"
    assert items[1].kind == "entry"


def test_english_heading_recognised():
    for heading in ("References", "REFERENCES:", "Bibliography"):
        items = parse_bibliography(f"{heading}\n[1] A. B[J]. C, 2020.\n")
        assert items[0].kind == "heading", heading


def test_title_looking_like_heading_word_is_still_an_entry():
    text = "[1] 张三. 参考文献著录研究[J]. 学报, 2020.\n"
    assert parse_bibliography(text)[0].kind == "entry"


def test_blank_lines_recorded():
    text = "[1] 张三. 标题[J]. 学报, 2020.\n\n\n[2] 李四. 标题[M]. 出版社, 2021.\n"
    items = parse_bibliography(text)
    assert items[1].leading_blanks == 2
