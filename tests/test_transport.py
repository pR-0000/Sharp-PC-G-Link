import threading
import time
import unittest
from unittest.mock import patch
from collections import deque

import serial

from sharp_link.protocol import prepare
from sharp_link.transport import Cancelled, Settings, SettingsError, TransferError, drain, monitor_cts, open_port, receive, send


class FakePort:
    def __init__(self, incoming=(), cts=True, blocked=False):
        self.incoming = deque(incoming)
        self.cts = cts
        self.blocked = blocked
        self.written = bytearray()
        self.closed = False
        self.discarded = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    @property
    def out_waiting(self):
        return int(self.blocked)

    @property
    def in_waiting(self):
        return len(self.incoming[0]) if self.incoming else 0

    def read(self, _size):
        if self.incoming:
            return self.incoming.popleft()
        time.sleep(0.002)
        return b""

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def reset_output_buffer(self):
        self.discarded += 1


class TransportTests(unittest.TestCase):
    def test_selected_framing_reaches_the_real_pyserial_backend(self):
        with open_port(Settings("loop://")) as port:
            self.assertEqual((port.baudrate, port.bytesize, port.parity, port.stopbits), (1200, 7, "N", 1))
        for bits, parity, stops in ((7, "E", 1), (8, "E", 2), (8, "O", 2)):
            with self.subTest(frame=(bits, parity, stops)):
                settings = Settings("loop://", baud=9600, data_bits=bits, parity=parity, stop_bits=stops)
                with open_port(settings) as port:
                    self.assertEqual((port.bytesize, port.parity, port.stopbits), (bits, parity, stops))
                    self.assertTrue(port.rtscts)
                    wire = b"10 END\r\n\x1a"
                    port.write(wire)
                    self.assertEqual(port.read(len(wire)), wire)

    def test_invalid_framing_is_rejected_before_opening_a_port(self):
        for changes in ({"data_bits": 9}, {"parity": "X"}, {"stop_bits": 3}):
            with self.subTest(changes=changes), self.assertRaises(SettingsError):
                Settings("test", **changes)

    def test_drain_accounts_for_parity_and_both_stop_bits(self):
        settings = Settings("test", baud=300, data_bits=8, parity="E", stop_bits=2)
        with patch("sharp_link.transport.pause") as pause:
            drain(FakePort(), settings, threading.Event())
        pause.assert_called_once()
        self.assertAlmostEqual(pause.call_args.args[1], 12 / 300)

    def test_hardware_flow_control_cannot_be_disabled(self):
        self.assertTrue(Settings("test").rtscts)
        with self.assertRaises(TypeError):
            Settings("test", rtscts=False)

    def setUp(self):
        self.events = []
        self.notify = lambda kind, value: self.events.append((kind, value))
        self.cancel = threading.Event()
        self.settings = Settings("test", line_delay=0, stall_timeout=0.05,
                                 receive_timeout=0.04, idle_timeout=0.04)
        self.program = prepare("10 END")

    def test_sender_preserves_exact_wire_bytes(self):
        port = FakePort()
        count = send(self.program, self.settings, self.cancel, self.notify, lambda _: port)
        self.assertEqual(bytes(port.written), b"10 END\r\n\x1a")
        self.assertEqual(count, 9)
        self.assertTrue(port.closed)

    def test_cts_monitor_reports_initial_state_and_changes_without_uart_io(self):
        port = FakePort(incoming=(b"keep",), cts=False)
        timer = threading.Timer(0.02, lambda: setattr(port, "cts", True))
        timer.start()
        try:
            monitor_cts(self.settings, self.cancel, self.notify, lambda _: port, duration=0.08)
        finally:
            timer.join()
        self.assertEqual([value.key for kind, value in self.events if kind == "status"],
                         ["cts_inactive", "cts_active"])
        self.assertFalse(port.written)
        self.assertEqual(list(port.incoming), [b"keep"])
        self.assertTrue(port.closed)

    def test_cts_monitor_cancellation_closes_the_port_without_writing(self):
        port = FakePort()
        timer = threading.Timer(0.02, self.cancel.set)
        timer.start()
        try:
            with self.assertRaises(Cancelled):
                monitor_cts(self.settings, self.cancel, self.notify, lambda _: port)
        finally:
            timer.join()
        self.assertFalse(port.written)
        self.assertTrue(port.closed)

    def test_low_cts_never_sends_and_times_out(self):
        port = FakePort(cts=False)
        with self.assertRaisesRegex(TransferError, "CTS"):
            send(self.program, self.settings, self.cancel, self.notify, lambda _: port)
        self.assertFalse(port.written)
        self.assertTrue(port.closed)

    def test_cts_can_resume_without_losing_bytes(self):
        port = FakePort(cts=False)
        timer = threading.Timer(0.02, lambda: setattr(port, "cts", True))
        timer.start()
        try:
            send(self.program, self.settings, self.cancel, self.notify, lambda _: port)
        finally:
            timer.join()
        self.assertEqual(port.written, self.program.wire)

    def test_cancel_while_cts_blocked_closes_port(self):
        port = FakePort(cts=False)
        timer = threading.Timer(0.02, self.cancel.set)
        timer.start()
        try:
            with self.assertRaises(Cancelled):
                send(self.program, self.settings, self.cancel, self.notify, lambda _: port)
        finally:
            timer.join()
        self.assertTrue(port.closed)
        self.assertFalse(port.written)

    def test_blocked_output_does_not_hang_flush(self):
        port = FakePort(blocked=True)
        with self.assertRaisesRegex(TransferError, "bloquée"):
            send(self.program, self.settings, self.cancel, self.notify, lambda _: port)
        self.assertGreaterEqual(port.discarded, 2)

    def test_cancel_already_set_does_not_open_hardware(self):
        self.cancel.set()
        def forbidden(_):
            self.fail("Port should not be opened")
        with self.assertRaises(Cancelled):
            send(self.program, self.settings, self.cancel, self.notify, forbidden)
        with self.assertRaises(Cancelled):
            monitor_cts(self.settings, self.cancel, self.notify, forbidden)

    def test_receive_eof_across_chunks_preserves_bytes(self):
        port = FakePort((b"10 ", b"END\r", b"\n", b"\x1aignored"))
        result = receive(self.settings, self.cancel, self.notify, lambda _: port)
        self.assertEqual(result, b"10 END\r\n")
        self.assertTrue(port.closed)

    def test_idle_without_eof_is_error_and_partial_data_is_available(self):
        port = FakePort((b"10 END\r\n",))
        with self.assertRaisesRegex(TransferError, "sans marqueur EOF"):
            receive(self.settings, self.cancel, self.notify, lambda _: port)
        self.assertIn(("received", b"10 END\r\n"), self.events)

    def test_no_data_does_not_wait_forever(self):
        port = FakePort()
        with self.assertRaisesRegex(TransferError, "Aucune donnée"):
            receive(self.settings, self.cancel, self.notify, lambda _: port)

    def test_disconnection_is_not_reported_as_success(self):
        port = FakePort()
        port.write = lambda _data: (_ for _ in ()).throw(serial.SerialException("device removed"))
        with self.assertRaises(serial.SerialException):
            send(self.program, self.settings, self.cancel, self.notify, lambda _: port)
        self.assertTrue(port.closed)

    def test_real_pyserial_loopback_send_and_receive(self):
        # Exercise pyserial's real byte queues. Reader acts as the remote device for send().
        settings = Settings("loop://", line_delay=0, stall_timeout=2)
        port = open_port(settings)
        captured = bytearray()
        finished = threading.Event()
        def reader():
            while not finished.is_set():
                try:
                    value = port.read(1)
                except serial.SerialException:
                    break
                captured.extend(value)
                if value == b"\x1a":
                    break
        thread = threading.Thread(target=reader)
        thread.start()
        try:
            send(self.program, settings, self.cancel, self.notify, lambda _: port)
        finally:
            finished.set()
            thread.join(timeout=2)
        self.assertEqual(captured, self.program.wire)
        second = open_port(settings)
        second.write(b"10 END\r\n\x1a")
        self.assertEqual(receive(settings, self.cancel, self.notify, lambda _: second), b"10 END\r\n")


if __name__ == "__main__":
    unittest.main()
