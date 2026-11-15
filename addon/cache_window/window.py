"""Where the cache window goes. No bpy here, so it's tested without Blender.

Blender's prefetch renders from just behind the playhead to the end of the
playback range, then wraps to its start, and the cache never drops frames
inside the range prefetch is working on. Setting the preview range to a
window around the playhead therefore caches both sides of it. These
functions pick that window and decide when to move it.
"""

# Leave some of the memory cache for whatever else Blender caches
BUDGET_SHARE = 0.9
# 8-bit RGBA, what the VSE caches for video. Float images take 16, so a
# project with float strips can overrun the estimate; the cache then drops
# the frames farthest from the playhead, as without the add-on.
BYTES_PER_PIXEL = 4
MIN_FRAMES = 3  # a window smaller than this isn't worth borrowing the range


def preview_scale(size, render_percentage):
    """The size the preview renders at, as a fraction of the scene's
    resolution, for a SpaceSequenceEditor.proxy_render_size value."""
    if size == "SCENE":
        return max(render_percentage, 1) / 100.0
    if size.startswith("PROXY_"):
        try:
            return int(size[len("PROXY_"):]) / 100.0
        except ValueError:
            return 1.0
    return 0.0  # NONE: no preview drawn


def frame_bytes(width, height, scale):
    """Bytes one cached frame of a width x height scene takes at scale."""
    w = max(int(width * scale), 1)
    h = max(int(height * scale), 1)
    return w * h * BYTES_PER_PIXEL


def frames_in_budget(limit_mb, final_bytes, raw_bytes=0):
    """How many frames fit in Blender's memory cache limit (MB), with each
    frame costing its final image plus, when the raw cache is on, its
    source image. None when there is no limit to respect."""
    if limit_mb <= 0:
        return None
    per_frame = final_bytes + raw_bytes
    if per_frame <= 0:
        return None
    return int(limit_mb * 1024 * 1024 * BUDGET_SHARE // per_frame)


def plan(frame, scene_start, scene_end, behind, ahead, budget=None):
    """The (start, end) window for a playhead at frame, with behind frames
    before it and ahead after it, shrunk to fit budget frames and kept
    inside the scene. Where the scene ends on one side, the frames that
    don't fit there go to the other side. None when no useful window fits."""
    if scene_end < scene_start:
        return None
    behind = max(int(behind), 0)
    ahead = max(int(ahead), 0)
    if budget is not None:
        room = int(budget) - 1  # the playhead's own frame
        if room < MIN_FRAMES - 1:
            return None
        if behind + ahead > room:
            total = behind + ahead
            behind = behind * room // total
            ahead = room - behind
    if behind + ahead + 1 < MIN_FRAMES:
        return None
    frame = min(max(int(frame), scene_start), scene_end)
    start = frame - behind
    end = frame + ahead
    if start < scene_start:
        end += scene_start - start
        start = scene_start
    if end > scene_end:
        start -= end - scene_end
        end = scene_end
    start = max(start, scene_start)
    return start, end


def should_move(frame, current, target):
    """Whether to move the window from current to target for a playhead at
    frame. It moves when there is none yet, when its size changed, when
    the playhead left it, or when the playhead got within half the wanted
    distance of either edge. Otherwise it stays put, so the cached frames
    stay protected while you rock back and forth."""
    if target is None:
        return False
    if current is None or current == target:
        return current is None
    start, end = current
    t_start, t_end = target
    if end - start != t_end - t_start:
        return True
    if frame < start or frame > end:
        return True
    want_behind = frame - t_start
    want_ahead = t_end - frame
    return (frame - start) * 2 < want_behind or (end - frame) * 2 < want_ahead
