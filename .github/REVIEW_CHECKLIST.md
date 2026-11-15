# PR review checklist

Run against every pull request's diff before it's merged, by an agent that
didn't write it (`/review-pr <number>`). Each line is pass, fail or n/a, with
the file and line for every fail. One fail means don't merge yet.

Items marked **CI** are also enforced by `.github/workflows/pr-guard.yml`;
the reviewer still confirms the check is green.

## Shape

1. **CI** Base branch is `main` and the head is not `main`.
2. **CI** At most 2 PRs open, this one included.
3. **CI** No file over 1 MB, no binaries other than images and fonts (no
   `.zip`, `.blend`), no `.env` or key files.
4. No secrets or personal data in the diff (tokens, emails, local paths
   with a user name).
5. No files under `decisions/` (president's cards travel by Sync).

## Add-on

6. The timer can't raise or stall Blender's UI: everything it calls is
   inside its try/except, it does no per-strip or per-frame loops, no
   operators, no file or network access.
7. The user's preview range survives: it is restored when the add-on is
   turned off or unregistered, before every save, when playback starts, and
   on file load if a saved file still holds a borrowed range; a range the
   user changed while borrowed is kept, not overwritten.
8. The `cache_window` scene property matches the range the add-on set, and
   is removed whenever the range is given back.
9. The window math in `window.py` stays inside the scene's frame range and
   the cache budget, and has tests for its edges (scene start and end,
   window bigger than the scene, zero or tiny budget).

## Tests and CI

10. The change has tests: a bug fix has a test that fails without it, a
    feature has tests for its main path and its edges.
11. The commands in CLAUDE.md's "Before you push" pass, and CI is green.
12. The PR description says what changed, why, and how it was tried in
    Blender (or why it wasn't).
