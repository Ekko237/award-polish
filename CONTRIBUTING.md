# Contributing

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Search the
[issues](https://github.com/Ekko237/award-polish/issues) before reporting a bug
or proposing a feature.

## Set up and run locally

This repo is a Markdown skill with Python helpers, not a standalone web app.
Use Python 3. The README's quick start is:

```bash
git clone https://github.com/Ekko237/award-polish && cd award-polish
pip install playwright pillow && playwright install chromium
python3 skills/award-polish/scripts/layout_check.py https://your-site.com --out check --keep "main=.your-main-button"
```

Replace the example URL and selector with your site and its main button.
The checker writes screenshots and `check/report.json`.
`asset_check.py` additionally needs beautifulsoup4 and tinycss2;
`seo_keep.py` needs requests and beautifulsoup4.
See [script usage](skills/award-polish/references/scripts.md) for other helpers.

To install your checkout for Claude Code or Codex, the README uses:

```bash
bash install.sh
```

This needs rsync and an existing `~/.claude` or `~/.codex` directory.
Alternatively, point your agent at `skills/award-polish/SKILL.md` and ask it to
"polish this site to award level"; slash commands use `/award-polish`.

## Checks

From the repo root, run both commands exactly as
[CI](.github/workflows/check-skill.yml) does:

```bash
python3 .github/scripts/check_skill_frontmatter.py
python3 -m py_compile skills/award-polish/scripts/*.py
```

CI validates skill frontmatter and compiles the Python scripts; there is no
automated test suite. For helper changes, also reproduce the affected behavior
and include the command and result in your PR. Leave generated screenshots,
reports, and `__pycache__` directories out of the change.

## Branches and pull requests

Use a descriptive branch and open a focused PR against `main`. Explain the
problem, the change, and how you checked it; link a related issue when available.
Update relevant instructions and both READMEs when shared guidance changes.
If you change folder structure, update the README tree in the same PR.
Remove secrets and personal information from examples, logs, and screenshots.

Releases use `CHANGELOG.md` entries in `version - YYYY-MM-DD` format. For a
release, keep the version in skill frontmatter, `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, and `.codex-plugin/plugin.json` consistent.
