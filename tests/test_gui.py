"""Real Tk widgets, INI reload and worker events, without opening any physical port."""
import tempfile
import threading
import time
from pathlib import Path
import unittest
from unittest.mock import patch

from sharp_link.config import load_settings
from sharp_link.gui import ASM_EXAMPLES, BASIC_EXAMPLES, LinkApp, resources
from sharp_link.i18n import msg
from sharp_link.protocol import parse_hex
from sharp_link.transport import TransferError


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ini = Path(self.temp.name) / "sharp_pc_g_link.ini"
        self.ports = patch("sharp_link.gui.list_ports.comports", return_value=[])
        self.ports.start()
        self.app = LinkApp(settings_file=self.ini)
        self.app.withdraw()
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.ports.stop()
        self.temp.cleanup()

    def test_no_device_does_not_open_a_port(self):
        self.assertEqual((self.app.baud.get(), self.app.data_bits.get(), self.app.parity.get(),
                          self.app.stop_bits.get()), ("1200", "7", "N", "1"))
        self.assertIn("1200 bauds / 7N1", self.app.serial_hint.get())
        self.app.load_basic(resources() / "examples/basic/01_bonjour.bas")
        self.app.start_send_basic()
        self.assertIn("port", self.app.status.get())
        self.assertIsNone(self.app.worker)

    def test_rom_tab_shares_window_language_and_settings(self):
        panel = self.app.rom_panel
        self.assertEqual(len(self.app.workspaces.tabs()), 2)
        self.assertIs(panel.winfo_toplevel(), self.app)
        self.app.open_rom_dump()
        self.assertEqual(self.app.workspaces.select(), str(self.app.rom_page))
        self.app.set_language('en')
        self.assertEqual(self.app.workspaces.tab(self.app.rom_page, 'text'), 'ROM backup')
        self.assertIn('TEXT → Sio → Format', panel.hint.get())
        self.app.port_lookup = {'FTDI test': 'COM_TEST'}; self.app.port.set('FTDI test')
        self.app.apply_recommended_settings()
        self.assertEqual((panel.settings().port, panel.settings().baud, panel.settings().frame), ('COM_TEST', 4800, '8N1'))
        self.app.model.set('PC-G850VS')
        self.assertEqual(panel.banks.get(), '32')

    def test_rom_refuses_wrong_framing_without_touching_preferences_or_hardware(self):
        from sharp_link.romstream import StreamSession
        panel = self.app.rom_panel
        panel.session = StreamSession.create(Path(self.temp.name)/'rom', 'PC-G801', 1)
        self.app.port_lookup = {'TEST': 'TEST'}; self.app.port.set('TEST')
        with patch.object(panel, 'error') as error, patch('sharp_link.romstream_gui.send') as send:
            panel.upload()
            self.assertIn('TEXT → Sio → Format', error.call_args.args[0].render('fr'))
            send.assert_not_called()
        self.assertFalse(panel.busy)
        self.assertEqual((self.app.baud.get(), self.app.data_bits.get()), ('1200', '7'))

    def test_serial_operations_are_exclusive_across_tabs_and_cancel_routes_to_owner(self):
        from sharp_link.romstream import StreamSession
        panel = self.app.rom_panel
        panel.session = StreamSession.create(Path(self.temp.name)/'rom', 'PC-G801', 1)
        self.app.port_lookup = {'TEST': 'TEST'}; self.app.port.set('TEST')
        self.app.apply_recommended_settings()
        released = threading.Event()
        panel.start(lambda settings: released.wait(2))
        try:
            self.assertTrue(self.app.is_busy())
            self.assertEqual(str(self.app.port_box['state']), 'disabled')
            self.assertEqual(str(self.app.cts_button['state']), 'disabled')
            self.assertEqual(str(panel.upload_button['state']), 'disabled')
            with patch('sharp_link.gui.monitor_cts') as monitor:
                self.app.start_cts_check(); monitor.assert_not_called()
            self.app.cancel_transfer()
            self.assertTrue(panel.cancel.is_set())
            self.assertFalse(self.app.cancel_event.is_set())
        finally:
            released.set()
        deadline = time.monotonic() + 2
        while panel.busy and time.monotonic() < deadline:
            self.app.update(); time.sleep(.01)
        self.assertFalse(self.app.is_busy())
        self.assertEqual(str(self.app.port_box['state']), 'readonly')
        self.app.worker = object(); self.app.update_controls()
        with patch.object(panel, 'error') as error:
            panel.receive(); error.assert_called_once()
        self.assertFalse(panel.busy)
        self.app.worker = None; self.app.update_controls()

    def test_all_examples_and_separate_send_commands(self):
        for relative in BASIC_EXAMPLES.values():
            self.assertTrue(self.app.load_basic(resources() / "examples" / relative))
            self.assertEqual(self.app.basic_program.kind, "basic")
        for relative in ASM_EXAMPLES.values():
            self.app.load_asm_example(resources() / "examples" / relative)
            self.assertIsNotNone(self.app.asm_program)
            self.assertIn("USER01FF", self.app.asm_hint.get())
        self.assertEqual(self.app.asm_program.kind, "hex")
        self.assertEqual(str(self.app.load_address_entry.cget("state")), "disabled")

    def test_bin_relocation_updates_wire_and_preview(self):
        self.app.load_asm_example(resources() / "examples/assembler/pcg801_signature.bin")
        self.app.load_address.set("0200")
        self.app.entry_address.set("0200")
        program = self.app.asm_program
        self.assertEqual(program.kind, "binary")
        self.assertEqual(program.start, 0x200)
        self.assertIn("G0200", self.app.asm_hint.get())
        self.assertTrue(program.wire.startswith(b":10020000"))
        self.assertIn("0200", self.app.asm_preview.get("1.0", "end"))
        # Relocation changes the load address only, not absolute addresses in Z80 code.
        self.assertEqual(parse_hex([line.decode().strip() for line in program.lines])[1], 0x200)

    def test_invalid_edit_blocks_basic_only(self):
        self.app.load_asm_example(resources() / "examples/assembler/pcg801_signature.bin")
        self.app.set_text(self.app.editor, '10 PRINT "é"')
        self.app.validate_basic()
        self.assertIsNone(self.app.basic_program)
        self.assertEqual(str(self.app.basic_send_button.cget("state")), "disabled")
        self.assertEqual(str(self.app.asm_send_button.cget("state")), "normal")

    def test_language_changes_widgets_errors_and_persists_in_ini(self):
        self.app.load_asm_example(resources() / "examples/assembler/pcg801_signature.bin")
        before = self.app.asm_program.wire
        self.app.set_language("en")
        self.assertEqual(self.app.basic_send_button.cget("text"), "Send BASIC")
        self.assertEqual(self.app.asm_send_button.cget("text"), "Send ASM")
        self.assertEqual(self.app.cts_button.cget("text"), "Check CTS")
        self.assertEqual(self.app.tabs.tab(self.app.receive_tab, "text"), "Receive")
        self.assertIn("Z80 ASSEMBLY", self.app.help_text.get("1.0", "end"))
        self.assertEqual(load_settings(self.ini)["language"], "en")
        self.app.events.put(("status", msg("cts_wait")))
        self.app.poll_events()
        self.assertIn("Waiting for CTS", self.app.status.get())
        self.app.events.put(("error", TransferError("cts_timeout")))
        self.app.poll_events()
        self.assertIn("CTS remains inactive", self.app.status.get())
        self.app.set_language("fr")
        self.assertIn("CTS reste inactif", self.app.status.get())
        self.assertEqual(self.app.asm_program.wire, before)

    def test_preferences_are_restored_in_a_new_application(self):
        self.app.set_language("en")
        self.app.baud.set("1200")
        self.app.data_bits.set("7")
        self.app.parity.set("E")
        self.app.stop_bits.set("2")
        self.app.load_address.set("0280")
        self.app.entry_address.set("0284")
        self.app.line_delay.set("100")
        self.app.save_config()
        self.app.destroy()
        self.app = LinkApp(settings_file=self.ini)
        self.app.withdraw()
        self.app.update()
        self.assertEqual(self.app.language, "en")
        self.assertEqual(self.app.baud.get(), "1200")
        self.assertEqual((self.app.data_bits.get(), self.app.parity.get(), self.app.stop_bits.get()), ("7", "E", "2"))
        self.assertIn("1200 baud / 7E2", self.app.serial_hint.get())
        self.assertEqual(self.app.load_address.get(), "0280")
        self.assertEqual(self.app.entry_address.get(), "0284")
        self.assertEqual(self.app.line_delay.get(), "100")
        self.assertFalse(hasattr(self.app, "flow"))

    def test_recommended_profile_preserves_port_model_and_delays(self):
        self.app.port_lookup = {"TEST": "TEST"}
        self.app.port.set("TEST")
        self.app.model.set("PC-G850VS")
        self.app.baud.set("300")
        self.app.data_bits.set("7")
        self.app.parity.set("O")
        self.app.stop_bits.set("2")
        self.app.line_delay.set("100")
        self.app.apply_recommended_settings()
        settings = self.app.get_settings()
        self.assertEqual((settings.port, settings.baud, settings.frame, settings.line_delay), ("TEST", 4800, "8N1", 0.1))
        self.assertEqual(self.app.model.get(), "PC-G850VS")
        saved = load_settings(self.ini)
        self.assertEqual((saved["baud"], saved["data_bits"], saved["parity"], saved["stop_bits"]), ("4800", "8", "N", "1"))

    def test_background_send_disables_both_paths_then_updates_log(self):
        self.app.load_basic(resources() / "examples/basic/01_bonjour.bas")
        self.app.port_lookup = {"TEST": "TEST"}
        self.app.port.set("TEST")
        self.app.baud.set("300")
        self.app.data_bits.set("8")
        self.app.parity.set("E")
        self.app.stop_bits.set("2")
        def sender(program, settings, _cancel, notify):
            self.assertEqual((settings.baud, settings.frame), (300, "8E2"))
            notify("progress", (program.size, program.size))
            return program.size
        with patch("sharp_link.gui.send", side_effect=sender):
            self.app.start_send_basic()
            self.assertEqual(str(self.app.basic_send_button.cget("state")), "disabled")
            self.assertEqual(str(self.app.asm_send_button.cget("state")), "disabled")
            deadline = time.monotonic() + 2
            while self.app.worker is not None and time.monotonic() < deadline:
                self.app.update()
                time.sleep(0.01)
        self.assertIsNone(self.app.worker)
        self.assertIn("octets émis", self.app.status.get())
        self.assertIn("TX 01_bonjour.bas", self.app.log.get("1.0", "end"))
        self.assertIn("300 8E2", self.app.log.get("1.0", "end"))
        self.assertIn("Basic←text", self.app.status.get())
        self.assertIn("nom du fichier PC n'est pas transmis", self.app.log.get("1.0", "end"))
        self.app.set_language("en")
        self.assertIn("Basic←text", self.app.status.get())
        self.assertIn("TEXT editor", self.app.basic_hint_label.cget("text"))

    def test_assembly_completion_does_not_request_text_to_basic_conversion(self):
        self.app.events.put(("done", ("send", 42, "hex")))
        self.app.poll_events()
        self.assertIn("42 octets émis", self.app.status.get())
        self.assertNotIn("Basic←text", self.app.status.get())
        self.assertNotIn("Convertir avec", self.app.log.get("1.0", "end"))

    def test_cts_check_worker_preserves_received_data_and_never_calls_send(self):
        self.app.port_lookup = {"TEST": "TEST"}
        self.app.port.set("TEST")
        self.app.received = b"previous reception"
        self.app.received_saved = self.app.received_complete = True
        def monitor(settings, _cancel, notify):
            self.assertEqual(settings.port, "TEST")
            notify("status", msg("cts_active"))
        with patch("sharp_link.gui.monitor_cts", side_effect=monitor) as observe, \
                patch("sharp_link.gui.send") as send, patch("sharp_link.gui.receive") as receive:
            self.app.start_cts_check()
            self.assertEqual(str(self.app.cts_button.cget("state")), "disabled")
            deadline = time.monotonic() + 2
            while self.app.worker is not None and time.monotonic() < deadline:
                self.app.update()
                time.sleep(0.01)
            observe.assert_called_once()
            send.assert_not_called()
            receive.assert_not_called()
        self.assertIsNone(self.app.worker)
        self.assertEqual(self.app.received, b"previous reception")
        self.assertTrue(self.app.received_saved and self.app.received_complete)
        self.assertIn("Contrôle CTS terminé", self.app.status.get())
        self.assertIn("CTS ACTIF", self.app.log.get("1.0", "end"))

    def test_actions_and_log_visible_at_minimum_size(self):
        self.app.geometry("980x730")
        self.app.deiconify()
        for language in ("fr", "en"):
            self.app.set_language(language)
            self.app.update()
            for control in (self.app.basic_send_button, self.app.asm_send_button, self.app.cancel_button,
                            self.app.data_bits_box, self.app.parity_box, self.app.stop_bits_box,
                            self.app.recommended_button, self.app.cts_button, self.app.basic_hint_label):
                self.assertGreater(control.winfo_height(), 20)
                self.assertLessEqual(control.winfo_rootx() + control.winfo_width(), self.app.winfo_rootx() + self.app.winfo_width())
                self.assertLess(control.winfo_rooty() + control.winfo_height(), self.app.winfo_rooty() + self.app.winfo_height())
            self.assertGreater(self.app.log.winfo_height(), 35)


if __name__ == "__main__":
    unittest.main()
