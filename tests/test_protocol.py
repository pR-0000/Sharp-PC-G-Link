import unittest
from pathlib import Path

from sharp_link.protocol import FormatError, instructions, intel_record, parse_address, prepare, prepare_binary, read_source

ROOT = Path(__file__).resolve().parents[1]


class ProtocolTests(unittest.TestCase):
    def test_binary_roundtrip_preserves_every_byte_including_control_values(self):
        data = bytes(range(256))
        program = prepare_binary(data, 0x100)
        decoded = b"".join(bytes.fromhex(line.decode()[9:-4]) for line in program.lines[:-1])
        self.assertEqual(decoded, data)
        self.assertEqual((program.start, program.end), (0x100, 0x1FF))
        self.assertTrue(program.wire.endswith(b":00000001FF\r\n\x1a"))
        self.assertEqual(program.wire.count(b"\x1a"), 1)

    def test_binary_bounds_empty_and_model_limits(self):
        for data, address in ((b"", 0x100), (b"\xC9", 0xFF), (b"12", 0x7FFF), (b"12", 0x17E2)):
            with self.subTest(address=address), self.assertRaises(FormatError):
                prepare_binary(data, address)

    def test_hex_address_notation(self):
        for value in ("0100", "0x100", "&H0100", " 100 "):
            self.assertEqual(parse_address(value), 0x100)
        for value in ("", "10000", "-100", "0x", "xyz"):
            with self.assertRaises(FormatError):
                parse_address(value)

    def test_errors_can_be_rendered_in_both_languages(self):
        with self.assertRaises(FormatError) as caught:
            prepare('10 PRINT "é"')
        self.assertIn("Ligne 1", caught.exception.render("fr"))
        self.assertIn("Line 1", caught.exception.render("en"))

    def test_basic_wire_matches_documented_sio(self):
        expected = b'10 PRINT "OK"\r\n20 END\r\n\x1a'
        for ending in ("\n", "\r", "\r\n"):
            with self.subTest(ending=repr(ending)):
                self.assertEqual(prepare(ending.join(['10 PRINT "OK"', '20 END']) + ending).wire, expected)

    def test_eof_from_sharp_export_is_not_duplicated(self):
        self.assertEqual(prepare("10 END\r\n\x1a\r\n").wire, b"10 END\r\n\x1a")

    def test_invalid_basic_does_not_get_silently_rewritten(self):
        for source in ("PRINT 42", "10 END\n10 END", "20 END\n10 END", "0 END", "65280 END"):
            with self.subTest(source=source), self.assertRaises(FormatError):
                prepare(source)

    def test_control_characters_and_accents_are_rejected(self):
        for source in ('10 PRINT "été"', '10\tEND', "10 END\x00", "10 END\x1a\n20 END"):
            with self.subTest(source=source), self.assertRaises(FormatError):
                prepare(source)

    def test_monitor_reference_vector(self):
        # Independently calculated record: length 1 + address 0100 + C9 = CB; checksum 35.
        program = prepare(":01010000C935\n:00000001FF", "ret.ihx")
        self.assertEqual(program.kind, "hex")
        self.assertEqual((program.start, program.end, program.data_bytes), (0x100, 0x100, 1))
        self.assertEqual(program.wire, b":01010000C935\r\n:00000001FF\r\n\x1a")

    def test_bad_checksum_missing_eof_trailing_data_and_overlaps(self):
        for content in (
            ":01010000C934\n:00000001FF", ":01010000C935",
            ":01010000C935\n:00000001FF\n:00000001FF",
            ":01010000C935\n:01010000C935\n:00000001FF",
            ":020000040000FA\n:01010000C935\n:00000001FF",
        ):
            with self.subTest(content=content), self.assertRaises(FormatError):
                prepare(content, "test.hex")

    def test_reject_system_rom_and_g801_too_large(self):
        for address in (0, 0x17E3, 0x8000):
            with self.subTest(address=address), self.assertRaises(FormatError):
                prepare(intel_record(address, b"\xC9") + "\n:00000001FF", "test.hex")

    def test_hex_auto_detects_even_with_txt_suffix(self):
        self.assertEqual(prepare(":01010000C935\n:00000001FF", "test.txt").kind, "hex")

    def test_assembly_source_is_text_not_machine_code(self):
        program = prepare("ORG 0100H\nRET", "source.asm")
        self.assertEqual(program.kind, "text")
        self.assertIn("assemblé", instructions(program, "PC-G801"))

    def test_every_shipped_example_is_valid_for_g801(self):
        for path in (ROOT / "examples").rglob("*"):
            if path.suffix in {".bas", ".hex"}:
                with self.subTest(path=path.name):
                    program = prepare(read_source(path), path.name)
                    self.assertGreater(program.size, 0)
                    self.assertTrue(program.wire.endswith(b"\r\n\x1a"))

    def test_g820_uses_its_monitor_entry(self):
        program = prepare(":01010000C935\n:00000001FF", "ret.hex", model="PC-G820")
        self.assertIn("CALL #5,&HC000", instructions(program, "PC-G820"))


if __name__ == "__main__":
    unittest.main()
