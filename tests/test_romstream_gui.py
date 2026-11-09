from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from sharp_link.config import load_settings
from sharp_link.romstream import StreamSession
from sharp_link.romstream_gui import AutoRomDumpApp


class AutoRomGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.ports=patch('sharp_link.romstream_gui.list_ports.comports',return_value=[]);self.ports.start()
        self.app=AutoRomDumpApp(self.root/'prefs.ini');self.app.withdraw();self.app.update()
    def tearDown(self):
        self.app.destroy();self.ports.stop();self.tmp.cleanup()
    def test_language_persists_and_one_run_instructions_are_translated(self):
        self.app.lang.set('English');self.app.change_language()
        self.assertEqual(load_settings(self.root/'prefs.ini')['language'],'en')
        self.assertIn('Send dumper',self.app.instructions.get())
        self.assertIn('One G100',self.app.note.get())
        self.app.session=StreamSession.create(self.root/'rom','PC-G801',1)
        self.app.agent_loaded=True;self.app.update_step()
        self.assertIn('No W/G103',self.app.instructions.get())
        self.app.lang.set('Français');self.app.change_language()
        self.assertIn('Aucun W/G103',self.app.instructions.get())
    def test_model_profiles_allow_extended_banks_and_g820_monitor(self):
        self.app.model.set('PC-G850VS');self.app.change_model()
        self.assertEqual(self.app.banks.get(),'32')
        self.assertEqual(len(self.app.bank_box['values']),32)
        self.app.session=StreamSession.create(self.root/'rom','PC-G820',1)
        self.app.update_step();self.assertIn('CALL #5,&HC000',self.app.instructions.get())
        self.assertIn('USER0AFF',self.app.instructions.get())
    def test_resume_rebuilds_agent_without_opening_serial(self):
        s=StreamSession.create(self.root/'rom','PC-G805',1)
        with patch.object(self.app,'error') as error:
            self.app.open_session(s.path/'session.json');error.assert_not_called()
        self.assertFalse(self.app.agent_loaded)
        self.assertEqual(self.app.banks.get(),'1')
        self.assertTrue((s.path/'agent-auto.hex').exists())
    def test_receiver_events_show_verified_progress_and_only_end_completes(self):
        self.app.session=StreamSession.create(self.root/'rom','PC-G801',1)
        self.app.events.put(('armed','path'))
        self.app.events.put(('block',{'index':1,'bank':255,'source':0x8000,'reads':1,'verified_reads':3,'total_reads':130}))
        self.app.after_cancel(self.app.poll_id);self.app.poll();self.app.update()
        self.assertAlmostEqual(self.app.progress['value'],300/130)
        self.assertIn('8000h',self.app.instructions.get())
        self.app.lang.set('English');self.app.change_language()
        self.assertIn('8000h',self.app.instructions.get())
        self.assertIn('RAM/fixed',self.app.instructions.get())
        self.app.lang.set('Français');self.app.change_language()
        self.app.events.put(('complete','somewhere'));self.app.after_cancel(self.app.poll_id);self.app.poll()
        self.assertIn('marqueur de fin',self.app.instructions.get())
    def test_invalid_port_and_absent_session_never_open_hardware(self):
        with patch.object(self.app,'error') as error:
            self.app.receive();error.assert_called_once()
        self.app.session=StreamSession.create(self.root/'rom','PC-G801',1)
        self.app.port.set('')
        with patch.object(self.app,'error') as error:
            self.app.upload();error.assert_called_once();self.assertFalse(self.app.busy)

    def test_upload_creates_backup_automatically_without_new_or_resume_steps(self):
        self.app.port.set('TEST');self.app.destination.set(str(self.root/'output'))
        with patch('sharp_link.romstream_gui.send',return_value=1) as send:
            self.app.upload()
            deadline=time.monotonic()+2
            while self.app.busy and time.monotonic()<deadline:
                self.app.update();time.sleep(.01)
            send.assert_called_once()
        self.assertTrue(self.app.agent_loaded)
        self.assertEqual(len(self.app.session.plan),193)
        self.assertEqual(self.app.session.path.parent,self.root/'output')
        self.assertEqual(str(self.app.rx_button['state']),'normal')
        self.assertTrue((self.app.session.path/'agent-auto.hex').exists())
        self.assertNotIn('session',self.app.instructions.get().lower())

    def test_cancelled_destination_never_sends_and_reception_requires_uploaded_program(self):
        self.app.port.set('TEST')
        with patch('sharp_link.romstream_gui.filedialog.askdirectory',return_value=''), patch('sharp_link.romstream_gui.send') as send:
            self.app.upload();send.assert_not_called()
        self.assertIsNone(self.app.session)
        with patch.object(self.app,'error') as error,patch('sharp_link.romstream_gui.receive_stream') as receive:
            self.app.receive();error.assert_called_once();receive.assert_not_called()


if __name__=='__main__':unittest.main()
