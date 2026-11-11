#!/usr/bin/env python3
"""Check each skills/**/SKILL.md frontmatter.

Requires a name and a description of at most 1024 characters.
The description may be a single-quoted, double-quoted, or plain one-line value.
"""
import pathlib
import sys

MAX_DESCRIPTION = 1024
ROOT = pathlib.Path(__file__).resolve().parents[2]
paths = sorted(ROOT.glob("skills/**/SKILL.md"))
if not paths:
    sys.exit("no skills/**/SKILL.md files found")


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        if value[0] == "'":
            return inner.replace("''", "'")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_frontmatter(text, path):
    if not text.startswith("---\n"):
        sys.exit(f"{path}: frontmatter must start on line 1")
    end = text.find("\n---\n", 4)
    if end == -1:
        sys.exit(f"{path}: frontmatter is not closed")
    data = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if line[0] in " \t":
            sys.exit(f"{path}: only one-line frontmatter values are supported, got {line!r}")
        if ":" not in line:
            sys.exit(f"{path}: bad frontmatter line: {line}")
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if raw in {">", ">-", "|", "|-"}:
            sys.exit(f"{path}: put {key} on one line so the length check can read it")
        data[key] = unquote(raw)
    return data


failed = False
for path in paths:
    rel = path.relative_to(ROOT)
    data = parse_frontmatter(path.read_text(encoding="utf-8"), rel)
    name = data.get("name", "").strip()
    description = data.get("description", "")
    if not name:
        print(f"{rel}: name is missing")
        failed = True
    if not description.strip():
        print(f"{rel}: description is missing")
        failed = True
        continue
    count = len(description)
    print(f"{rel}: name={name} description_chars={count}")
    if count > MAX_DESCRIPTION:
        print(f"{rel}: description is {count} characters; max is {MAX_DESCRIPTION}")
        failed = True

if failed:
    sys.exit(1)
