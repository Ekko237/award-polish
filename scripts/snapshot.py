import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# 给评审做冻结快照：只从提交导出（git archive），网站目录下有没提交或没进仓库的文件就拒绝，
# 免得「工作区里有、提交里没有」的文件在快照里变成 404；导出后跑 asset_check.py 查全站资源。
# 不进仓库的大文件（游戏包、视频）用 --link 软链接进快照。
# 用法：python3 snapshot.py <仓库> <网站目录（相对仓库）> <快照目录> [--ref HEAD] [--link 快照内路径=实际路径 ...] [--skip 子目录 ...]
ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("site")
ap.add_argument("out")
ap.add_argument("--ref", default="HEAD")
ap.add_argument("--link", action="append", default=[], metavar="快照内路径=实际路径")
ap.add_argument("--skip", action="append", default=[], help="交给 asset_check.py 的不查子目录")
args = ap.parse_args()
repo = Path(args.repo).resolve()
out = Path(args.out).resolve()


def git(*a):
    return subprocess.run(["git", *a], cwd=repo, check=True, text=True, capture_output=True).stdout


if args.ref == "HEAD":
    dirty = git("status", "--porcelain", "--untracked-files=all", "--", args.site).strip()
    if dirty:
        sys.exit(f"{args.site} 下还有没提交的文件，先提交再做快照：\n{dirty}")
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
print(f"快照 {site} 做好了（{args.ref} = {git('rev-parse', '--short', args.ref).strip()}）")
