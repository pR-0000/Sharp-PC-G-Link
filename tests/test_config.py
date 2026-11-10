import configparser
import json
from pathlib import Path
import tempfile
import unittest

from sharp_link.config import DEFAULTS, load_settings, save_settings


class ConfigTests(unittest.TestCase):
    def test_expanded_ram_defaults_off_and_roundtrips(self):
        self.assertEqual(load_settings(self.path)['expanded_ram'],'no')
        values=dict(DEFAULTS,expanded_ram='yes')
        save_settings(self.path,values)
        self.assertEqual(load_settings(self.path)['expanded_ram'],'yes')
        self.path.write_text('[assembler]\nexpanded_ram = invalid\n',encoding='utf-8')
        self.assertEqual(load_settings(self.path)['expanded_ram'],'no')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "sharp_pc_g_link.ini"

    def tearDown(self):
        self.temp.cleanup()

    def test_utf8_ini_roundtrip_and_no_json(self):
        values = dict(DEFAULTS, language="en", port="port % test é", load_address="0200")
        save_settings(self.path, values)
        self.assertEqual(load_settings(self.path), values)
        self.assertIn("[interface]", self.path.read_text(encoding="utf-8"))
        self.assertFalse(self.path.with_suffix(".ini.tmp").exists())

    def test_invalid_ini_uses_defaults(self):
        self.path.write_text("[interface\nlanguage = en", encoding="utf-8")
        self.assertEqual(load_settings(self.path), DEFAULTS)

    def test_existing_ini_takes_priority_over_legacy_json(self):
        old = Path(self.temp.name) / "settings.json"
        old.write_text(json.dumps({"baud": 9600, "rtscts": False}), encoding="utf-8")
        migrated = load_settings(self.path, old)
        self.assertEqual(migrated["baud"], "9600")
        self.assertNotIn("rtscts", migrated)
        save_settings(self.path, dict(DEFAULTS, language="en", baud="1200"))
        self.assertEqual(load_settings(self.path, old)["baud"], "1200")
        self.assertTrue(old.exists())

    def test_old_ini_cannot_turn_off_rtscts(self):
        self.path.write_text("[serial]\nrtscts = no\nbaud = 1200\n", encoding="utf-8")
        settings = load_settings(self.path)
        self.assertNotIn("rtscts", settings)
        self.assertEqual(settings["baud"], "1200")
        save_settings(self.path, settings)
        self.assertNotIn("rtscts", self.path.read_text())

    def test_old_ini_adds_framing_defaults_without_resetting_saved_preferences(self):
        self.path.write_text("[interface]\nlanguage = en\n[serial]\nport = COM7\nbaud = 300\n", encoding="utf-8")
        settings = load_settings(self.path)
        self.assertEqual((settings["language"], settings["port"], settings["baud"]), ("en", "COM7", "300"))
        self.assertEqual((settings["data_bits"], settings["parity"], settings["stop_bits"]), ("7", "N", "1"))
        settings.update(data_bits="7", parity="O", stop_bits="2")
        save_settings(self.path, settings)
        self.assertEqual(load_settings(self.path), settings)

    def test_invalid_frame_values_do_not_discard_other_ini_preferences(self):
        self.path.write_text("[serial]\nport = COM8\ndata_bits = 9\nparity = even\nstop_bits = 3\n", encoding="utf-8")
        settings = load_settings(self.path)
        self.assertEqual((settings["port"], settings["data_bits"], settings["parity"], settings["stop_bits"]),
                         ("COM8", "7", "E", "1"))


if __name__ == "__main__":
    unittest.main()
