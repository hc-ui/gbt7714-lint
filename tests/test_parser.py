from gbt7714_lint.parser import authors_segment, parse_bibliography, split_authors


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
