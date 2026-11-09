from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sharp_link.config import load_settings
from sharp_link.romdump import DumpSession
from sharp_link.romdump_gui import RomDumpApp

class RomDumpGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.ports=patch('sharp_link.romdump_gui.list_ports.comports',return_value=[]);self.ports.start()
        self.app=RomDumpApp(settings_file=self.path/'prefs.ini');self.app.withdraw();self.app.update()
    def tearDown(self):
        self.app.destroy();self.ports.stop();self.temp.cleanup()
    def test_language_is_saved_and_instructions_are_translated(self):
        self.app.lang.set('English');self.app.change_language()
        self.assertIn('Create or resume',self.app.instructions.get())
        self.assertEqual(load_settings(self.path/'prefs.ini')['language'],'en')
        self.app.lang.set('Français');self.app.change_language()
        self.assertIn('Créer ou reprendre',self.app.instructions.get())
    def test_model_defaults_do_not_claim_g805_rom_size(self):
        self.app.model.set('PC-G805');self.app.change_model()
        self.assertEqual(self.app.banks.get(),'16')
        self.assertIn('ne prouve pas la capacité',self.app.note.get())
        self.app.model.set('PC-G801');self.app.change_model();self.assertEqual(self.app.banks.get(),'5')
    def test_next_and_independent_read_commands_are_distinct(self):
        self.app.session=DumpSession.create(self.path/'rom','PC-G801',4)
        self.app.update_step();self.assertIn('USER1400',self.app.instructions.get())
        self.app.agent_loaded=True
        self.app.update_step();self.assertIn('G100',self.app.instructions.get())
        self.app.last_copy=0;self.app.update_step();self.assertIn('G103',self.app.instructions.get())
        self.assertIn('W300,1400',self.app.instructions.get())
    def test_no_session_or_invalid_port_never_starts_hardware(self):
        with patch.object(self.app,'error') as error:
            self.app.upload();error.assert_called_once();self.assertFalse(self.app.busy)
        self.app.session=DumpSession.create(self.path/'rom','PC-G801',4)
        self.app.port.set('')
        with patch.object(self.app,'error') as error:
            self.app.receive();error.assert_called_once();self.assertFalse(self.app.busy)

    def test_resume_four_banks_creates_a_five_bank_copy_without_serial(self):
        original=DumpSession.create(self.path/'rom','PC-G801',4)
        before=(original.path/'session.json').read_bytes()
        with patch.object(self.app,'error') as error:
            self.app.open_session(original.path/'session.json')
            error.assert_not_called()
        self.assertNotEqual(self.app.session.path,original.path)
        self.assertEqual(self.app.session.bank_count,5)
        self.assertEqual((original.path/'session.json').read_bytes(),before)
        self.assertFalse(self.app.agent_loaded)
        self.assertIn('USER1400',self.app.instructions.get())
