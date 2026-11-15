---
name: review-pr
description: Second review of a Cache Window pull request against .github/REVIEW_CHECKLIST.md before it's merged. Use when asked to review a PR, run the checklist, or "/review-pr <number>".
argument-hint: <pr-number>
---

# Review PR $ARGUMENTS

You are the second reviewer: you didn't write this PR, and your job is to
find what would break Blender, lose the user's preview range, or break the
repo, not to restyle it. Don't push commits to the PR; report.

1. Read `.github/REVIEW_CHECKLIST.md`, then `CLAUDE.md`'s "Rules".
2. Gather the PR:
   ```sh
   gh pr view $ARGUMENTS --json number,title,body,baseRefName,headRefName,headRefOid,files,additions,deletions
   gh pr diff $ARGUMENTS
   gh pr checks $ARGUMENTS
   gh pr list --state open
   ```
3. Check out the head into a separate worktree (never switch the main
   checkout's branch) and run the mechanical checks and CLAUDE.md's
   "Before you push" commands there:
   ```sh
   git fetch origin main pull/$ARGUMENTS/head:review/pr-$ARGUMENTS
   git worktree add ../cache-window-review-$ARGUMENTS review/pr-$ARGUMENTS
   bash scripts/pr-guard.sh origin/main review/pr-$ARGUMENTS
   ```
   Remove the worktree when done (`git worktree remove`).
4. Read the changed code, not only the diff hunks: for each item, look for
   the concrete way it goes wrong (a path where the user's range is lost, a
   handler that raises, playback that loops inside the borrowed window, a
   window that leaves the scene range). Go through the 12 items in order.
   For each, decide **pass**, **fail** or **n/a**; for a fail give
   file:line and one sentence on what goes wrong.
5. If CI is still running, say so; don't mark item 11 pass until it's green.
6. Post the result on the PR, then give the same text in your reply:
   ```sh
   gh pr comment $ARGUMENTS --body-file <file>
   ```
   Format: a first line `Second review: ready to merge` or
   `Second review: N item(s) to fix`, then a table `| # | Item | Result | Note |`
   with all 12 rows, then any other bugs found under "Other findings". Keep
   notes to one sentence, plain words.
