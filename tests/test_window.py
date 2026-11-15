"""The window math, without Blender."""

import importlib.util
import os
import unittest

# Loaded by path: the package's __init__ needs bpy, window.py doesn't
_spec = importlib.util.spec_from_file_location("cache_window_math", os.path.join(
    os.path.dirname(__file__), "..", "addon", "cache_window", "window.py"))
window = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(window)


class PlanTest(unittest.TestCase):
    def test_around_the_playhead(self):
        self.assertEqual(window.plan(500, 1, 10000, 240, 240), (260, 740))

    def test_near_the_start_gives_the_rest_to_ahead(self):
        self.assertEqual(window.plan(50, 1, 10000, 240, 240), (1, 481))

    def test_near_the_end_gives_the_rest_to_behind(self):
        self.assertEqual(window.plan(9990, 1, 10000, 240, 240), (9520, 10000))

    def test_window_bigger_than_the_scene_is_the_scene(self):
        self.assertEqual(window.plan(50, 1, 100, 240, 240), (1, 100))

    def test_playhead_outside_the_scene_is_clamped(self):
        self.assertEqual(window.plan(-30, 1, 10000, 10, 10), (1, 21))
        self.assertEqual(window.plan(20000, 1, 10000, 10, 10), (9980, 10000))

    def test_shrinks_to_the_budget_keeping_the_ratio(self):
        self.assertEqual(window.plan(1000, 1, 10000, 300, 100, budget=201), (850, 1050))

    def test_budget_counts_the_playhead_frame(self):
        start, end = window.plan(1000, 1, 10000, 240, 240, budget=101)
        self.assertEqual(end - start + 1, 101)

    def test_tiny_or_zero_budget_gives_no_window(self):
        self.assertIsNone(window.plan(1000, 1, 10000, 240, 240, budget=0))
        self.assertIsNone(window.plan(1000, 1, 10000, 240, 240, budget=2))

    def test_zero_seconds_gives_no_window(self):
        self.assertIsNone(window.plan(1000, 1, 10000, 0, 0))

    def test_only_ahead(self):
        self.assertEqual(window.plan(1000, 1, 10000, 0, 60), (1000, 1060))

    def test_empty_scene_gives_no_window(self):
        self.assertIsNone(window.plan(5, 10, 1, 10, 10))


class ShouldMoveTest(unittest.TestCase):
    def test_first_window(self):
        self.assertTrue(window.should_move(500, None, (260, 740)))

    def test_no_target_never_moves(self):
        self.assertFalse(window.should_move(500, (260, 740), None))
        self.assertFalse(window.should_move(500, None, None))

    def test_small_steps_keep_it(self):
        current = (260, 740)
        for frame in (400, 500, 600, 620):
            self.assertFalse(window.should_move(frame, current, window.plan(frame, 1, 10000, 240, 240)), frame)

    def test_moves_near_an_edge(self):
        current = (260, 740)
        self.assertTrue(window.should_move(625, current, window.plan(625, 1, 10000, 240, 240)))
        self.assertTrue(window.should_move(375, current, window.plan(375, 1, 10000, 240, 240)))

    def test_moves_when_the_playhead_jumps_out(self):
        self.assertTrue(window.should_move(5000, (260, 740), window.plan(5000, 1, 10000, 240, 240)))

    def test_moves_when_the_size_changes(self):
        self.assertTrue(window.should_move(500, (260, 740), window.plan(500, 1, 10000, 120, 120)))

    def test_stays_at_the_scene_start(self):
        current = window.plan(10, 1, 10000, 240, 240)
        self.assertFalse(window.should_move(3, current, window.plan(3, 1, 10000, 240, 240)))


class StepsTest(unittest.TestCase):
    def test_grows_behind_a_band_at_a_time_then_full(self):
        self.assertEqual(window.steps(1000, (760, 1240), 60), [
            (940, 1060), (880, 1060), (820, 1060), (760, 1060), (760, 1240)])

    def test_each_step_contains_the_one_before(self):
        out = window.steps(1000, (700, 1300), 70)
        for a, b in zip(out, out[1:]):
            self.assertLessEqual(b[0], a[0])
            self.assertGreaterEqual(b[1], a[1])

    def test_last_step_is_the_full_window(self):
        self.assertEqual(window.steps(1000, (760, 1240), 60)[-1], (760, 1240))
        self.assertEqual(window.steps(1000, (760, 1240), 10_000), [(760, 1240)])

    def test_nothing_behind(self):
        self.assertEqual(window.steps(1, (1, 481), 60), [(1, 61), (1, 481)])

    def test_nothing_ahead(self):
        self.assertEqual(window.steps(100, (40, 100), 30), [(70, 100), (40, 100)])

    def test_never_more_than_max_steps_behind(self):
        out = window.steps(100_000, (64_000, 136_000), 60)
        self.assertLessEqual(len(out), window.MAX_STEPS + 1)
        self.assertEqual(out[-1], (64_000, 136_000))

    def test_tiny_step_still_moves(self):
        out = window.steps(10, (5, 15), 0)
        self.assertEqual(out[0], (9, 11))
        self.assertEqual(out[-1], (5, 15))


class BudgetTest(unittest.TestCase):
    def test_preview_scale(self):
        self.assertEqual(window.preview_scale("PROXY_25", 100), 0.25)
        self.assertEqual(window.preview_scale("SCENE", 50), 0.5)
        self.assertEqual(window.preview_scale("NONE", 100), 0.0)
        self.assertEqual(window.preview_scale("PROXY_x", 100), 1.0)

    def test_frames_in_budget(self):
        final = window.frame_bytes(1920, 1080, 0.25)
        self.assertEqual(final, 480 * 270 * 4)
        self.assertEqual(window.frames_in_budget(4096, final), int(4096 * 1024 * 1024 * 0.9 // final))

    def test_raw_cache_costs_frames(self):
        final = window.frame_bytes(1920, 1080, 0.25)
        raw = window.frame_bytes(1920, 1080, 1.0)
        self.assertLess(window.frames_in_budget(4096, final, raw), window.frames_in_budget(4096, final))

    def test_no_limit(self):
        self.assertIsNone(window.frames_in_budget(0, 100))


if __name__ == "__main__":
    unittest.main()
