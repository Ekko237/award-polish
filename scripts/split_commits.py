import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 工作区攒了几件改动时，按件拆成一件一个提交。拆法写在一个 JSON 里：
# {"ctx": {"styles.css": 1}, "items": [
#    {"name": "hero", "msg": "提交说明", "hunks": {"src/site.js": ["关键词", ...], "pages/*/index.html": [...]}},
#    {"name": "palette", "msg": "...", "files": ["assets/raw"]},
#    {"name": "stamps", "msg": "...", "files": ["pages"], "only": "?v="}]}
# hunks：改动块的增删行里出现任一关键词就归这一件；路径带 * 按 glob 展开。files：整个文件或目录归这一件。
# only：这一件暂存后每一行增删都要含这个字样（比如资源指纹），混进别的改动就拒绝提交。
# ctx：每个文件的上下文行数（默认 3）。几件改动只隔一两行、3 行上下文会并成一块时用 1；不许用 0：
# 零上下文的改动块只暂存一部分时，git apply 会按过时的行号把后面的块放错位置。
# 用法：python3 split_commits.py <仓库> <拆法.json> plan          列出归属不清（没归属、归了两件）的改动块
#       python3 split_commits.py <仓库> <拆法.json> run [--dry] [--items a,b]   先跑 plan，全部清楚才按顺序逐件提交
ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("spec")
ap.add_argument("action", choices=["plan", "run"])
ap.add_argument("--dry", action="store_true", help="逐件暂存、打印、撤出暂存区，不提交")
ap.add_argument("--sign", default="", help="追加在每条提交说明末尾的文字，比如 Co-Authored-By 行")
ap.add_argument("--items", help="只提交这几件（逗号分隔的 name），中途停下改完拆法后接着提交剩下的用")
args = ap.parse_args()
ROOT = Path(args.repo).resolve()
spec = json.loads(Path(args.spec).read_text())
CTX = {k: str(v) for k, v in spec.get("ctx", {}).items()}
if "0" in CTX.values():
    sys.exit("ctx 不能是 0")
ITEMS = spec["items"]


def git(*a, inp=None):
    return subprocess.run(["git", *a], cwd=ROOT, check=True, text=True, capture_output=True, input=inp).stdout


def expand(pat):
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(pat)) if "*" in pat else [pat]


def split_hunks(path):
    head, *hunks = re.split(r"(?m)^(?=@@ )", git("diff", f"-U{CTX.get(path, '3')}", "--", path))
    return head, hunks


def changed(text):
    return [ln for ln in text.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]


def owners(path, hunk, keymap):
    return [n for n, ks in keymap.get(path, []) if any(k in ln for ln in changed(hunk) for k in ks)]


def keymap():
    km = {}
    for it in ITEMS:
        for pat, ks in it.get("hunks", {}).items():
            for path in expand(pat):
                km.setdefault(path, []).append((it["name"], ks))
    return km


def file_owner(path):
    return [it["name"] for it in ITEMS for f in it.get("files", []) if path == f or path.startswith(f.rstrip("/") + "/")]


def plan():
    km = keymap()
    bad = []
    for path in git("diff", "--name-only").split():
        if path in km:
            for h in split_hunks(path)[1]:
                o = owners(path, h, km) or file_owner(path)
                if len(o) != 1:
                    bad.append(f"{path} {h.splitlines()[0]} → {o or '没有归属'}")
        elif len(file_owner(path)) != 1:
            bad.append(f"{path}（整个文件）→ {file_owner(path) or '没有归属'}")
    for path in git("ls-files", "--others", "--exclude-standard").split():
        if len(file_owner(path)) != 1:
            bad.append(f"{path}（新文件）→ {file_owner(path) or '没有归属'}")
    for b in bad:
        print(b)
    print("全部归属清楚" if not bad else f"{len(bad)} 处要处理：改关键词或拆法再跑 plan")
    return not bad


def run_item(it):
    if git("diff", "--cached", "--name-only").strip():
        sys.exit("暂存区不是空的，先处理掉")
    for pat, ks in it.get("hunks", {}).items():
        for path in expand(pat):
            head, hunks = split_hunks(path)
            picked = [h for h in hunks if any(k in ln for ln in changed(h) for k in ks)]
            if picked:
                git("apply", "--cached", "-", inp=head + "".join(picked))
    for f in it.get("files", []):
        git("add", "--", f)
    staged = git("diff", "--cached")
    if not staged.strip():
        sys.exit(f"{it['name']}：什么都没暂存上，关键词或路径不对")
    if "only" in it:
        stray = [ln for ln in changed(staged) if it["only"] not in ln]
        if stray:
            git("reset", "-q")
            sys.exit(f"{it['name']}：暂存区里有不该在这一件的改动：\n" + "\n".join(stray[:20]))
    print(git("diff", "--cached", "--stat").rstrip())
    if args.dry:
        git("reset", "-q")
        print(f"（{it['name']} 演练，没提交）")
    else:
        git("commit", "-q", "-m", it["msg"] + (f"\n\n{args.sign}" if args.sign else ""))
        print(git("log", "--oneline", "-1").rstrip())


if not plan():
    sys.exit(1)
if args.action == "run":
    names = args.items.split(",") if args.items else [it["name"] for it in ITEMS]
    unknown = set(names) - {it["name"] for it in ITEMS}
    if unknown:
        sys.exit(f"拆法里没有这几件：{sorted(unknown)}")
    for it in ITEMS:
        if it["name"] in names:
            run_item(it)
    left = git("status", "--porcelain").strip()
    print("工作区干净" if not left else "还剩没拆走的改动：\n" + left)
