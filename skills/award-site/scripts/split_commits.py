import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# When the working tree holds several changes, split them into one commit each. The split is described in a JSON file:
# {"ctx": {"styles.css": 1}, "items": [
#    {"name": "hero", "msg": "commit message", "hunks": {"src/site.js": ["keyword", ...], "pages/*/index.html": [...]}},
#    {"name": "palette", "msg": "...", "files": ["assets/raw"]},
#    {"name": "stamps", "msg": "...", "files": ["pages"], "only": "?v="}]}
# hunks: a hunk belongs to this item when any added or removed line contains one of its keywords; paths with * are globbed. files: whole files or directories for this item.
# only: after staging this item, every added or removed line must contain this string (e.g. an asset fingerprint); anything else mixed in refuses the commit.
# ctx: context lines per file (default 3). Use 1 when changes are only a line or two apart and 3 lines would merge them into one hunk; never 0:
# when only part of a zero-context diff is staged, git apply places later hunks at stale line numbers.
# Usage: python3 split_commits.py <repo> <split.json> plan          list hunks with unclear owners (none, or two items)
#       python3 split_commits.py <repo> <split.json> run [--dry] [--items a,b]   runs plan first and commits item by item only when everything is clear
ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("spec")
ap.add_argument("action", choices=["plan", "run"])
ap.add_argument("--dry", action="store_true", help="stage, print and unstage each item without committing")
ap.add_argument("--sign", default="", help="text appended to every commit message, e.g. a Co-Authored-By line")
ap.add_argument("--items", help="commit only these items (comma-separated names), to continue after fixing the split halfway")
args = ap.parse_args()
ROOT = Path(args.repo).resolve()
spec = json.loads(Path(args.spec).read_text())
CTX = {k: str(v) for k, v in spec.get("ctx", {}).items()}
if "0" in CTX.values():
    sys.exit("ctx must not be 0")
ITEMS = spec["items"]


def git(*a, inp=None):
    return subprocess.run(["git", *a], cwd=ROOT, check=True, text=True, capture_output=True, input=inp).stdout


def names(*a):
    # -z separates names with \0 so file names with spaces stay whole
    return [n for n in git(*a, "-z").split("\0") if n]


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
    for path in names("diff", "--name-only"):
        if path in km:
            for h in split_hunks(path)[1]:
                o = owners(path, h, km) or file_owner(path)
                if len(o) != 1:
                    bad.append(f"{path} {h.splitlines()[0]} -> {o or 'no owner'}")
        elif len(file_owner(path)) != 1:
            bad.append(f"{path} (whole file) -> {file_owner(path) or 'no owner'}")
    for path in names("ls-files", "--others", "--exclude-standard"):
        if len(file_owner(path)) != 1:
            bad.append(f"{path} (new file) -> {file_owner(path) or 'no owner'}")
    for b in bad:
        print(b)
    print("Every hunk has one owner" if not bad else f"{len(bad)} to fix: change keywords or the split, then run plan again")
    return not bad


def run_item(it):
    if git("diff", "--cached", "--name-only").strip():
        sys.exit("The index is not empty; deal with it first")
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
        sys.exit(f"{it['name']}: nothing was staged; keywords or paths are wrong")
    if "only" in it:
        stray = [ln for ln in changed(staged) if it["only"] not in ln]
        if stray:
            git("reset", "-q")
            sys.exit(f"{it['name']}: the index holds changes that do not belong to this item:\n" + "\n".join(stray[:20]))
    print(git("diff", "--cached", "--stat").rstrip())
    if args.dry:
        git("reset", "-q")
        print(f"({it['name']} dry run, not committed)")
    else:
        git("commit", "-q", "-m", it["msg"] + (f"\n\n{args.sign}" if args.sign else ""))
        print(git("log", "--oneline", "-1").rstrip())


if not plan():
    sys.exit(1)
if args.action == "run":
    chosen = args.items.split(",") if args.items else [it["name"] for it in ITEMS]
    unknown = set(chosen) - {it["name"] for it in ITEMS}
    if unknown:
        sys.exit(f"These items are not in the split: {sorted(unknown)}")
    for it in ITEMS:
        if it["name"] in chosen:
            run_item(it)
    left = git("status", "--porcelain").strip()
    print("Working tree clean" if not left else "Changes left over:\n" + left)
