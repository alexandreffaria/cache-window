"""The package script puts the add-on's files at the zip's top level, where
Blender's "Install from Disk" looks for blender_manifest.toml."""

import importlib.util
import os
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_build():
    spec = importlib.util.spec_from_file_location(
        "build_addon", os.path.join(ROOT, "scripts", "build_addon.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BuildTest(unittest.TestCase):
    def test_zip_has_manifest_at_top_level(self):
        build = _load_build()
        with tempfile.TemporaryDirectory() as tmp:
            build.OUT = os.path.join(tmp, "out.zip")
            self.assertEqual(build.main(), 0)
            with zipfile.ZipFile(build.OUT) as z:
                names = z.namelist()
        self.assertIn("blender_manifest.toml", names)
        self.assertTrue(all("/" not in n for n in names), names)


if __name__ == "__main__":
    unittest.main()
