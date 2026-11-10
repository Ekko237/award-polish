import argparse
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import tinycss2
from bs4 import BeautifulSoup

# 全站本地资源齐不齐：网站目录下每个 HTML 引用的本站文件（img/source 的 src 和 srcset、link href、script src、
# 行内 style 的 url()）和每个 CSS 文件里的 url() 是否都在磁盘上。缺一个就列出来，退出码 1。
# layout_check.py 只查打开过的页面；这个脚本不开浏览器，几秒查完全站，做快照和发布前都跑。
# 用法：python3 asset_check.py <网站目录> [--skip 子目录 ...]
ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--skip", action="append", default=[], help="不查的子目录（相对网站目录），比如游戏包、第三方文档")
args = ap.parse_args()
ROOT = Path(args.root).resolve()
SKIP = [Path(s).parts for s in args.skip]
SKIP_PREFIX = ("http://", "https://", "//", "data:", "mailto:", "tel:", "#", "javascript:", "blob:")
LINK_REL_SKIP = {"canonical", "alternate", "preconnect", "dns-prefetch", "author", "me", "next", "prev"}
missing = []


def skipped(p):
    parts = p.relative_to(ROOT).parts
    return any(parts[:len(s)] == s for s in SKIP)


def check(ref, base, where):
    ref = ref.strip()
    if not ref or ref.startswith(SKIP_PREFIX):
        return
    path = unquote(urlsplit(ref).path)
    if not path:
        return
    target = (ROOT / path.lstrip("/")) if path.startswith("/") else (base / path)
    if path.endswith("/"):
        target = target / "index.html"
    if not target.exists():
        missing.append(f"{where}: {ref}")


def css_urls(tokens):
    for t in tokens:
        if t.type == "url":
            yield t.value
        elif t.type == "function":
            if t.lower_name == "url":
                yield "".join(a.value for a in t.arguments if a.type == "string")
            yield from css_urls(t.arguments)
        elif t.type in ("() block", "[] block", "{} block"):
            yield from css_urls(t.content)


for html in sorted(ROOT.rglob("*.html")):
    if skipped(html):
        continue
    rel = html.relative_to(ROOT)
    soup = BeautifulSoup(html.read_text(), "html.parser")
    for tag, attr in (("img", "src"), ("source", "src"), ("script", "src"), ("link", "href"), ("video", "poster")):
        for el in soup.find_all(tag):
            if not el.get(attr):
                continue
            if tag == "link" and set(el.get("rel") or []) & LINK_REL_SKIP:
                continue
            check(el[attr], html.parent, f"{rel} <{tag} {attr}>")
    for el in soup.find_all(["img", "source"]):
        for part in (el.get("srcset") or "").split(","):
            if part.strip():
                check(part.strip().split()[0], html.parent, f"{rel} <{el.name} srcset>")
    for el in soup.find_all(style=True):
        for u in css_urls(tinycss2.parse_component_value_list(el["style"])):
            check(u, html.parent, f"{rel} style=")
    for el in soup.find_all("style"):
        for rule in tinycss2.parse_stylesheet(el.get_text(), skip_comments=True, skip_whitespace=True):
            for u in css_urls(list(getattr(rule, "prelude", None) or []) + list(getattr(rule, "content", None) or [])):
                check(u, html.parent, f"{rel} <style>")

for css in sorted(ROOT.rglob("*.css")):
    if skipped(css):
        continue
    for rule in tinycss2.parse_stylesheet(css.read_text(), skip_comments=True, skip_whitespace=True):
        for u in css_urls(list(getattr(rule, "prelude", None) or []) + list(getattr(rule, "content", None) or [])):
            check(u, css.parent, str(css.relative_to(ROOT)))

for m in missing:
    print("缺文件", m)
print(f"资源检查：缺 {len(missing)} 个")
sys.exit(1 if missing else 0)
