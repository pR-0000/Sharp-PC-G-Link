"""Cancelable serial operations. No polarity inversion: handled in the FTDI EEPROM."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Callable

import serial

from .protocol import EOF, MAX_FILE_BYTES, PreparedFile
from .i18n import LocalizedError, msg, tr

Notify = Callable[[str, object], None]


class TransferError(LocalizedError, RuntimeError):
    pass


class Cancelled(TransferError):
    pass


class SettingsError(LocalizedError, ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    port: str
    baud: int = 1200
    rtscts: bool = field(default=True, init=False)
    line_delay: float = 0.05
    char_delay: float = 0
    stall_timeout: float = 20
    receive_timeout: float = 90
    idle_timeout: float = 10
    data_bits: int = 7
    parity: str = "N"
    stop_bits: int = 1

    def __post_init__(self):
        if not self.port.strip():
            raise SettingsError("no_port")
        if self.baud not in (300, 600, 1200, 2400, 4800, 9600):
            raise SettingsError("bad_baud")
        if self.data_bits not in (7, 8) or self.parity not in ("N", "E", "O") or self.stop_bits not in (1, 2):
            raise SettingsError("bad_frame")
        if not 0 <= self.line_delay <= 2 or not 0 <= self.char_delay <= 0.1:
            raise SettingsError("bad_delays")
        if self.stall_timeout <= 0 or self.receive_timeout <= 0 or self.idle_timeout <= 0:
            raise SettingsError("bad_timeouts")

    @property
    def frame(self) -> str:
        return f"{self.data_bits}{self.parity}{self.stop_bits}"

    @property
    def character_bits(self) -> int:
        return 1 + self.data_bits + int(self.parity != "N") + self.stop_bits


def open_port(settings: Settings):
    # Assign states before opening, so RTS/DTR are requested asserted from the start.
    port = serial.serial_for_url(
        settings.port, do_not_open=True, baudrate=settings.baud,
        bytesize=settings.data_bits, parity=settings.parity, stopbits=settings.stop_bits,
        timeout=0.1, write_timeout=0.25, rtscts=True, xonxoff=False, dsrdtr=False,
    )
    port.rts = True
    port.dtr = True
    try:
        port.open()
    except Exception:
        port.close()
        raise
    return port


def check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled("cancelled")


def pause(cancel: threading.Event, seconds: float) -> None:
    if cancel.wait(seconds):
        check_cancel(cancel)


def wait_ready(port, settings: Settings, cancel: threading.Event, notify: Notify) -> None:
    start = time.monotonic()
    announced = False
    while not port.cts:
        check_cancel(cancel)
        if not announced:
            notify("status", msg("cts_wait"))
            announced = True
        if time.monotonic() - start > settings.stall_timeout:
            raise TransferError("cts_timeout")
        pause(cancel, 0.02)
    if announced:
        notify("status", msg("sending"))


def drain(port, settings: Settings, cancel: threading.Event) -> None:
    # serial.flush() may block indefinitely under RTS/CTS, including on cancellation.
    start = time.monotonic()
    previous = port.out_waiting
    while port.out_waiting:
        check_cancel(cancel)
        current = port.out_waiting
        if current < previous:
            start = time.monotonic()
        previous = current
        if time.monotonic() - start > settings.stall_timeout:
            raise TransferError("drain_timeout")
        pause(cancel, 0.01)
    # Account for the final UART byte still in the shift register.
    pause(cancel, settings.character_bits / settings.baud)


def monitor_cts(settings: Settings, cancel: threading.Event, notify: Notify,
                factory=open_port, duration: float = 60) -> None:
    """Observe the driver's CTS state without writing or consuming UART bytes.

    Opening the port still asserts RTS/DTR, just as a normal transfer does.
    CTS alone cannot identify whether the Sharp is running LOAD.
    """
    check_cancel(cancel)
    with factory(settings) as port:
        previous = None
        deadline = time.monotonic() + duration
        while True:
            check_cancel(cancel)
            current = bool(port.cts)
            if current != previous:
                notify("status", msg("cts_active" if current else "cts_inactive"))
                previous = current
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            pause(cancel, min(0.05, remaining))


def send(program: PreparedFile, settings: Settings, cancel: threading.Event,
         notify: Notify, factory=open_port) -> int:
    check_cancel(cancel)
    sent = 0
    last_progress = 0.0
    with factory(settings) as port:
        try:
            port.reset_output_buffer()
            notify("status", msg("cts_initial_active" if port.cts else "cts_initial_inactive"))
            notify("status", msg("sending"))
            for line in (*program.lines, EOF):
                for value in line:
                    check_cancel(cancel)
                    wait_ready(port, settings, cancel, notify)
                    if port.write(bytes((value,))) != 1:
                        raise TransferError("short_write")
                    sent += 1
                    now = time.monotonic()
                    if now - last_progress >= 0.05 or sent == program.size:
                        notify("progress", (sent, program.size))
                        last_progress = now
                    if settings.char_delay:
                        pause(cancel, settings.char_delay)
                drain(port, settings, cancel)
                if line != EOF:
                    pause(cancel, settings.line_delay)
        except BaseException:
            # Do not let queued bytes continue after cancellation/failure.
            try:
                port.reset_output_buffer()
            except (OSError, serial.SerialException):
                pass
            raise
    return sent


def receive(settings: Settings, cancel: threading.Event, notify: Notify, factory=open_port) -> bytes:
    """Receive a Sharp TEXT/monitor stream; only 1A marks a complete transfer."""
    data = bytearray()
    last_notification = 0.0
    check_cancel(cancel)
    with factory(settings) as port:
        # Do not reset the input buffer: data may arrive immediately after open.
        start = last_data = time.monotonic()
        notify("status", msg("rx_ready"))
        try:
            while True:
                check_cancel(cancel)
                chunk = port.read(min(max(port.in_waiting, 1), 4096))
                now = time.monotonic()
                if chunk:
                    last_data = now
                    complete = EOF in chunk
                    data.extend(chunk.split(EOF, 1)[0])
                    if len(data) > MAX_FILE_BYTES:
                        raise TransferError("rx_large")
                    if now - last_notification >= 0.05 or complete:
                        notify("received", bytes(data))
                        last_notification = now
                    if complete:
                        return bytes(data)
                elif not data and now - start > settings.receive_timeout:
                    raise TransferError("rx_timeout")
                elif data and now - last_data > settings.idle_timeout:
                    raise TransferError("rx_incomplete")
        finally:
            # Preserve the last bytes even if canceled/disconnected between preview updates.
            notify("received", bytes(data))


def friendly_error(error: Exception, language: str = "fr") -> str:
    if isinstance(error, LocalizedError):
        return error.render(language)
    if isinstance(error, serial.SerialTimeoutException):
        return tr(language, "serial_timeout")
    if isinstance(error, serial.SerialException) or isinstance(error, OSError):
        return tr(language, "serial_error", detail=str(error))
    return str(error)
