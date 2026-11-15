"""Cache Window: keeps the video editor's cache around the playhead.

Blender's prefetch only fills frames ahead of the playhead, and drops the
ones behind it first. Python can't reach the cache, but prefetch wraps
inside the playback range, so this add-on borrows the preview range as a
window around the playhead while you're paused: prefetch fills both sides
and the cache keeps them. The window moves when the playhead nears an edge
and is handed back whenever playback starts, before a save, and when the
add-on is turned off.

While the range is borrowed, the scene has a "cache_window" property with
the "start" and "end" it set. Other add-ons that treat the preview range as
the playback range can check it and ignore a borrowed range.
"""

import bpy
from bpy.app.handlers import persistent

from . import window

MARKER = "cache_window"
TICK = 0.1  # seconds between checks while working
IDLE_TICK = 0.5  # while turned off or nothing to do

# "scene": name of the scene whose range is borrowed, so it's handed back
# when the window shows another scene. "hold": (scene name, frame) after a
# save; the range isn't borrowed again until the playhead moves, so a file
# just saved doesn't show as changed right away.
_state = {"scene": None, "hold": None}


# The user's preview range and the borrowed one


def _marker(scene):
    """The add-on's record on scene, as a dict, or None."""
    try:
        m = scene.get(MARKER)
    except Exception:
        return None
    if m is None:
        return None
    try:
        return {k: int(m[k]) for k in ("start", "end", "user_start", "user_end")}
    except Exception:
        return None


def _is_ours(scene, m):
    """Whether the preview range on scene is still the one the add-on set."""
    return (m is not None and scene.use_preview_range
            and scene.frame_preview_start == m["start"]
            and scene.frame_preview_end == m["end"])


def _drop_marker(scene):
    try:
        if MARKER in scene:
            del scene[MARKER]
    except Exception:
        pass


def _set_range(scene, start, end):
    """Sets the preview range in an order Blender won't clamp: it keeps the
    start at or before the end at every step. Only while the range is on:
    while it's off, Blender resets the other end to the scene's on every
    set."""
    if start > scene.frame_preview_end:
        scene.frame_preview_end = end
        scene.frame_preview_start = start
    else:
        scene.frame_preview_start = start
        scene.frame_preview_end = end


def release(scene):
    """Hands the preview range back on scene: turns it off and puts the
    user's numbers back, unless the user changed it meanwhile, in which
    case theirs stays. Safe to call any time."""
    if scene is None:
        return
    m = _marker(scene)
    if m is not None and (_is_ours(scene, m) or _turned_off(scene, m)):
        _give_back(scene, m)
    _drop_marker(scene)
    if _state["scene"] == scene.name:
        _state["scene"] = None


def _turned_off(scene, m):
    """Whether the user switched the borrowed range off without changing
    it: the numbers are still the window's."""
    return (not scene.use_preview_range
            and scene.frame_preview_start == m["start"]
            and scene.frame_preview_end == m["end"])


def _give_back(scene, m):
    """Puts the user's numbers back and leaves the range off."""
    scene.use_preview_range = True
    _set_range(scene, m["user_start"], m["user_end"])
    scene.use_preview_range = False


def release_all():
    for scene in bpy.data.scenes:
        try:
            release(scene)
        except Exception as e:
            print("Cache Window: couldn't hand back the range of", scene.name, e)
    _state["scene"] = None


def borrow(scene, start, end):
    """Sets the window to start..end on scene, remembering the user's range
    the first time."""
    m = _marker(scene)
    if m is None:
        m = {"user_start": scene.frame_preview_start,
             "user_end": scene.frame_preview_end}
    scene.use_preview_range = True
    _set_range(scene, start, end)
    m["start"] = scene.frame_preview_start
    m["end"] = scene.frame_preview_end
    scene[MARKER] = m
    _state["scene"] = scene.name


# Where the window should be


def _prefs():
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except Exception:
        return None


def _is_playing():
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", ()):
        screen = getattr(win, "screen", None)
        if screen is not None and getattr(screen, "is_animation_playing", False):
            return True
    return False


def _budget(scene):
    """How many frames the memory cache holds at the preview's size, or
    None when that's unknown."""
    try:
        limit = bpy.context.preferences.system.memory_cache_limit
    except Exception:
        return None
    r = scene.render
    pct = getattr(r, "resolution_percentage", 100)
    scale = 0.0
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", ()):
        screen = getattr(win, "screen", None)
        for area in getattr(screen, "areas", ()):
            if area.type != "SEQUENCE_EDITOR":
                continue
            space = area.spaces.active
            if getattr(space, "view_type", "") == "SEQUENCER":
                continue
            scale = max(scale, window.preview_scale(
                getattr(space, "proxy_render_size", "SCENE"), pct))
    if scale <= 0:
        scale = pct / 100.0
    final = window.frame_bytes(r.resolution_x, r.resolution_y, scale)
    # The raw cache holds source images, which can be full size even when
    # the preview is smaller
    raw = 0
    if getattr(scene.sequence_editor, "use_cache_raw", False):
        raw = window.frame_bytes(r.resolution_x, r.resolution_y, 1.0)
    return window.frames_in_budget(limit, final, raw)


def target(scene, prefs):
    fps = scene.render.fps / (scene.render.fps_base or 1.0)
    return window.plan(
        scene.frame_current, scene.frame_start, scene.frame_end,
        round(prefs.behind_seconds * fps), round(prefs.ahead_seconds * fps),
        _budget(scene))


def update(scene, prefs):
    """One step: borrow, move or hand back the range on scene. Returns the
    seconds until the next step."""
    if prefs is None or not prefs.enabled:
        release_all()
        return IDLE_TICK
    if _state["scene"] not in (None, scene.name):
        other = bpy.data.scenes.get(_state["scene"])
        release(other)
        _state["scene"] = None
    ed = scene.sequence_editor
    if ed is None or not getattr(ed, "use_prefetch", False) or _is_playing():
        release(scene)
        return TICK if ed is not None else IDLE_TICK
    hold = _state["hold"]
    if hold is not None:
        if hold == (scene.name, scene.frame_current):
            return TICK
        _state["hold"] = None
    m = _marker(scene)
    if m is not None and _turned_off(scene, m):
        # The user switched the window off: give their numbers back and
        # wait for the playhead to move before borrowing again
        _give_back(scene, m)
        _drop_marker(scene)
        _state["scene"] = None
        _state["hold"] = (scene.name, scene.frame_current)
        return TICK
    if m is not None and not _is_ours(scene, m):
        # The user changed the range while it was borrowed: it's theirs now
        _drop_marker(scene)
        _state["scene"] = None
        m = None
    if m is None and scene.use_preview_range:
        return IDLE_TICK  # the user's own preview range is on: stay out
    want = target(scene, prefs)
    if want is None:
        release(scene)
        return IDLE_TICK
    current = (m["start"], m["end"]) if m is not None else None
    if window.should_move(scene.frame_current, current, want):
        borrow(scene, *want)
    return TICK


def tick():
    """The timer. Never raises: an exception would stop it for good."""
    try:
        scene = bpy.context.scene
        if scene is None:
            return IDLE_TICK
        return update(scene, _prefs())
    except Exception as e:
        print("Cache Window: skipped a step:", e)
        return IDLE_TICK


# Moments the range must be handed back right away


@persistent
def _on_play(scene, *args):
    try:
        release(scene)
    except Exception as e:
        print("Cache Window: couldn't hand back the range on play:", e)


@persistent
def _on_save(*args):
    release_all()


@persistent
def _on_saved(*args):
    try:
        scene = bpy.context.scene
        _state["hold"] = (scene.name, scene.frame_current)
    except Exception:
        _state["hold"] = None


@persistent
def _on_load(*args):
    # A file saved by a Blender that crashed with the range borrowed
    release_all()


# Preferences and UI


def _toggle_changed(self, context):
    if not self.enabled:
        release_all()


class CacheWindowPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enabled: bpy.props.BoolProperty(
        name="Cache Around Playhead",
        description="Keep frames cached on both sides of the playhead while paused, "
                    "by borrowing the preview range",
        default=True,
        update=_toggle_changed,
    )
    behind_seconds: bpy.props.FloatProperty(
        name="Behind", description="Seconds to keep cached before the playhead",
        default=4.0, min=0.0, max=600.0, unit="TIME_ABSOLUTE",
    )
    ahead_seconds: bpy.props.FloatProperty(
        name="Ahead", description="Seconds to keep cached after the playhead",
        default=4.0, min=0.0, max=600.0, unit="TIME_ABSOLUTE",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enabled")
        row = layout.row()
        row.prop(self, "behind_seconds")
        row.prop(self, "ahead_seconds")
        layout.label(text="The window shrinks to fit the Memory Cache Limit "
                          "(Preferences › System).")


def _draw_menu(self, context):
    prefs = _prefs()
    if prefs is not None:
        self.layout.separator()
        self.layout.prop(prefs, "enabled")


_HANDLERS = (
    ("animation_playback_pre", _on_play),
    ("save_pre", _on_save),
    ("save_post", _on_saved),
    ("load_post", _on_load),
)


def register():
    bpy.utils.register_class(CacheWindowPreferences)
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name, None)
        if lst is not None and fn not in lst:
            lst.append(fn)
    menu = getattr(bpy.types, "SEQUENCER_MT_view", None)
    if menu is not None:
        menu.append(_draw_menu)
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick, first_interval=IDLE_TICK, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    release_all()
    menu = getattr(bpy.types, "SEQUENCER_MT_view", None)
    if menu is not None:
        menu.remove(_draw_menu)
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name, None)
        if lst is not None and fn in lst:
            lst.remove(fn)
    bpy.utils.unregister_class(CacheWindowPreferences)
