#!/usr/bin/env bash
# Install award-polish as a plain skill folder.
# Usage: bash install.sh                  (detect ~/.claude and ~/.codex)
#        bash install.sh claude           (~/.claude/skills/award-polish)
#        bash install.sh codex            (~/.codex/skills/award-polish)
#        bash install.sh /path/to/skills  (any other agent: the folder it loads skills from)
# Claude Code users can also install it as a plugin, see README.md.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/award-polish"
TARGETS=()

case "${1:-auto}" in
  codex)  TARGETS=("$HOME/.codex/skills/award-polish") ;;
  claude) TARGETS=("$HOME/.claude/skills/award-polish") ;;
  auto)
    [ -d "$HOME/.codex" ]  && TARGETS+=("$HOME/.codex/skills/award-polish")
    [ -d "$HOME/.claude" ] && TARGETS+=("$HOME/.claude/skills/award-polish")
    ;;
  -*) echo "Usage: bash install.sh [claude|codex|/path/to/skills]"; exit 1 ;;
  *)  TARGETS=("${1%/}/award-polish") ;;
esac

if [ ${#TARGETS[@]} -eq 0 ]; then
  echo "Neither ~/.claude nor ~/.codex found. Pass the folder your agent loads skills from: bash install.sh /path/to/skills"
  exit 1
fi

for DST in "${TARGETS[@]}"; do
  # An existing folder this repo did not install (e.g. your own private skill of the same name) is backed up whole, never overwritten.
  if [ -d "$DST" ] && [ ! -f "$DST/.award-polish-installed" ]; then
    BAK="$DST.bak-$(date +%Y%m%d-%H%M%S)"
    cp -R "$DST" "$BAK"
    echo "⚠️  $DST already exists and was not installed by this repo; backed up to:"
    echo "    $BAK"
  fi

  mkdir -p "$DST"
  # no --delete: extra files in the target (your own notes) are kept
  rsync -a --exclude '.DS_Store' --exclude '__pycache__' "$SRC"/ "$DST"/
  touch "$DST/.award-polish-installed"
  echo "✅ Installed to $DST"
done

echo
echo "Ask your agent to \"polish this site to award level\" or \"use the award-polish skill\"; agents with slash commands also take /award-polish."
