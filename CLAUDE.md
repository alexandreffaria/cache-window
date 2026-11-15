# Cache Window

A Blender extension that keeps the video editor's cache around the playhead
instead of only ahead of it. Blender's prefetch fills frames ahead and drops
the frames behind first; Python can't touch the cache, so the add-on borrows
the preview range: prefetch wraps inside it, which fills a window on both
sides of the playhead and protects it from being dropped. See README.md.

- `addon/cache_window/window.py`: the window math. No `bpy`, so it's tested
  without Blender.
- `addon/cache_window/__init__.py`: the add-on (timer, handlers, UI).
- `tests/`: unittest, with a fake `bpy` for the add-on parts.

## How work is done

One change at a time. Each change is a branch and a PR: build it, have a
fresh agent review it, fix, review again, until the review says ready.

- **Never commit to `main` directly.** Branch from an up-to-date `main`:
  `feat/…`, `fix/…`, `chore/…` or `ci/…`.
- **At most 2 open PRs.** Run `gh pr list --state open` first. CI's PR guard
  fails a third.
- **No stacked PRs.** Every PR's base is `main`.
- **Every PR gets a second review** before merge: a fresh agent runs
  `/review-pr <number>` against `.github/REVIEW_CHECKLIST.md` and posts the
  result on the PR. Fix what it finds and ask for another review.
- **Product decisions go to president** (`decisions/`, see the
  `decision-cards` skill), not chat. Never commit files under `decisions/`
  in a PR; stage files by path. Settled decisions are recorded in
  `docs/decisions.md`.

## Rules

- The add-on's timer must never raise (it would stop for good) and must
  stay cheap: no loops over strips or frames, no operators.
- The preview range is the user's. Save it before borrowing it, put it back
  when the add-on is turned off, before a save, when playback starts, and
  never leave the borrowed range in a saved file.
- If the user changes the preview range while it's borrowed, theirs wins:
  stand down and don't overwrite it.
- Other add-ons (Blendeck's shuttle) read the preview range as the playback
  range. The scene property `cache_window` says it's borrowed; keep it in
  sync with what's set.

## Before you push

```sh
python -I -m unittest discover -s tests -v
python -m compileall -q addon scripts tests
python -I scripts/build_addon.py
```

To try it for real: install `dist/cache-window.zip` in Blender (Get
Extensions › Install from Disk), turn on the timeline's cache overlay
(Sequencer › View › Cache › Final Images) and watch the line around the
playhead.
