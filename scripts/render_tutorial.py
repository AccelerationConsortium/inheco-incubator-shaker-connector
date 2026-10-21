"""Render the Chinese tutorial to self-contained HTML; run from repository root."""

import html
import re
from pathlib import Path

from markdown_it import MarkdownIt

STYLE = 'body{margin:0;background:#f5f3f9;color:#252333;font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}main{max-width:920px;margin:40px auto;padding:48px;background:white;border-radius:20px;box-shadow:0 12px 50px #51416b12}h1{font-size:32px;line-height:1.4}h2{margin-top:60px;border-top:1px solid #e5e1ec;padding-top:24px;line-height:1.5;color:#564779}a{color:#65518f}nav{background:#f1edf7;padding:24px;border-radius:12px;columns:2;column-gap:30px}nav a{display:block;font-size:14px;break-inside:avoid;text-decoration:none;margin:6px 0}pre{overflow:auto;background:#242234;color:#f4effe;padding:20px;border-radius:10px;font:14px/1.65 ui-monospace,monospace}code{font-family:ui-monospace,monospace}p code,li code,td code{background:#f3f0f8;border-radius:4px;padding:2px 5px;font-size:.9em;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow:auto}td,th{padding:12px;text-align:left;border:1px solid #e4dfec;min-width:120px}th{background:#f2eef7}strong{color:#44335f}li{margin:8px 0}footer{font-size:13px;margin-top:50px;color:#766d86}@media(max-width:700px){main{margin:0;padding:24px;border-radius:0}nav{columns:1}h1{font-size:26px}}@media print{body{background:white}main{padding:0;margin:0;box-shadow:none}nav{display:none}pre{white-space:pre-wrap;color:black;background:#eee}h2{break-after:avoid}tr{break-inside:avoid}}'


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "docs/TUTORIAL.zh-CN.md"
    content = MarkdownIt("commonmark").enable("table").render(source.read_text())
    toc = []

    def heading(match):
        title = re.sub("<.*?>", "", match[1])
        identifier = f"chapter-{len(toc) + 1}"
        toc.append((identifier, title))
        return f'<h2 id="{identifier}">{match[1]}</h2>'

    content = re.sub(r"<h2>(.*?)</h2>", heading, content)
    nav = "".join(
        f'<a href="#{identifier}">{html.escape(title)}</a>' for identifier, title in toc
    )
    output = (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>INHECO SiLA2 Connector 从零教程</title>"
        f'<style>{STYLE}</style><main><nav aria-label="章节目录">{nav}</nav>{content}'
        "<footer>UniteLabs CDK · INHECO MP · v0.2.0 · 实机验收待完成</footer></main></html>"
    )
    target = source.with_suffix(".html")
    target.write_text(output)
    print(f"Rendered {target.name}: {len(toc)} chapters")


if __name__ == "__main__":
    main()
