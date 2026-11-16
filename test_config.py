import tempfile
import tomllib
import unittest
from pathlib import Path

import config


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()  # never the project's own config.toml
        self.path = Path(self.dir.name) / "config.toml"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_created_from_example_with_defaults(self):
        cfg = config.load(self.path)
        self.assertEqual(self.path.read_bytes(), config.EXAMPLE.read_bytes())
        self.assertEqual(cfg, config.Config())
        self.assertIsNone(cfg.home_key)

    def test_set_changes_one_line_only(self):
        config.load(self.path)
        before = self.path.read_bytes().splitlines(keepends=True)
        config.set("radius_miles", 30, self.path)
        after = self.path.read_bytes().splitlines(keepends=True)
        self.assertEqual(len(before), len(after))
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(after[changed[0]], b"radius_miles = 30\n")
        self.assertEqual(config.load(self.path).radius_miles, 30)

    def test_set_uncomments_an_unset_key(self):
        config.set("home_key", "38.577,-121.495", self.path)
        self.assertEqual(config.load(self.path).home_key, "38.577,-121.495")
        self.assertEqual(self.path.read_text().count("home_key"), 1)

    def test_set_quotes_strings_safely(self):
        config.set("llm_model", 'a "quoted" \\ name', self.path)
        self.assertEqual(config.load(self.path).llm_model, 'a "quoted" \\ name')

    def test_set_keeps_crlf_line_endings(self):
        self.path.write_bytes(b"# note\r\nradius_miles = 20\r\nrouting = \"estimate\"\r\n")
        config.set("routing", "osrm", self.path)
        self.assertEqual(self.path.read_bytes(), b"# note\r\nradius_miles = 20\r\nrouting = \"osrm\"\r\n")

    def test_set_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            config.set("radius_mile", 5, self.path)

    def test_set_none_raises(self):
        with self.assertRaises(ValueError):
            config.set("llm_key", None, self.path)

    def test_bad_routing_raises(self):
        self.path.write_text('routing = "tomtom"\n')
        with self.assertRaises(ValueError):
            config.load(self.path)

    def test_misspelt_key_raises(self):
        self.path.write_text("radius_mile = 5\n")
        with self.assertRaises(TypeError):
            config.load(self.path)

    def test_example_is_valid_toml_and_every_setting_is_described(self):
        lines = config.EXAMPLE.read_text().splitlines()
        tomllib.loads("\n".join(lines))
        for field in config.dataclasses.fields(config.Config):
            i = next(i for i, l in enumerate(lines) if l.lstrip("# ").startswith(field.name + " ="))
            self.assertTrue(lines[i - 1].startswith("# ") and "=" not in lines[i - 1], field.name)


if __name__ == "__main__":
    unittest.main()
