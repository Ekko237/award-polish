#!/usr/bin/env bash
# Install award-site as a plain skill for Codex and/or Claude Code.
# Usage: bash install.sh            (detect where to install)
#        bash install.sh codex      (Codex only)
#        bash install.sh claude     (Claude Code only)
# Claude Code users can also install it as a plugin, see README.md.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/award-site"
TARGETS=()

case "${1:-auto}" in
  codex)  TARGETS=("$HOME/.codex/skills/award-site") ;;
  claude) TARGETS=("$HOME/.claude/skills/award-site") ;;
  auto)
    [ -d "$HOME/.codex" ]  && TARGETS+=("$HOME/.codex/skills/award-site")
    [ -d "$HOME/.claude" ] && TARGETS+=("$HOME/.claude/skills/award-site")
    ;;
  *) echo "Usage: bash install.sh [codex|claude]"; exit 1 ;;
esac

if [ ${#TARGETS[@]} -eq 0 ]; then
  echo "Neither ~/.codex nor ~/.claude found. Install Codex or Claude Code first."
  exit 1
fi

for DST in "${TARGETS[@]}"; do
  # An existing folder this repo did not install (e.g. your own private skill of the same name) is backed up whole, never overwritten.
  if [ -d "$DST" ] && [ ! -f "$DST/.award-site-installed" ]; then
    BAK="$DST.bak-$(date +%Y%m%d-%H%M%S)"
    cp -R "$DST" "$BAK"
    echo "⚠️  $DST already exists and was not installed by this repo; backed up to:"
    echo "    $BAK"
  fi

  mkdir -p "$DST"
  # no --delete: extra files in the target (your own notes) are kept
  rsync -a --exclude '.DS_Store' --exclude '__pycache__' "$SRC"/ "$DST"/
  touch "$DST/.award-site-installed"
  echo "✅ Installed to $DST"
done

echo
echo "Open Codex or Claude Code and say \"polish this website to award level\", or use /award-site."
