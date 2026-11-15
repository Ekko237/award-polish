import argparse
import json
import os
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
# Commands are a list of arguments with shell=False. Paths from the split file must stay inside the repo and must not look like options.
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


def plain(value, label):
    if not isinstance(value, str) or "\0" in value:
        sys.exit(f"{label} must be plain text")
    return value


def rel_path(value, label):
    plain(value, label)
    if not value or value.startswith("-") or "\n" in value or "\r" in value:
        sys.exit(f"{label} must be a relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        sys.exit(f"{label} must stay inside the repo: {value}")
    return value


def item_name(value):
    plain(value, "item name")
    if not value or value != value.strip() or "\n" in value or "," in value or "/" in value or value.startswith("-"):
        sys.exit(f"item name is not usable: {value!r}")
    return value


ROOT = Path(os.path.abspath(args.repo))
if not ROOT.is_dir():
    sys.exit(f"repo is not a directory: {ROOT}")
spec_path = Path(args.spec)
if not spec_path.is_file():
    sys.exit(f"split file is not a file: {spec_path}")
plain(args.sign, "sign text")
try:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as err:
    sys.exit(f"split file is not valid JSON: {err}")
if not isinstance(spec, dict):
    sys.exit("split file must be a JSON object")
ctx_in = spec.get("ctx", {})
if not isinstance(ctx_in, dict):
    sys.exit("ctx must be an object")
CTX = {}
for key, value in ctx_in.items():
    rel_path(key, "ctx path")
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 99:
        sys.exit("ctx must be a whole number from 1 to 99")
    CTX[key] = str(value)
items_in = spec.get("items")
if not isinstance(items_in, list) or not items_in:
    sys.exit("items must be a non-empty list")
ITEMS = []
seen = set()
for it in items_in:
    if not isinstance(it, dict):
        sys.exit("each item must be an object")
    name = item_name(it.get("name", ""))
    if name in seen:
        sys.exit(f"duplicate item name: {name}")
    seen.add(name)
    msg = plain(it.get("msg", ""), "commit message")
    if not msg.strip():
        sys.exit(f"{name}: commit message is empty")
    hunks = it.get("hunks", {})
    if not isinstance(hunks, dict):
        sys.exit(f"{name}: hunks must be an object")
    clean_hunks = {}
    for pat, keywords in hunks.items():
        rel_path(pat, f"{name} hunk path")
        if not isinstance(keywords, list) or not keywords:
            sys.exit(f"{name}: keywords for {pat} must be a non-empty list")
        clean = []
        for keyword in keywords:
            plain(keyword, f"{name} keyword")
            if not keyword:
                sys.exit(f"{name}: keyword for {pat} is empty")
            clean.append(keyword)
        clean_hunks[pat] = clean
    files = it.get("files", [])
    if not isinstance(files, list):
        sys.exit(f"{name}: files must be a list")
    clean_files = [rel_path(entry, f"{name} file") for entry in files]
    if not clean_hunks and not clean_files:
        sys.exit(f"{name}: needs hunks or files")
    cleaned = {"name": name, "msg": msg, "hunks": clean_hunks, "files": clean_files}
    if "only" in it:
        only = plain(it["only"], f"{name} only")
        if not only:
            sys.exit(f"{name}: only must not be empty")
        cleaned["only"] = only
    ITEMS.append(cleaned)


# Git is only started with shell=False and one of the fixed argv lists below.
# shell is off, so a path or commit message is data for git, not a shell command.
# The executable is the literal "git". Paths are checked by rel_path first
# (relative, no "..", not an option). The apply patch is stdin, not an argument.
# That is safe: nothing here is passed to a shell, and no argument can add a
# subcommand or leave the repo.


def git_changed_names():
    # Safe: shell is off. This argv is the fixed list git diff --name-only -z.
    # -z keeps file names with spaces whole. Nothing from the split file is included.
    out = subprocess.run(
        ["git", "diff", "--name-only", "-z"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout
    return [n for n in out.split("\0") if n]


def git_untracked_names():
    # Safe: shell is off. This argv is the fixed list git ls-files --others --exclude-standard -z.
    out = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout
    return [n for n in out.split("\0") if n]


def git_diff_path(path):
    path = rel_path(path, "diff path")
    context = CTX.get(path, "3")
    if not re.fullmatch(r"[1-9][0-9]?", context):
        sys.exit("diff context must be 1 to 99")
    # Safe: shell is off. argv is the fixed form git diff -U<n> -- <path>.
    # n is 1-99 and path was checked by rel_path, so it cannot be another git option.
    return subprocess.run(
        ["git", "diff", "-U" + context, "--", path],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_cached_names():
    # Safe: shell is off. This argv is the fixed list git diff --cached --name-only.
    return subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_apply_cached(patch):
    if not isinstance(patch, str) or "\0" in patch:
        sys.exit("refusing a patch that is not plain text")
    # Safe: shell is off. argv is the fixed list git apply --cached -.
    # The patch is stdin, not an argument.
    return subprocess.run(
        ["git", "apply", "--cached", "-"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        input=patch,
        shell=False,
    ).stdout


def git_add(path):
    path = rel_path(path, "git add path")
    # Safe: shell is off. argv is the fixed form git add -- <path>.
    # "--" keeps the path from being read as an option.
    return subprocess.run(
        ["git", "add", "--", path],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_cached_diff():
    # Safe: shell is off. This argv is the fixed list git diff --cached.
    return subprocess.run(
        ["git", "diff", "--cached"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_reset_quiet():
    # Safe: shell is off. This argv is the fixed list git reset -q.
    # It unstages only. It does not move HEAD or delete files.
    return subprocess.run(
        ["git", "reset", "-q"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_cached_stat():
    # Safe: shell is off. This argv is the fixed list git diff --cached --stat.
    return subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_commit(message):
    plain(message, "commit message")
    if not message.strip():
        sys.exit("commit message is empty")
    # Safe: shell is off. argv is the fixed form git commit -q -m <message>.
    # -m takes the next item as the message, even if that text starts with "-".
    return subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_log_one():
    # Safe: shell is off. This argv is the fixed list git log --oneline -1.
    return subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def git_status():
    # Safe: shell is off. This argv is the fixed list git status --porcelain.
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        shell=False,
    ).stdout


def expand(pat):
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(pat)) if "*" in pat else [pat]


def split_hunks(path):
    head, *hunks = re.split(r"(?m)^(?=@@ )", git_diff_path(path))
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
    for path in git_changed_names():
        if path in km:
            for h in split_hunks(path)[1]:
                o = owners(path, h, km) or file_owner(path)
                if len(o) != 1:
                    bad.append(f"{path} {h.splitlines()[0]} -> {o or 'no owner'}")
        elif len(file_owner(path)) != 1:
            bad.append(f"{path} (whole file) -> {file_owner(path) or 'no owner'}")
    for path in git_untracked_names():
        if len(file_owner(path)) != 1:
            bad.append(f"{path} (new file) -> {file_owner(path) or 'no owner'}")
    for b in bad:
        print(b)
    print("Every hunk has one owner" if not bad else f"{len(bad)} to fix: change keywords or the split, then run plan again")
    return not bad


def run_item(it):
    if git_cached_names().strip():
        sys.exit("The index is not empty; deal with it first")
    for pat, ks in it.get("hunks", {}).items():
        for path in expand(pat):
            head, hunks = split_hunks(path)
            picked = [h for h in hunks if any(k in ln for ln in changed(h) for k in ks)]
            if picked:
                git_apply_cached(head + "".join(picked))
    for f in it.get("files", []):
        git_add(f)
    staged = git_cached_diff()
    if not staged.strip():
        sys.exit(f"{it['name']}: nothing was staged; keywords or paths are wrong")
    if "only" in it:
        stray = [ln for ln in changed(staged) if it["only"] not in ln]
        if stray:
            git_reset_quiet()
            sys.exit(f"{it['name']}: the index holds changes that do not belong to this item:\n" + "\n".join(stray[:20]))
    print(git_cached_stat().rstrip())
    if args.dry:
        git_reset_quiet()
        print(f"({it['name']} dry run, not committed)")
    else:
        git_commit(it["msg"] + (f"\n\n{args.sign}" if args.sign else ""))
        print(git_log_one().rstrip())


if not plan():
    sys.exit(1)
if args.action == "run":
    chosen = args.items.split(",") if args.items else [it["name"] for it in ITEMS]
    if any(not part for part in chosen):
        sys.exit("items list has an empty name")
    unknown = set(chosen) - {it["name"] for it in ITEMS}
    if unknown:
        sys.exit(f"These items are not in the split: {sorted(unknown)}")
    for it in ITEMS:
        if it["name"] in chosen:
            run_item(it)
    left = git_status().strip()
    print("Working tree clean" if not left else "Changes left over:\n" + left)
