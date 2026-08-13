# gbt7714-lint

[![CI](https://github.com/hc-ui/gbt7714-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/hc-ui/gbt7714-lint/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gbt7714-lint)](https://pypi.org/project/gbt7714-lint/)
[![Python](https://img.shields.io/pypi/pyversions/gbt7714-lint)](https://pypi.org/project/gbt7714-lint/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**参考文献格式检查与自动修复工具，面向 GB/T 7714—2025 新国标。**

**[在线试用（免安装）→ hc-ui.github.io/gbt7714-lint](https://hc-ui.github.io/gbt7714-lint/)** — 粘贴即查，纯浏览器本地运行，数据不上传。

A linter and auto-fixer for plain-text bibliographies under **GB/T 7714—2025**, the new Chinese national standard for bibliographic references that took effect on **July 1, 2026**, replacing GB/T 7714—2015. Paste the reference list from your thesis, get a rule-by-rule report, and let `--fix` migrate the mechanical parts automatically. Zero dependencies, works offline. [Try it in your browser](https://hc-ui.github.io/gbt7714-lint/) — no install needed.

![在线 Demo：逐条指出格式问题并给出修复对照](assets/demo-screenshot.png)

## 为什么需要它

GB/T 7714—2025 已于 2026 年 7 月 1 日实施，高校学位论文和期刊投稿都在陆续切换新国标。但你手里的参考文献往往是 Word 里的一段**纯文本**——BibTeX 转换器、LaTeX 宏包、Zotero CSL 样式都帮不上忙。

`gbt7714-lint` 直接检查纯文本参考文献列表，逐条指出不符合 2025 新国标的地方，并自动修复其中机械性的部分，例如：

- 外文作者姓氏 `EINSTEIN A`（2015 版写法）→ `Einstein A`（2025 版），汉语拼音姓氏 `ZHANG S Q` 正确保留全大写
- `倪连生, 王琳, 等译` → `倪连生, 王琳, 等，译`（2025 版其他责任者新增逗号）
- 纸质文献误标引用日期 `2019[2024-05-06]` → `2019`（2025 版规定非在线资源不著录引用日期）
- 著者超过 3 人未加"等 / et al."
- 缺失或未知的文献类型标识（2025 版将其改为必备项，并新增 `PP` 预印本、`DS` 数据集、`A` 档案）
- 引用日期 `[2024.5.6]` → `[2024-05-06]`
- 全角标点误用作著录符号、条目缺句点、序号跳号/重复

## 安装

```bash
pip install gbt7714-lint
```

无任何第三方依赖，Python 3.9+。

## 使用

```bash
# 检查（从 Word 复制参考文献，存成 refs.txt）
gbt7714-lint refs.txt

# 自动修复，结果写入新文件
gbt7714-lint refs.txt --fix -o refs_fixed.txt

# 机器可读输出（供脚本/CI 使用）
gbt7714-lint refs.txt --json

# 从剪贴板 / 管道读取
Get-Clipboard | gbt7714-lint -      # PowerShell
pbpaste | gbt7714-lint -            # macOS
```

检查输出示例：

```text
检查 refs.txt：共 7 条参考文献
  [1] 第1行 [W101] 警告：外文作者姓氏全大写是 2015 版写法，2025 版改为仅首字母大写（可自动修复）
      'EINSTEIN A' → 'Einstein A'
  [4] 第4行 [W103] 警告：2025 版规定非在线资源不著录引用日期，应删除方括号引用日期（可自动修复）
  [8] 第7行 [E001] 错误：缺少文献类型标识（如 [J]、[M]、[D]）。2025 版将文献类型标识改为必备著录项
合计：1 个错误，8 个警告；其中 7 处可用 --fix 自动修复
```

也可以作为 Python 库调用：

```python
from gbt7714_lint import lint_text, fix_text

result = lint_text(open("refs.txt", encoding="utf-8").read())
for issue in result.issues:
    print(issue.rule_id, issue.message)

fixed, remaining = fix_text(open("refs.txt", encoding="utf-8").read())
```

## 规则一览

| 规则 | 级别 | 说明 | 自动修复 |
|------|------|------|:---:|
| E001 | 错误 | 缺少文献类型标识（2025 版必备项） | – |
| E002 | 错误 | 未知/小写的文献类型或载体标识 | 部分 |
| W101 | 警告 | 外文姓氏全大写（2015 版风格），应仅首字母大写 | ✓ |
| W102 | 警告 | 其他责任者"等译"应为"等，译"（2025 版新规） | ✓ |
| W103 | 警告 | 非在线资源著录了引用日期（2025 版禁止） | ✓ |
| W104 | 警告 | 在线资源缺少引用日期 | – |
| W105 | 警告 | 著者超过 3 人未加"等 / et al." | ✓ |
| W106 | 警告 | 日期未采用 YYYY-MM-DD 格式（区分并保留"(更新日期)"与"[引用日期]"两种括号） | ✓ |
| W107 | 警告 | 全角标点误用作著录符号 | ✓ |
| W108 | 警告 | 参考文献序号不连续或重复 | – |
| W109 | 警告 | 条目结尾缺少句点 | ✓ |
| W110 | 警告 | 中文文献误用"et al."或外文文献误用"等" | ✓ |
| W111 | 警告 | 文献类型标识前有多余空格（"标题 [J]"应为"标题[J]"） | ✓ |

## Features (English)

- **Plain-text first.** Works on the reference list you actually have — text copied out of Word/WPS — not BibTeX or a reference-manager database.
- **2025-aware.** Rules target the GB/T 7714—2025 revision specifically: foreign surnames in initial caps (pinyin surnames stay ALL CAPS), the new comma in "等，译", no cited dates on non-online resources, new document types `PP` (preprint), `DS` (dataset), `A` (archive), and the `MM` microform carrier.
- **Safe auto-fix.** Only deterministic, mechanical transforms are applied by `--fix`; anything requiring judgment stays a warning. URLs are never altered.
- **Zero dependencies.** Pure standard library, Python 3.9+, offline. Reads UTF-8 and GBK files.
- **Scriptable.** `--json` output and exit codes (`1` when errors remain) for CI and editor integrations.

## 局限与说明

- 本工具做**格式**检查，不核验文献是否真实存在（真伪核验可配合 [citation-checker](https://github.com/QAbot-zh/citation-checker) 等工具）。
- 拼音姓氏识别基于常见姓氏罗马化对照表，存在歧义时宁可不修（少数外文姓氏如 "Long"、"Chan" 会被保守跳过）。
- 解析器面向常见著录形态做了启发式设计；遇到误报/漏报，欢迎[提 issue](https://github.com/hc-ui/gbt7714-lint/issues) 并附上出问题的条目。

## 贡献

欢迎 issue 与 PR。跑测试：

```bash
pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE)
