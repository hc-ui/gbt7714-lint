import json

from gbt7714_lint.cli import main
from gbt7714_lint.linter import fix_text, lint_text

SAMPLE = (
    "[1] EINSTEIN A. Relativity: the special and the general theory[M]. New York: Crown, 1961.\n"
    "[2] 张三，李四，王五，赵六. 某领域研究进展[J]. 某学报, 2020, 12(3): 45-50。\n"
    "[3] 皮亚杰. 结构主义[M]. 倪连生, 王琳, 等译. 北京: 商务印书馆, 1984.\n"
    "[4] 王芳. 某在线报告[EB/OL]. [2024.5.6]. https://example.com/report.\n"
)


def test_lint_text_finds_expected_rules():
    result = lint_text(SAMPLE)
    rule_ids = {i.rule_id for i in result.issues}
    assert {"W101", "W102", "W105", "W106", "W107"} <= rule_ids
    assert result.error_count == 0


def test_fix_text_resolves_fixable_issues():
    fixed, remaining = fix_text(SAMPLE)
    assert "Einstein A." in fixed
    assert "张三,李四,王五,等" in fixed
    assert "等，译" in fixed
    assert "[2024-05-06]" in fixed
    assert "。" not in fixed
    fixable_rules = {"W101", "W102", "W105", "W106", "W107"}
    assert not [i for i in remaining.issues if i.rule_id in fixable_rules]


def test_cli_lint_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.txt"
    good.write_text("[1] 张三. 标题[J]. 学报, 2020, 1(2): 3-4.\n", encoding="utf-8")
    assert main([str(good)]) == 0

    bad = tmp_path / "bad.txt"
    bad.write_text("[1] 张三. 标题. 学报, 2020.\n", encoding="utf-8")
    assert main([str(bad)]) == 1
    out = capsys.readouterr().out
    assert "E001" in out


def test_cli_json_output(tmp_path, capsys):
    f = tmp_path / "refs.txt"
    f.write_text(SAMPLE, encoding="utf-8")
    assert main([str(f), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"] == 4
    assert payload["warnings"] > 0


def test_cli_fix_writes_output(tmp_path, capsys):
    src = tmp_path / "refs.txt"
    src.write_text(SAMPLE, encoding="utf-8")
    dst = tmp_path / "fixed.txt"
    assert main([str(src), "--fix", "-o", str(dst)]) == 0
    fixed = dst.read_text(encoding="utf-8")
    assert "Einstein A." in fixed


def test_cli_reads_gbk_file(tmp_path):
    f = tmp_path / "gbk.txt"
    f.write_bytes("[1] 张三. 标题[J]. 学报, 2020, 1(2): 3-4.\n".encode("gbk"))
    assert main([str(f)]) == 0
