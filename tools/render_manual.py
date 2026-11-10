"""Render this project's simple Markdown manual as offline HTML, without dependencies."""
from html import escape
from pathlib import Path
import re
import os


def inline(text):
    text = escape(text)
    def link(match):
        target = match[2]
        return f'<a href="{target}">{match[1]}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def render(root: Path, language="fr", stem=None, output=None, outputs=None):
    stem = stem or "README"
    blocks, paragraph, table_rows = [], [], []
    in_code = False
    listing = None
    def flush():
        if paragraph:
            blocks.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()
    def flush_table():
        if table_rows:
            blocks.append('<table>')
            for index, cells in enumerate(table_rows):
                tag = 'th' if index == 0 else 'td'
                blocks.append('<tr>' + ''.join(f'<{tag}>{inline(cell)}</{tag}>' for cell in cells) + '</tr>')
            blocks.append('</table>')
            table_rows.clear()
    for line in (root / f"{stem}.md").read_text(encoding="utf-8").splitlines():
        if not in_code and line.strip().startswith('|'):
            flush()
            if listing:
                blocks.append(f'</{listing}>')
                listing = None
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells):
                table_rows.append(cells)
            continue
        flush_table()
        if line.startswith("```"):
            flush()
            if listing:
                blocks.append(f"</{listing}>")
                listing = None
            blocks.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
        elif in_code:
            blocks.append(escape(line) + "\n")
        else:
            heading = re.match(r"^(#{1,3}) (.+)", line)
            item = re.match(r"^(?:([-])|\d+\.) (.+)", line)
            if not item and listing:
                blocks.append(f"</{listing}>")
                listing = None
            anchor = re.fullmatch(r'<a id="([a-zA-Z][\w-]*)"></a>', line.strip())
            if anchor:
                flush()
                blocks.append(f'<a id="{anchor[1]}"></a>')
            elif heading:
                flush()
                n = len(heading[1])
                blocks.append(f"<h{n}>{inline(heading[2])}</h{n}>")
            elif item:
                flush()
                kind = "ul" if item[1] else "ol"
                if listing != kind:
                    if listing:
                        blocks.append(f"</{listing}>")
                    blocks.append(f"<{kind}>")
                    listing = kind
                blocks.append("<li>" + inline(item[2]) + "</li>")
            elif not line.strip():
                flush()
            else:
                paragraph.append(line)
    flush()
    flush_table()
    if listing:
        blocks.append(f"</{listing}>")
    html = """<!doctype html><html lang="LANGUAGE"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sharp PC-G Link</title><style>
body{background:#edf1f5;color:#23364a;font:17px/1.6 'Segoe UI',sans-serif;margin:0}
main{max-width:940px;margin:30px auto;background:white;padding:32px 50px;border-radius:12px}
h1{color:#142c40;font-size:2.4em;line-height:1.15}h2{color:#176d8a;margin-top:1.8em}
h3{margin-top:1.7em}a{color:#146787}code{background:#edf1f5;padding:2px 5px;border-radius:3px}
pre{background:#142c40;color:#e7f3fa;padding:18px 22px;border-radius:8px;overflow:auto;line-height:1.1}
pre code{background:none;padding:0}li{margin:.45em 0}@media(max-width:700px){main{padding:20px;margin:0;border-radius:0}}
table{border-collapse:collapse;width:100%;font-size:.92em}th,td{border:1px solid #d6dfe6;padding:8px 10px;text-align:left;vertical-align:top}th{background:#edf1f5}
</style><main>""".replace('lang="LANGUAGE"', f'lang="{language}"') + "\n".join(blocks) + "</main></html>"
    target = output or root / f"{stem}.html"
    if outputs is not None:
        def relocate(match):
            href = match[1]
            if re.match(r'^[a-zA-Z]+:', href) or href.startswith('#'):
                return match[0]
            filename, marker, anchor = href.partition('#')
            source_link = (root / filename).resolve()
            destination = outputs.get(source_link, source_link)
            relative = Path(os.path.relpath(destination, target.parent)).as_posix()
            return 'href="' + relative + (marker + anchor if marker else '') + '"'
        html = re.sub(r'href="([^"]+)"', relocate, html)
    target.write_text(html, encoding="utf-8")


def render_all(root):
    sources = [root / 'README.md', root / 'NOTICE.md']
    sources.extend((root / 'docs').glob('*.md'))
    sources.extend((root / 'romdump').glob('*.md'))
    sources.extend((root / 'examples').rglob('*.md'))
    outputs = {source.resolve(): ((root / 'docs' / source.name).with_suffix('.html')
               if source.parent == root else source.with_suffix('.html')) for source in sources}
    for source, destination in outputs.items():
        render(source.parent, 'en' if source.stem.endswith('_EN') else 'fr',
               stem=source.stem, output=destination, outputs=outputs)


if __name__ == "__main__":
    render_all(Path(__file__).resolve().parents[1])
