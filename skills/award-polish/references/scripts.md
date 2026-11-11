# Script usage

`S=<skill dir>/scripts` (`<skill dir>` is explained in SKILL.md "Where the scripts are"). All browser scripts use headless Python Playwright; on an 8GB machine run one at a time.

**Steps files** (shared by layout_check states, record_moment and sound_levels): a JSON array, one action per item:
`{"click": selector}`, `{"hover": selector}`, `{"fill": selector, "value": text}`, `{"press": "Enter"}`, `{"scroll": pixels}`, `{"js": code}`, `{"wait": ms}`, `{"wait_for": selector}`. Clicks go to the first visible match.

## Layout check: layout_check.py

```
python3 $S/layout_check.py <url...> --widths 375,768,1024,1280,1440 --out <dir> [--keep name=selector] [--states states.json] [--slices 8] [--forbid "—,–"] [--clock 2026-11-09T12:30]
```

- Takes a full-page screenshot at each width and checks horizontal overflow, elements off screen, clipped outlines and shadows, truncated text, h1 over 2 lines, console errors, broken images and failed requests (analytics and ad requests ignored); writes `report.json`.
- `--keep`: measures key elements in the first screen; outside the first screen or covered by a banner or overlay fails; prints a y-value table per width. Run pages with different key elements separately. For laptop screens add `--widths 1536 --height 864` and `--widths 1280 --height 800`.
- `--states`: states after interaction. Each item is `{"name", "url", "steps"}`; the script clicks there at every width and checks again.
- `--slices 8`: one image per screen, for reviewers and the anchor set. `--forbid`: strings that must not appear. `--clock`: freezes the clock so greetings and opening hours give the same result every run.
- Three report-only fields that do not fail: `smallTargets` (hit area under 44px, counting absolutely positioned `::before` / `::after`, phone widths only), `smallVisible` (visible size under 44px with a big enough hit area), `smallText` (rendered size, ancestor scaling included, under 12px). On scaled canvases all three count as failures.
- Every `clipped` entry carries `over` (pixels past the edge) and `kind`: `shadow` means only the outline or shadow crosses, usually invisible at a few pixels; `box` means the element itself crosses, including intentionally cropped images. Elements under a zero-opacity ancestor and 1px screen-reader text are skipped.
- Check every reported item; for anything you call a false positive, write one line why. A whole interface inside a frame that scrolls sideways is only checked at its design width.

## Site assets: asset_check.py

`python3 $S/asset_check.py <site dir> [--skip subdir]`: no browser; checks that every local file referenced by each HTML and CSS file (src, srcset, href, poster, url()) exists on disk, exit code 1 if anything is missing. The layout check only covers pages it opened; this covers the whole site in seconds.

## Review snapshot: snapshot.py

`python3 $S/snapshot.py <repo> <site dir> <snapshot dir> [--ref HEAD] [--link path-in-snapshot=real-path] [--skip subdir]`: exports from a commit only (git archive), refuses when the site directory has uncommitted files, and runs asset_check afterwards. Large files kept out of git are symlinked in with `--link`. Projects with a build step build from a clean checkout instead.

## Signature moment frames: record_moment.py

`python3 $S/record_moment.py <url> --steps steps.json --out <dir> --every 40 [--phone]`: add `"frames": 800` (milliseconds to record) to the step to record, optionally `"name"`. A virtual clock drives JS and CSS animations, so a busy machine drops no frames. Writes `contact-NN.png` (each frame labelled in ms), `animations.json` (duration, easing, delay, View Transition pseudo-elements included) and `motion.json` (from which ms to which ms the picture moves). Warns when the last frame is still moving, meaning frames is too short.

## Sound levels: sound_levels.py

`python3 $S/sound_levels.py <url> --steps steps.json --out levels.json [--phone] [--fake-mic]`: taps the WebAudio output with a probe (test browser only) and records each step's peak level (0 silent, 1 full scale) and played media files. Steps may add `"label"` and `"listen"` (ms to listen, default 700); `wait` and `wait_for` only wait and are not measured. The browser creates audio on the first click, so start with a warm-up click. `--fake-mic` feeds a test tone as the microphone with permission granted.

## Review prompts: review_prompt.py

```
python3 $S/review_prompt.py --config <review.json> --anchor-shots <anchor screenshots> --current <this version's screenshots> --round <.work/rN> [--best <best version screenshots>] [--live-best <best version URL>]
```

Copies the screenshot sets into the round directory under names that do not reveal their source, randomly assigns A/B and C/D per reviewer, and writes `prompt-r1.md`, `prompt-r2.md` and the mapping `blind.json`. The config is copied from `templates/review.json`; the template is `templates/REVIEW_PROMPT.md`, and review rules change only there.

## Scoring: calibrate.py

```
python3 $S/calibrate.py --round <.work/rN> --anchor <anchor.json> --model "<model effort>" [--best <best.json>] [--save <best.json>] [--live-anchor]
```

Finds the anchor set via blind.json, calibrates each item (at most ±1 by default; with screenshots only, motion, micro-interactions, usability and retention are not calibrated unless `--live-anchor`), averages, decides by the C/D blind comparison, and prints a last line ready for the log. `--save` writes best.json only on "new best version". **Keep the algorithm fixed within a round**: copy the script into the project's work directory at kickoff and use that copy for the whole round.

## Before/after: side_by_side.py

```
python3 $S/side_by_side.py --urls "Before=<url>" "After=<url>" [third column] --pages / <key page> --widths 1440,375 --out <dir> [--dismiss <banner close button>] [--clock ...] [--full]
```

Each column gets a fresh browser context; the same page and width are screenshotted and stitched with labels. URLs may include a subpath (`http://localhost:8790/a/`). To stitch existing images: `side_by_side.py img1 img2 --labels Before,After --out x.png`.

## Search fields: seo_keep.py

`python3 $S/seo_keep.py --base <live> --new <local> --pages <pages…> [--sitemap N] [--files /robots.txt /sitemap.xml] [--dump refs/seo-baseline.json]`: compares title, description, canonical, hreflang, robots, structured data types, H1, lang and share card fields page by page; any difference exits with code 1. `--dump` saves the base fields as the search baseline.

## Wait for release: wait_live.py

`python3 $S/wait_live.py <url> --has <string only the new version has> [--gone <old string>] [--timeout 1500]`: opens the page with a fresh `?v=` each round and checks the page plus the stylesheets and scripts it references, so a CDN still serving old CSS is caught.

## Split commits: split_commits.py

For when changes piled up in the working tree (the normal way is to commit each change right away). The split is a JSON file:

```
{"ctx": {"styles.css": 1},
 "items": [
   {"name": "hero", "msg": "commit message", "hunks": {"src/site.js": ["keyword"], "pages/*/index.html": ["keyword"]}},
   {"name": "palette", "msg": "…", "files": ["assets/raw"]},
   {"name": "stamps", "msg": "…", "files": ["pages"], "only": "?v="}]}
```

- `hunks`: a hunk belongs to this item when any added or removed line contains a keyword; paths with `*` are globbed. `files`: whole files or directories for this item.
- `only`: after staging, every added or removed line must contain this string, otherwise the commit is refused. Put site-wide changes like asset fingerprints last and guard them with it.
- `ctx`: context lines, default 3; use 1 when changes are a line or two apart; never 0 (when part of a zero-context diff is staged, git apply places later hunks at stale line numbers).
- `python3 $S/split_commits.py <repo> <split.json> plan` lists hunks with no owner or two owners; adjust keywords until everything is clear, then `run [--dry] [--items a,b] [--sign "Co-Authored-By: …"]` commits item by item. Pick keywords that belong to one item only; a class name several items share puts a hunk in two items.
