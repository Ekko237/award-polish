import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FILES = ROOT / "files"
EMAIL = "{{EMAIL_c0959587}}"
WORKDIR = "@WORKDIR@"


def git(target, *args):
    subprocess.run(["git", "-C", str(target), *args], check=True)


def commit(target, author, message, date=None):
    env = None
    if date:
        env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    subprocess.run(
        [
            "git",
            "-c",
            f"user.name={author}",
            "-c",
            f"user.email={EMAIL}",
            "-C",
            str(target),
            "commit",
            "-m",
            message,
        ],
        check=True,
        env=env,
    )


def clear_keep_git(target):
    for entry in target.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def copy_contents(source, target):
    for entry in source.iterdir():
        destination = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination)
        else:
            shutil.copy2(entry, destination)


def main():
    parser = argparse.ArgumentParser(
        description="按编号搭建 Lumen Notes、港湾咖啡或松木工作室的工作目录。"
    )
    parser.add_argument("id", choices=("0", "1", "2"), help="项目编号")
    parser.add_argument("target", type=Path, help="尚不存在的目标目录")
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    if target.exists():
        parser.error("目标目录已存在")
    target.parent.mkdir(parents=True, exist_ok=True)

    if args.id == "0":
        shutil.copytree(FILES / "lumen-notes-site", target)
        git(target, "init", "-q", "-b", "main")
        git(target, "add", "-A")
        commit(target, "Lumen", "上线版")
        return

    if args.id == "1":
        replay(FILES / "harbor-cafe-web", target, "Harbor")
    else:
        replay(FILES / "pinewood-studio", target, "Pinewood")


def replay(project, target, author):
    """按 manifest.json 逐个版本铺进去提交、打标签，再放上不进仓库的文件。"""
    manifest = json.loads((project / "manifest.json").read_text(encoding="utf-8"))
    target.mkdir(parents=True)
    git(target, "init", "-q", "-b", "main")
    for version in manifest["versions"]:
        clear_keep_git(target)
        copy_contents(project / "versions" / version["version"], target)
        git(target, "add", "-A")
        commit(target, author, version["message"], version.get("date"))
        for tag in version["tags"]:
            git(target, "tag", tag)
    for entry in project.iterdir():
        if entry.name in ("manifest.json", "versions"):
            continue
        destination = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination)
            files = destination.rglob("*")
        else:
            shutil.copy2(entry, destination)
            files = [destination]
        for path in files:
            if path.is_file() and path.suffix in (".md", ".json"):
                text = path.read_text(encoding="utf-8")
                if WORKDIR in text:
                    path.write_text(text.replace(WORKDIR, str(target)), encoding="utf-8")

if __name__ == "__main__":
    main()
