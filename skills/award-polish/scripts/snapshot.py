import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Frozen snapshot for reviewers: export from a commit only (git archive) and refuse when the site directory has uncommitted or untracked files,
# so files that exist in the working tree but not in the commit do not turn into 404s; then run asset_check.py over the whole site.
# Large files kept out of git (game builds, videos) are symlinked into the snapshot with --link.
# Usage: python3 snapshot.py <repo> <site dir (relative to repo)> <snapshot dir> [--ref HEAD] [--link path-in-snapshot=real-path ...] [--skip subdir ...]
ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("site")
ap.add_argument("out")
ap.add_argument("--ref", default="HEAD")
ap.add_argument("--link", action="append", default=[], metavar="path-in-snapshot=real-path")
ap.add_argument("--skip", action="append", default=[], help="subdirectory asset_check.py should skip")
args = ap.parse_args()
repo = Path(args.repo).resolve()
out = Path(args.out).resolve()


def git(*a):
    return subprocess.run(["git", *a], cwd=repo, check=True, text=True, capture_output=True).stdout


if args.ref == "HEAD":
    dirty = git("status", "--porcelain", "--untracked-files=all", "--", args.site).strip()
    if dirty:
        sys.exit(f"{args.site} has uncommitted files; commit them before taking a snapshot:\n{dirty}")
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
archive = subprocess.run(["git", "archive", args.ref, args.site], cwd=repo, check=True, capture_output=True).stdout
subprocess.run(["tar", "-x", "-C", str(out)], input=archive, check=True)
site = out / args.site
for spec in args.link:
    inner, target = spec.split("=", 1)
    dest = site / inner
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(Path(target).resolve())
check = [sys.executable, str(Path(__file__).with_name("asset_check.py")), str(site)]
for s in args.skip:
    check += ["--skip", s]
subprocess.run(check, check=True)
print(f"Snapshot {site} ready ({args.ref} = {git('rev-parse', '--short', args.ref).strip()})")
