# Changelog

## 1.0.3 - 2026-11-15

Security scan fixes. The polish loop is unchanged.

- `seo_keep.py --dump` writes only a relative path inside the repo or the working directory. Absolute paths and `..` are refused. The skill declares that file write (`Write`).
- Git, tar, and the bundled asset check go through `scripts/_proc.py`. That module allowlists `git`, `tar`, and `python`, checks the arguments, and is the only `subprocess.run` call.

## 1.0.2 - 2026-11-15

Security scan fixes. The polish loop is unchanged.

- Network use is declared on the skill (`WebFetch` and `permissions: [network]`). `seo_keep.py` fetches the pages it is given to compare search fields. `wait_live.py` opens the live URL it is given, plus that page's stylesheets and scripts, to see when a release is being served. `asset_check.py` only parses local paths and does not open a connection.
- The snapshot and commit-splitting scripts call git and tar with fixed argument lists, `shell` off, and checked inputs.
- Redesign guidance stays inside this skill and defers to the user.
- The skill frontmatter includes version, license, and homepage.

## 1.0.1 - 2026-11-15

Security scan fixes. The polish loop is unchanged.

- A snapshot no longer deletes an existing output directory. Replacement needs `--overwrite` and the marker file this tool writes. Paths that overlap the repo, home, or the filesystem root are refused, and symlinks are not followed. The uncommitted-files check runs for every ref.
- The description is limited to browser UI work, excludes prose, documents, and non-web work, and names the optional commit-splitting helper.
- Deploy, publish, and other destructive or irreversible actions need an explicit yes. Design iteration stays autonomous.
- A content change that trips review goes through review.
- Sketches and prompts sent to an image generator need the user's authorization. Providers are not switched silently.
- The Lighthouse command is pinned to 13.6.0.
- The skill lists the tools it uses, and the snapshot and commit-splitting scripts reject unsafe arguments.

## 1.0.0 - 2026-11-10

First public release. Tested with Claude Code and Codex.

**The 10-item ruler was calibrated on 5 real Sites of the Day and 1 template site: 10 is a top Site of the Day, 9 is an average Site of the Day, 8 is Honorable Mention.**

**Awwwards is the bar the loop aims at. The projects listed in the README have not won an Awwwards award.**

The skill is a Markdown folder plus Python scripts. A batch is scored by two fresh reviewers, and a blind side-by-side against the best version so far decides whether it counts. The checks run in headless Chromium.
