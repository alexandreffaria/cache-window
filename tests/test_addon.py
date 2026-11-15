"""The add-on's borrowing and handing back of the preview range, against a
fake bpy, so the user's range is tested without Blender."""

import importlib
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon"))


class _Render:
    def __init__(self):
        self.fps = 60
        self.fps_base = 1.0
        self.resolution_x = 1920
        self.resolution_y = 1080
        self.resolution_percentage = 100


class _Editor:
    def __init__(self):
        self.use_prefetch = True
        self.use_cache_raw = False


class _Scene(dict):
    """A scene: attributes for RNA properties, items for ID properties.
    The preview range clamps like Blender's: start never after end."""

    def __init__(self, name="Edit"):
        super().__init__()
        self.name = name
        self.frame_current = 1000
        self.frame_start = 1
        self.frame_end = 10000
        self.use_preview_range = False
        self._ps = 0
        self._pe = 0
        self.render = _Render()
        self.sequence_editor = _Editor()

    @property
    def frame_preview_start(self):
        return self._ps

    @frame_preview_start.setter
    def frame_preview_start(self, v):
        self._ps = min(v, self._pe)

    @property
    def frame_preview_end(self):
        return self._pe

    @frame_preview_end.setter
    def frame_preview_end(self, v):
        self._pe = max(v, self._ps)


class _Space:
    view_type = "SEQUENCER_PREVIEW"
    proxy_render_size = "PROXY_25"


class _Area:
    type = "SEQUENCE_EDITOR"

    def __init__(self):
        self.spaces = types.SimpleNamespace(active=_Space())


class _Screen:
    def __init__(self):
        self.is_animation_playing = False
        self.areas = [_Area()]


class _Scenes(list):
    def get(self, name):
        return next((s for s in self if s.name == name), None)


class _Timers:
    def __init__(self):
        self.fns = []

    def is_registered(self, fn):
        return fn in self.fns

    def register(self, fn, **kw):
        self.fns.append(fn)

    def unregister(self, fn):
        self.fns.remove(fn)


def _fake_bpy():
    bpy = types.ModuleType("bpy")
    screen = _Screen()
    scene = _Scene()
    prefs = types.SimpleNamespace(enabled=True, behind_seconds=2.0, ahead_seconds=2.0)
    bpy.context = types.SimpleNamespace(
        scene=scene,
        window_manager=types.SimpleNamespace(windows=[types.SimpleNamespace(screen=screen)]),
        preferences=types.SimpleNamespace(
            system=types.SimpleNamespace(memory_cache_limit=4096),
            addons={"cache_window": types.SimpleNamespace(preferences=prefs)},
        ),
    )
    bpy.data = types.SimpleNamespace(scenes=_Scenes([scene]))
    handlers = types.SimpleNamespace(
        animation_playback_pre=[], save_pre=[], save_post=[], load_post=[],
        persistent=lambda fn: fn)
    bpy.app = types.SimpleNamespace(handlers=handlers, timers=_Timers())
    props = types.SimpleNamespace(
        BoolProperty=lambda **kw: None, FloatProperty=lambda **kw: None)
    bpy.props = props
    bpy.types = types.SimpleNamespace(AddonPreferences=object, SEQUENCER_MT_view=None)
    bpy.utils = types.SimpleNamespace(register_class=lambda c: None, unregister_class=lambda c: None)
    sys.modules["bpy"] = bpy
    sys.modules["bpy.app"] = bpy.app
    sys.modules["bpy.app.handlers"] = handlers
    return bpy, scene, screen, prefs


class AddonTest(unittest.TestCase):
    def setUp(self):
        self.bpy, self.scene, self.screen, self.prefs = _fake_bpy()
        for name in ("cache_window", "cache_window.window"):
            sys.modules.pop(name, None)
        self.cw = importlib.import_module("cache_window")
        # The user's own range, off, with numbers they set long ago
        self.scene._pe = 300
        self.scene._ps = 100

    def user_range(self):
        s = self.scene
        return s.use_preview_range, s.frame_preview_start, s.frame_preview_end

    def test_borrows_a_window_around_the_playhead(self):
        self.assertEqual(self.cw.tick(), self.cw.TICK)
        self.assertEqual(self.user_range(), (True, 880, 1120))
        self.assertEqual((self.scene["cache_window"]["start"], self.scene["cache_window"]["end"]), (880, 1120))

    def test_small_moves_keep_the_window(self):
        self.cw.tick()
        self.scene.frame_current = 1040
        self.cw.tick()
        self.assertEqual(self.user_range(), (True, 880, 1120))

    def test_follows_the_playhead_forward_and_back(self):
        self.cw.tick()
        self.scene.frame_current = 5000
        self.cw.tick()
        self.assertEqual(self.user_range(), (True, 4880, 5120))
        self.scene.frame_current = 200
        self.cw.tick()
        self.assertEqual(self.user_range(), (True, 80, 320))

    def test_turning_off_gives_the_users_range_back(self):
        self.cw.tick()
        self.prefs.enabled = False
        self.cw.tick()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.assertNotIn("cache_window", self.scene)

    def test_playback_gives_the_range_back(self):
        self.cw.tick()
        self.cw._on_play(self.scene, None)
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.screen.is_animation_playing = True
        self.cw.tick()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.screen.is_animation_playing = False
        self.cw.tick()
        self.assertTrue(self.scene.use_preview_range)

    def test_save_gives_the_range_back_and_waits_for_a_move(self):
        self.cw.tick()
        self.cw._on_save()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.cw._on_saved()
        self.cw.tick()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.scene.frame_current += 1
        self.cw.tick()
        self.assertTrue(self.scene.use_preview_range)

    def test_a_loaded_file_with_a_borrowed_range_gets_the_users_back(self):
        self.cw.tick()
        sys.modules.pop("cache_window", None)  # a new session
        self.cw = importlib.import_module("cache_window")
        self.cw._on_load()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.assertNotIn("cache_window", self.scene)

    def test_users_own_preview_range_is_left_alone(self):
        self.scene.use_preview_range = True
        self.cw.tick()
        self.assertEqual(self.user_range(), (True, 100, 300))
        self.assertNotIn("cache_window", self.scene)

    def test_a_range_the_user_changed_while_borrowed_is_theirs(self):
        self.cw.tick()
        self.scene.frame_preview_start = 900
        self.cw.tick()
        self.assertEqual(self.user_range(), (True, 900, 1120))
        self.assertNotIn("cache_window", self.scene)
        self.prefs.enabled = False
        self.cw.tick()
        self.assertEqual(self.user_range(), (True, 900, 1120))

    def test_no_prefetch_no_window(self):
        self.scene.sequence_editor.use_prefetch = False
        self.cw.tick()
        self.assertEqual(self.user_range(), (False, 100, 300))

    def test_switching_scenes_gives_the_old_one_back(self):
        self.cw.tick()
        other = _Scene("Other")
        self.bpy.data.scenes.append(other)
        self.bpy.context.scene = other
        self.cw.tick()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.assertTrue(other.use_preview_range)

    def test_window_fits_the_cache(self):
        self.prefs.behind_seconds = self.prefs.ahead_seconds = 60.0
        self.bpy.context.preferences.system.memory_cache_limit = 100
        self.cw.tick()
        frames = self.scene.frame_preview_end - self.scene.frame_preview_start + 1
        self.assertLessEqual(frames, 100 * 1024 * 1024 * 0.9 // (480 * 270 * 4))

    def test_the_timer_never_raises(self):
        self.bpy.context.scene = types.SimpleNamespace(name="Broken")
        self.assertEqual(self.cw.tick(), self.cw.IDLE_TICK)

    def test_register_and_unregister(self):
        self.cw.register()
        self.assertIn(self.cw.tick, self.bpy.app.timers.fns)
        self.assertIn(self.cw._on_play, self.bpy.app.handlers.animation_playback_pre)
        self.cw.tick()
        self.cw.unregister()
        self.assertEqual(self.user_range(), (False, 100, 300))
        self.assertNotIn(self.cw.tick, self.bpy.app.timers.fns)
        self.assertEqual(self.bpy.app.handlers.save_pre, [])


if __name__ == "__main__":
    unittest.main()
