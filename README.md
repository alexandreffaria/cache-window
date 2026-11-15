# Cache Window

A Blender extension for the video editor (VSE) that keeps the cache **around
the playhead** instead of only ahead of it. Step back a few frames while
editing and they're still there, with no stall while Blender decodes them
again.

## Why

Blender's prefetch only renders frames *ahead* of the playhead. When the
memory cache is full, Blender drops the frames farthest from the playhead,
and frames *behind* it count as twice as far. So the moment you step back,
the frames you just watched are often gone.

Python can't touch the cache. But prefetch wraps around inside the playback
range, and the cache never drops frames in the range prefetch is working
on. So while you're paused, this add-on sets the **preview range** to a
window around the playhead (4 s behind and 4 s ahead by default). Prefetch
fills both sides, and the cache keeps them. When the playhead gets near an
edge of the window, the window moves with it.

## What you'll notice

- While paused, the timeline outside the window is shaded, as with any
  preview range. That's the window.
- Jump to Endpoint (Shift+Left/Right) jumps to the window's edges while
  paused, since it follows the preview range.
- Switch the window off with the timeline's preview-range toggle and your
  own numbers come back. The window returns when the playhead moves.
- When playback starts, the range is handed back right away, so playback
  runs over the whole scene. When you stop, the window comes back.
- If you turn on or change the preview range yourself, yours wins. The
  add-on stays out until you clear it (Alt+P or View › Range › Clear
  Preview Range).
- Your preview range is put back before every save, so saved files never
  hold the window.
- The window shrinks to fit the Memory Cache Limit (Preferences › System ›
  Memory & Limits).

## Install

Download `cache-window.zip` from the latest CI run (or build it with
`python scripts/build_addon.py`), then in Blender: Edit › Preferences › Get
Extensions › ⌄ › Install from Disk. Needs Blender 4.2 or newer.

Turn it on or off from the Sequencer's **View** menu (Cache Around
Playhead). Set the seconds behind and ahead in the add-on's preferences.

## Tips

- **Use proxies.** With 25% proxies and the preview at 25%, a frame is about
  16 times smaller, so the same memory holds a much longer window.
- **Turn off the raw cache** (Sidebar › Cache › Raw Images) unless you're
  tweaking strip settings. It stores full-size source frames, which can
  take most of the memory cache and squeeze the window.
- Prefetch must be on (Preview › View › Prefetch Frames), since that's what
  fills the window.

## For other add-ons

While the range is borrowed, the scene has a `cache_window` property with
the `start` and `end` the add-on set. If your add-on treats the preview
range as the playback range, ignore it when
`scene.get("cache_window")` matches `frame_preview_start` and
`frame_preview_end`.

## Development

See [CLAUDE.md](CLAUDE.md).
