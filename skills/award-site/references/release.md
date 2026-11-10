# Shipping

## When to ship

- **Local by default**: build, self-check and review on localhost; ship once the finish conditions hold (or the deadline arrives), then verify everything live.
- **Deploy first**: when the user or the situation needs a reachable link up front (a submission that needs a link, a client who wants to look), ship a viewable version as fast as possible to hold the link, then keep working locally without updating the live site, and release the best version once before the deadline.
- **Staged updates**: only when someone will definitely look in between (a client checking daily, a site with real users) update the live site after a local review passes (no worse than live, no fatal problems).
- **Pushing to an auto-deploying branch is shipping** (Vercel or Cloudflare on main): no push without the user's go-ahead, and push exactly the version the user approved.

## Before shipping

- **Find everyone who deploys this site**: read the platform's recent deploys and match each one to a source by time (auto-deploys after merged PRs, scheduled jobs running a release script from some working directory, other collaborators). The shipped code has to reach every source's branch and working directory, or the next merge or scheduled job rolls the site back.
- **Record the rollback target**: the current live version and the rollback command go in the log.
- The build must pass; redesigns also pass the preservation and brand checks in `mode-redesign.md`.

## Final release

Leave time before the deadline: stop opening new batches and only fix problems; push the best version live and verify every width, the core flow, the console and images; fix problems before the deadline, or go back to the last good version and push that. The live site must work at all times.

- **Assembling the best version**: the look follows the batch that won the blind comparison; later fixes that do not change the look (errors, copy, tap targets, accessibility) stay; spots whose look changed without winning are edited back to that batch's look; run the full self-check once more before pushing.
- **The last batch is not scored yet**: ship the highest-scored batch. The unscored batch still gets its checks and is committed on the redesign branch; the log says it is not live and whether the branch was pushed. Fixes made on the live branch are merged back into the redesign branch; asset fingerprint lines will conflict, so confirm the conflicts are only fingerprints, take either side, and rerun the fingerprint script.
- **After deploying, look at the deploy working directory**: done only when `git status` is clean. Commit and push state files the deploy script changed (for example IndexNow submission records), and delete build caches it left.

## After shipping

- Wait with `wait_live.py <url> --has <string only this version has>` until the live site really serves the new version (page plus its stylesheets and scripts), then run the core flow live; sites with search traffic run `seo_keep.py` again.
- Links you send the user carry a random parameter (`?v=timestamp`): static hosts (GitHub Pages) cache pages for about 10 minutes.
- If the live site breaks: push the last good version back first (or use the platform's "roll back to previous deploy"), then fix.

## When local history contains personal information, push a clean snapshot

When early commits carry a real name and private email: `git archive` the commit to ship into a clone of the public repo, commit it with the public repo's own author identity, grep for real names, emails and anything that must stay private before pushing, keep the public repo's own README and `.nojekyll`, and leave the local `.gitignore` out.
