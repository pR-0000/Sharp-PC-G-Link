"""Native desktop transfer console for programmers; serial I/O runs in a worker."""
from __future__ import annotations

import math
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
import webbrowser

from serial.tools import list_ports

from . import __version__
from .config import config_path, legacy_path, load_settings, save_settings
from .i18n import LANGUAGES, LocalizedError, Message, msg, tr
from .protocol import (FormatError, MAX_FILE_BYTES, MODELS, SMALL_RAM_MODELS,
                       PreparedFile, parse_address, prepare, prepare_binary, read_source)
from .reference import REFERENCE
from .transport import Cancelled, Settings, friendly_error, monitor_cts, receive, send

APP_NAME = "Sharp PC-G Link"
BASIC_EXAMPLES = {
    "example_hello": "basic/01_bonjour.bas",
    "example_calculation": "basic/02_calcul.bas",
    "example_game": "basic/03_devine.bas",
}
ASM_EXAMPLES = {
    "example_bin": "assembler/pcg801_signature.bin",
    "example_hex": "assembler/pcg801_signature.hex",
}
G850_BASIC_EXAMPLES = {
    "g850_hello": "pc-g850/basic/{lang}/01_transfer.bas",
    "g850_lcd": "pc-g850/basic/{lang}/02_lcd.bas",
    "g850_keyboard": "pc-g850/basic/{lang}/03_keyboard.bas",
    "g850_calculation": "pc-g850/basic/{lang}/04_calculation.bas",
    "g850_animation": "pc-g850/basic/{lang}/05_animation.bas",
}
G850_ASM_EXAMPLES = {
    "g850_signature_bin": "pc-g850/assembler/g850_signature.bin",
    "g850_signature_hex": "pc-g850/assembler/g850_signature.hex",
    "g850_lcd_bin": "pc-g850/assembler/g850_lcd.bin",
    "g850_lcd_hex": "pc-g850/assembler/g850_lcd.hex",
}


def resources() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def selection_label(path: Path) -> str:
    try:
        return "examples/" + path.relative_to(resources() / "examples").as_posix()
    except ValueError:
        return str(path)


class LinkApp(tk.Tk):
    def __init__(self, settings_file: Path | None = None):
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("1120x840")
        self.minsize(980, 760)
        self.settings_file = settings_file or config_path()
        self.saved = load_settings(self.settings_file, legacy_path() if settings_file is None else None)
        self.language = self.saved["language"]
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.closing = False
        self.controls: list[tuple[tk.Widget, str]] = []
        self.translatable: list[tuple[tk.Widget, str]] = []
        self.pending_validation = self.pending_config = self.poll_after_id = None
        self.basic_path: Path | None = None
        self.asm_path: Path | None = None
        self.basic_program: PreparedFile | None = None
        self.asm_program: PreparedFile | None = None
        self.basic_original = ""
        self.basic_dirty = False
        self.asm_data = b""
        self.received = b""
        self.received_complete = self.received_saved = False
        self.last_error = None
        self.last_status: Message | str = msg("ready")
        self._last_ini_error = None
        self.started = 0.0
        self.port_lookup = {}

        self.language_display = tk.StringVar(value=LANGUAGES[self.language])
        self.model = tk.StringVar(value=self.saved["model"] if self.saved["model"] in MODELS else "PC-G801")
        self.expanded_ram = tk.BooleanVar(value=self.saved["expanded_ram"] == "yes")
        self.port = tk.StringVar()
        self.baud = tk.StringVar(value=self.saved["baud"])
        self.data_bits = tk.StringVar(value=self.saved["data_bits"])
        self.parity = tk.StringVar(value=self.saved["parity"])
        self.stop_bits = tk.StringVar(value=self.saved["stop_bits"])
        self.line_delay = tk.StringVar(value=self.saved["line_delay_ms"])
        self.char_delay = tk.StringVar(value=self.saved["char_delay_ms"])
        self.load_address = tk.StringVar(value=self.saved["load_address"])
        self.entry_address = tk.StringVar(value=self.saved["entry_address"])
        self.basic_file_label, self.asm_file_label = tk.StringVar(), tk.StringVar()
        self.basic_info, self.asm_info, self.asm_hint = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.serial_hint = tk.StringVar()
        self.status, self.rx_status = tk.StringVar(), tk.StringVar()

        style = ttk.Style(self)
        for theme in (("vista", "xpnative", "clam") if sys.platform == "win32" else ("aqua", "clam")):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        tkfont.nametofont("TkDefaultFont").configure(size=9)
        self._build()
        self.localize()
        self.refresh_ports(initial=True)
        self.append_log(msg("log_start", version=__version__, path=str(self.settings_file)))
        for variable in (self.model, self.expanded_ram, self.port, self.baud, self.data_bits, self.parity, self.stop_bits, self.line_delay,
                         self.char_delay, self.load_address, self.entry_address):
            variable.trace_add("write", self.settings_changed)
        self.poll_after_id = self.after(75, self.poll_events)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Control-o>", lambda _event: self.choose_basic())
        self.bind("<Control-s>", lambda _event: self.save_source())
        self.save_config()

    def t(self, key, **params):
        return tr(self.language, key, **params)

    def rendered(self, value):
        return value.render(self.language) if isinstance(value, Message) else str(value)

    def caption(self, widget, key):
        self.translatable.append((widget, key))
        widget.configure(text=self.t(key))
        return widget

    def managed(self, widget, normal="normal"):
        self.controls.append((widget, normal))
        return widget

    def button(self, parent, key, command, *, managed=True, **kwargs):
        button = self.caption(ttk.Button(parent, command=command, **kwargs), key)
        return self.managed(button) if managed else button

    def label(self, parent, key, **kwargs):
        return self.caption(ttk.Label(parent, **kwargs), key)

    def box(self, parent, key, **kwargs):
        return self.caption(ttk.LabelFrame(parent, padding=7, **kwargs), key)

    def combo(self, parent, variable, values, **kwargs):
        return self.managed(ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", **kwargs), "readonly")

    def _build(self):
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        toolbar = ttk.Frame(root)
        toolbar.pack(fill="x", pady=(0, 7))
        ttk.Label(toolbar, text=f"{APP_NAME} {__version__}", font=("Segoe UI", 12, "bold")).pack(side="left")
        self.button(toolbar, "manual", self.open_manual, managed=False).pack(side="right", padx=(8, 0))
        self.language_box = ttk.Combobox(toolbar, textvariable=self.language_display,
                                      values=tuple(LANGUAGES.values()), state="readonly", width=12)
        self.language_box.pack(side="right", padx=(5, 0))
        self.language_box.bind("<<ComboboxSelected>>", self.change_language)
        self.label(toolbar, "language").pack(side="right", padx=(12, 0))

        serial_box = self.box(root, "serial_settings")
        serial_box.pack(fill="x", pady=(0, 7))
        row = ttk.Frame(serial_box)
        row.pack(fill="x")
        self.label(row, "model").pack(side="left")
        self.combo(row, self.model, MODELS, width=11).pack(side="left", padx=(4, 12))
        self.label(row, "port").pack(side="left")
        self.port_box = self.combo(row, self.port, (), width=40)
        self.port_box.pack(side="left", fill="x", expand=True, padx=(4, 5))
        self.button(row, "refresh", self.refresh_ports).pack(side="left", padx=(0, 12))
        self.label(row, "baud").pack(side="left")
        self.combo(row, self.baud, (300, 600, 1200, 2400, 4800, 9600), width=7).pack(side="left", padx=(4, 10))
        # Fixed protocol names are intentionally identical in both languages.
        self.label(row, "flow_required").pack(side="left")
        row = ttk.Frame(serial_box)
        row.pack(fill="x", pady=(5, 0))
        self.label(row, "data_bits").pack(side="left")
        self.data_bits_box = self.combo(row, self.data_bits, (7, 8), width=3)
        self.data_bits_box.pack(side="left", padx=(4, 12))
        self.label(row, "parity").pack(side="left")
        self.parity_box = self.combo(row, self.parity, ("N", "E", "O"), width=3)
        self.parity_box.pack(side="left", padx=(4, 12))
        self.label(row, "stop_bits").pack(side="left")
        self.stop_bits_box = self.combo(row, self.stop_bits, (1, 2), width=3)
        self.stop_bits_box.pack(side="left", padx=(4, 16))
        ttk.Label(row, text="CR LF  |  EOF 1A  |  XON/XOFF: OFF").pack(side="left")
        self.recommended_button = self.button(row, "recommended_settings", self.apply_recommended_settings)
        self.recommended_button.pack(side="right", padx=(10, 0))
        row = ttk.Frame(serial_box)
        row.pack(fill="x", pady=(5, 0))
        self.label(row, "line_delay").pack(side="left")
        self.managed(ttk.Entry(row, textvariable=self.line_delay, width=7)).pack(side="left", padx=(4, 15))
        self.label(row, "char_delay").pack(side="left")
        self.managed(ttk.Entry(row, textvariable=self.char_delay, width=7)).pack(side="left", padx=(4, 0))
        self.cts_button = self.button(row, "check_cts", self.start_cts_check)
        self.cts_button.pack(side="right", padx=(10, 0))
        ttk.Label(serial_box, textvariable=self.serial_hint, wraplength=930, justify="left").pack(
            anchor="w", pady=(5, 0))

        self.workspaces = ttk.Notebook(root)
        self.workspaces.pack(fill="both", expand=True)
        self.transfer_page = ttk.Frame(self.workspaces, padding=(0, 7, 0, 0))
        self.rom_page = ttk.Frame(self.workspaces)
        self.workspaces.add(self.transfer_page)
        self.workspaces.add(self.rom_page)
        root = self.transfer_page

        basic_box = self.box(root, "basic_frame")
        basic_box.pack(fill="x", pady=(0, 7))
        row = ttk.Frame(basic_box)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.basic_file_label, state="readonly").pack(side="left", fill="x", expand=True)
        self.button(row, "browse", self.choose_basic).pack(side="left", padx=(6, 5))
        self.basic_send_button = self.button(row, "send_basic", self.start_send_basic)
        self.basic_send_button.pack(side="left", padx=(0, 5))
        self.basic_examples_button = self.managed(self.caption(ttk.Menubutton(row), "examples"))
        self.basic_examples_button.pack(side="left")
        self.basic_examples_menu = tk.Menu(self.basic_examples_button, tearoff=False)
        self.basic_examples_button.configure(menu=self.basic_examples_menu)
        self.basic_hint_label = self.label(basic_box, "basic_hint", wraplength=930, justify="left")
        self.basic_hint_label.pack(anchor="w", pady=(5, 0))

        asm_box = self.box(root, "asm_frame")
        asm_box.pack(fill="x", pady=(0, 7))
        row = ttk.Frame(asm_box)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.asm_file_label, state="readonly").pack(side="left", fill="x", expand=True)
        self.button(row, "browse", self.choose_asm).pack(side="left", padx=(6, 5))
        self.asm_send_button = self.button(row, "send_asm", self.start_send_asm)
        self.asm_send_button.pack(side="left", padx=(0, 5))
        self.asm_examples_button = self.managed(self.caption(ttk.Menubutton(row), "examples"))
        self.asm_examples_button.pack(side="left")
        self.asm_examples_menu = tk.Menu(self.asm_examples_button, tearoff=False)
        self.asm_examples_button.configure(menu=self.asm_examples_menu)
        row = ttk.Frame(asm_box)
        row.pack(fill="x", pady=(5, 0))
        self.label(row, "load_address").pack(side="left")
        self.load_address_entry = self.managed(ttk.Entry(row, textvariable=self.load_address, width=8))
        self.load_address_entry.pack(side="left", padx=(5, 15))
        self.expanded_ram_box = self.managed(self.caption(ttk.Checkbutton(row, variable=self.expanded_ram), "expanded_ram"))
        self.expanded_ram_box.pack(side="right", padx=(12, 0))
        self.label(row, "entry_address").pack(side="left")
        self.managed(ttk.Entry(row, textvariable=self.entry_address, width=8)).pack(side="left", padx=(5, 16))
        ttk.Label(row, textvariable=self.asm_info).pack(side="left", fill="x", expand=True)
        ttk.Label(asm_box, textvariable=self.asm_hint).pack(anchor="w", pady=(4, 0))

        self.panes = ttk.Panedwindow(root, orient="vertical")
        self.panes.pack(fill="both", expand=True)
        self.tabs = ttk.Notebook(self.panes)
        self.panes.add(self.tabs, weight=3)
        self.basic_tab, self.asm_tab, self.receive_tab, self.help_tab = [ttk.Frame(self.tabs, padding=6) for _ in range(4)]
        for frame in (self.basic_tab, self.asm_tab, self.receive_tab, self.help_tab):
            self.tabs.add(frame)
        row = ttk.Frame(self.basic_tab)
        row.pack(fill="x", pady=(0, 4))
        self.save_source_button = self.button(row, "save_source", self.save_source)
        self.save_source_button.pack(side="right")
        ttk.Label(row, textvariable=self.basic_info).pack(side="left")
        self.editor = self.text_box(self.basic_tab, height=8, readonly=False)
        self.editor.bind("<<Modified>>", self.source_modified)
        self.asm_preview = self.text_box(self.asm_tab, height=8)
        row = ttk.Frame(self.receive_tab)
        row.pack(fill="x", pady=(0, 5))
        self.receive_button = self.button(row, "receive", self.start_receive)
        self.receive_button.pack(side="left")
        self.save_rx_button = self.button(row, "save_receive", self.save_received)
        self.save_rx_button.pack(side="left", padx=(5, 15))
        ttk.Label(row, textvariable=self.rx_status).pack(side="left")
        self.label(self.receive_tab, "receive_hint").pack(anchor="w", pady=(0, 5))
        self.rx_preview = self.text_box(self.receive_tab, height=7)
        self.help_text = self.text_box(self.help_tab, height=8, font=("Segoe UI", 10), wrap="word")

        self.log_frame = self.box(self.panes, "log_frame")
        self.panes.add(self.log_frame, weight=2)
        row = ttk.Frame(self.log_frame)
        row.pack(fill="x", pady=(0, 4))
        self.progress = ttk.Progressbar(row, maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.cancel_button = self.button(row, "cancel", self.cancel_transfer, managed=False)
        self.cancel_button.pack(side="left")
        self.button(row, "clear_log", self.clear_log, managed=False).pack(side="left", padx=(5, 0))
        ttk.Label(self.log_frame, textvariable=self.status, wraplength=1000).pack(anchor="w", pady=(0, 4))
        self.log = self.text_box(self.log_frame, height=5, wrap="word")
        from .romstream_gui import RomDumpPanel
        self.rom_panel = RomDumpPanel(self.rom_page, host=self)
        self.rom_panel.pack(fill="both", expand=True)

    def text_box(self, parent, *, height, readonly=True, font=("Consolas", 10), wrap="none"):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, height=height, wrap=wrap, font=font, undo=not readonly,
                       borderwidth=1, relief="sunken", padx=5, pady=4)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vertical.set)
        vertical.pack(side="right", fill="y")
        if wrap == "none":
            horizontal = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
            text.configure(xscrollcommand=horizontal.set)
            horizontal.pack(side="bottom", fill="x")
        text.pack(fill="both", expand=True)
        if readonly:
            text.configure(state="disabled")
        return text

    @staticmethod
    def set_text(widget, value):
        state = widget.cget("state")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state=state)

    def localize(self):
        self.workspaces.tab(self.transfer_page, text="Program transfer" if self.language == "en" else "Transfert de programmes")
        self.workspaces.tab(self.rom_page, text="ROM backup" if self.language == "en" else "Sauvegarde ROM")
        self.rom_panel.translate()
        for widget, key in self.translatable:
            if widget.winfo_exists():
                widget.configure(text=self.t(key))
        for frame, key in ((self.basic_tab, "basic_tab"), (self.asm_tab, "asm_tab"),
                           (self.receive_tab, "receive_tab"), (self.help_tab, "help_tab")):
            self.tabs.tab(frame, text=self.t(key))
        self.update_example_menus()
        self.language_display.set(LANGUAGES[self.language])
        self.update_serial_hint()
        self.set_text(self.help_text, REFERENCE[self.language])
        self.status.set(self.rendered(self.last_status))
        if self.last_error is not None:
            self.status.set(friendly_error(self.last_error, self.language))
        self.update_rx_status()
        self.validate_basic()
        self.validate_asm()

    def change_language(self, _event=None):
        selected = self.language_display.get()
        self.set_language(next((code for code, name in LANGUAGES.items() if name == selected), "fr"))

    def set_language(self, code):
        if code not in LANGUAGES:
            return
        self.language = code
        self.localize()
        self.save_config()

    def set_status(self, value):
        self.last_error = None
        self.last_status = value
        self.status.set(self.rendered(value))

    def show_error(self, title, error):
        self.last_error = error
        detail = friendly_error(error, self.language)
        self.status.set(detail)
        self.append_log(msg("log_error", detail=detail))
        messagebox.showerror(self.t(title), detail, parent=self)

    def refresh_ports(self, initial=False):
        try:
            old_device = self.port_lookup.get(self.port.get(), self.saved["port"] if initial else "")
            ports = sorted(list_ports.comports(), key=lambda port: (port.vid != 0x0403, port.device))
            self.port_lookup = {f"{port.device} — {port.description}" + (" [FTDI]" if port.vid == 0x0403 else ""): port.device for port in ports}
            self.port_box.configure(values=tuple(self.port_lookup))
            matching = next((label for label, device in self.port_lookup.items() if device == old_device), "")
            expected = [label for label in self.port_lookup if "SHARP" in label.upper()]
            self.port.set(matching or (expected[0] if len(expected) == 1 else next(iter(self.port_lookup)) if len(ports) == 1 else ""))
            self.set_status(msg("ready" if ports else "no_ports"))
        except Exception as error:
            self.set_status(msg("ports_error", detail=str(error)))

    def settings_changed(self, *_):
        self.update_example_menus()
        self.update_serial_hint()
        self.validate_basic()
        self.validate_asm()
        if self.pending_config:
            self.after_cancel(self.pending_config)
        self.pending_config = self.after(400, self.save_config)

    def update_example_menus(self):
        key = (self.language, self.model.get().startswith("PC-G850"))
        if getattr(self, "_example_menu_key", None) == key:
            return
        self._example_menu_key = key
        for menu, common, specific, loader in (
            (self.basic_examples_menu, BASIC_EXAMPLES, G850_BASIC_EXAMPLES, self.load_basic),
            (self.asm_examples_menu, ASM_EXAMPLES, G850_ASM_EXAMPLES, self.load_asm_example),
        ):
            menu.delete(0, "end")
            for key, relative in common.items():
                menu.add_command(label=self.t(key), command=lambda path=relative, load=loader: load(resources() / "examples" / path))
            if self.model.get().startswith("PC-G850"):
                menu.add_separator()
                for key, relative in specific.items():
                    path = relative.format(lang=self.language)
                    menu.add_command(label=self.t(key), command=lambda path=path, load=loader: load(resources() / "examples" / path))

    def update_serial_hint(self):
        key = "serial_hint_g801" if self.model.get() == "PC-G801" else "serial_hint"
        frame = f"{self.data_bits.get()}{self.parity.get()}{self.stop_bits.get()}"
        self.serial_hint.set(self.t(key, baud=self.baud.get(), frame=frame))

    def apply_recommended_settings(self):
        if self.is_busy():
            return
        self.baud.set("4800")
        self.data_bits.set("8")
        self.parity.set("N")
        self.stop_bits.set("1")
        self.save_config()

    def save_config(self):
        if self.pending_config:
            self.after_cancel(self.pending_config)
        self.pending_config = None
        values = dict(self.saved)
        values['rom_directory'] = self.rom_panel.destination.get()
        values.update(language=self.language, model=self.model.get(), port=self.port_lookup.get(self.port.get(), ""))
        values["expanded_ram"] = "yes" if self.expanded_ram.get() else "no"
        if self.baud.get() in {"300", "600", "1200", "2400", "4800", "9600"}:
            values["baud"] = self.baud.get()
        for key, variable, choices in (("data_bits", self.data_bits, ("7", "8")),
                                       ("parity", self.parity, ("N", "E", "O")),
                                       ("stop_bits", self.stop_bits, ("1", "2"))):
            if variable.get() in choices:
                values[key] = variable.get()
        for key, variable, maximum in (("line_delay_ms", self.line_delay, 2000), ("char_delay_ms", self.char_delay, 100)):
            try:
                number = float(variable.get().replace(",", "."))
                if math.isfinite(number) and 0 <= number <= maximum:
                    values[key] = f"{number:g}"
            except ValueError:
                pass
        for key, variable in (("load_address", self.load_address), ("entry_address", self.entry_address)):
            try:
                values[key] = f"{parse_address(variable.get()):04X}"
            except FormatError:
                pass
        try:
            save_settings(self.settings_file, values)
            self.saved = values
            self._last_ini_error = None
        except OSError as error:
            if str(error) != self._last_ini_error:
                self.append_log(msg("ini_error", detail=str(error)))
            self._last_ini_error = str(error)

    def choose_basic(self):
        if self.is_busy():
            return
        path = filedialog.askopenfilename(parent=self, title=self.t("choose_basic"), filetypes=[(self.t("basic_files"), "*.bas *.txt"), (self.t("all_files"), "*.*")])
        if path:
            self.load_basic(Path(path))

    def load_basic(self, path: Path):
        if self.is_busy():
            return False
        if self.basic_dirty and not messagebox.askyesno(self.t("unsaved"), self.t("discard_source"), parent=self):
            return False
        try:
            if path.suffix.lower() not in {".bas", ".txt"}:
                raise FormatError("basic_suffix")
            text = read_source(path)
            prepare(text, path.name, "basic", self.model.get(), self.language)
        except (OSError, FormatError) as error:
            self.show_error("file_error", error)
            return False
        self.basic_path = path
        self.basic_original = text
        self.set_text(self.editor, text)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.basic_dirty = False
        self.validate_basic()
        self.tabs.select(self.basic_tab)
        return True

    def source_modified(self, _event=None):
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        if self.pending_validation:
            self.after_cancel(self.pending_validation)
        self.pending_validation = self.after(250, self.validate_basic)

    def validate_basic(self):
        if self.pending_validation:
            self.after_cancel(self.pending_validation)
        self.pending_validation = None
        source = self.editor.get("1.0", "end-1c")
        self.basic_dirty = source != self.basic_original
        name = selection_label(self.basic_path) if self.basic_path else self.t("no_file")
        self.basic_file_label.set(name + (" *" if self.basic_dirty else ""))
        self.basic_program = None
        if source.strip():
            try:
                self.basic_program = prepare(source, self.basic_path.name if self.basic_path else "program.bas", "basic", self.model.get(), self.language)
                self.basic_info.set(self.t("basic_summary", lines=len(self.basic_program.lines), size=self.basic_program.size))
            except FormatError as error:
                self.basic_info.set(self.t("validation_error", detail=error.render(self.language)))
        else:
            self.basic_info.set(self.t("editor_hint"))
        self.update_controls()

    def choose_asm(self):
        if self.is_busy():
            return
        path = filedialog.askopenfilename(parent=self, title=self.t("choose_asm"), filetypes=[(self.t("asm_files"), "*.ihx *.hex *.bin"), (self.t("all_files"), "*.*")])
        if path:
            self.load_asm(Path(path))

    def load_asm_example(self, path):
        if self.is_busy():
            return
        self.load_address.set("0100")
        self.entry_address.set("0100")
        self.load_asm(path)

    def load_asm(self, path: Path):
        if self.is_busy():
            return False
        try:
            if path.suffix.lower() not in {".bin", ".hex", ".ihx"}:
                raise FormatError("binary_suffix")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise FormatError("file_large")
            data = path.read_bytes()
            self.prepare_asm(path, data)
        except (OSError, FormatError) as error:
            self.show_error("file_error", error)
            return False
        self.asm_path, self.asm_data = path, data
        self.validate_asm()
        self.tabs.select(self.asm_tab)
        return True

    def prepare_asm(self, path, data):
        if path.suffix.lower() == ".bin":
            return prepare_binary(data, parse_address(self.load_address.get()), path.name, self.model.get(), self.language, self.expanded_ram.get())
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise FormatError("not_text") from None
        return prepare(text, path.name, "hex", self.model.get(), self.language, self.expanded_ram.get())

    def validate_asm(self):
        self.asm_program = None
        self.asm_file_label.set(selection_label(self.asm_path) if self.asm_path else self.t("no_file"))
        if self.asm_path is None:
            self.asm_info.set("")
            self.asm_hint.set(self.t("asm_empty_hint"))
        else:
            try:
                program = self.prepare_asm(self.asm_path, self.asm_data)
                entry = parse_address(self.entry_address.get())
                self.asm_program = program
                self.asm_info.set(self.t("asm_summary", kind=self.t("binary_kind" if program.kind == "binary" else "hex_kind"), count=program.data_bytes, start=program.start, end=program.end, size=program.size))
                reserve = program.reserve_end
                self.asm_hint.set(self.t("asm_hint", mon="CALL #5,&HC000" if self.model.get() == "PC-G820" else "MON", reserve=reserve, entry=entry))
                prefix = self.t("binary_preview", name=program.name, count=program.data_bytes, start=program.start, end=program.end)
                self.set_text(self.asm_preview, prefix + program.preview)
            except FormatError as error:
                self.asm_info.set(self.t("validation_error", detail=error.render(self.language)))
                self.asm_hint.set(self.t("asm_empty_hint"))
                self.set_text(self.asm_preview, error.render(self.language))
        self.update_controls()

    def save_source(self):
        if self.is_busy():
            return
        path = filedialog.asksaveasfilename(parent=self, title=self.t("save_basic_title"), initialfile=self.basic_path.name if self.basic_path else "program.bas", defaultextension=".bas", filetypes=[(self.t("basic_files"), "*.bas *.txt"), (self.t("all_files"), "*.*")])
        if path:
            try:
                source = self.editor.get("1.0", "end-1c")
                Path(path).write_text(source, encoding="utf-8", newline="\n")
                self.basic_path, self.basic_original = Path(path), source
                self.validate_basic()
                self.set_status(msg("source_saved", path=path))
            except OSError as error:
                self.show_error("save_error", error)

    def get_settings(self):
        try:
            return Settings(self.port_lookup.get(self.port.get(), ""), baud=int(self.baud.get()),
                            data_bits=int(self.data_bits.get()), parity=self.parity.get(),
                            stop_bits=int(self.stop_bits.get()),
                            line_delay=float(self.line_delay.get().replace(",", ".")) / 1000,
                            char_delay=float(self.char_delay.get().replace(",", ".")) / 1000)
        except ValueError as error:
            if isinstance(error, LocalizedError):
                raise
            raise FormatError("settings_error", detail=str(error)) from error

    def is_busy(self):
        return self.worker is not None or bool(getattr(self, "rom_panel", None) and self.rom_panel.busy)

    def update_controls(self):
        busy = self.is_busy()
        for widget, normal in self.controls:
            widget.configure(state="disabled" if busy else normal)
        self.editor.configure(state="disabled" if busy else "normal")
        self.basic_send_button.configure(state="normal" if not busy and self.basic_program else "disabled")
        self.asm_send_button.configure(state="normal" if not busy and self.asm_program else "disabled")
        self.load_address_entry.configure(state="normal" if not busy and (self.asm_path is None or self.asm_path.suffix.lower() == ".bin") else "disabled")
        self.save_source_button.configure(state="normal" if not busy and self.editor.get("1.0", "end-1c") else "disabled")
        self.save_rx_button.configure(state="normal" if not busy and self.received else "disabled")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if getattr(self, "rom_panel", None):
            self.rom_panel.update_controls(busy)

    def start_send_basic(self):
        if not self.is_busy():
            self.validate_basic()
            self.start_send(self.basic_program)

    def start_send_asm(self):
        if not self.is_busy():
            self.validate_asm()
            self.start_send(self.asm_program)

    def start_send(self, program):
        if self.is_busy() or program is None:
            return
        try:
            settings = self.get_settings()
        except ValueError as error:
            self.last_error = error
            self.status.set(friendly_error(error, self.language))
            return
        self.begin("send", settings, program)

    def start_receive(self):
        if self.is_busy():
            return
        try:
            settings = self.get_settings()
        except ValueError as error:
            self.last_error = error
            self.status.set(friendly_error(error, self.language))
            return
        if self.received and not self.received_saved and not messagebox.askyesno(self.t("new_receive"), self.t("replace_receive"), parent=self):
            return
        self.received = b""
        self.received_complete = self.received_saved = False
        self.set_text(self.rx_preview, "")
        self.update_rx_status()
        self.tabs.select(self.receive_tab)
        self.begin("receive", settings)

    def start_cts_check(self):
        if self.is_busy():
            return
        try:
            settings = self.get_settings()
        except ValueError as error:
            self.last_error = error
            self.status.set(friendly_error(error, self.language))
            return
        self.begin("cts", settings)

    def begin(self, operation, settings, program=None):
        self.cancel_event.clear()
        self.started = time.monotonic()
        self.set_status(msg("opening"))
        self.progress.configure(value=0)
        self.save_config()
        log_key = {"send": "log_send", "receive": "log_receive", "cts": "log_cts"}[operation]
        self.append_log(msg(log_key, name=program.name if program else "", port=settings.port, baud=settings.baud, frame=settings.frame, flow="ON" if settings.rtscts else "OFF"))

        def run():
            try:
                notify = lambda kind, value: self.events.put((kind, value))
                if operation == "send":
                    result = send(program, settings, self.cancel_event, notify)
                elif operation == "receive":
                    result = receive(settings, self.cancel_event, notify)
                else:
                    result = monitor_cts(settings, self.cancel_event, notify)
                self.events.put(("done", (operation, result, program.kind if program else None)))
            except Exception as error:
                self.events.put(("error", error))

        self.worker = threading.Thread(target=run, daemon=True)
        self.update_controls()
        self.worker.start()

    def cancel_transfer(self):
        if self.rom_panel.busy:
            self.rom_panel.cancel.set()
            return
        self.cancel_event.set()
        self.set_status(msg("cancelling"))

    def update_rx_status(self):
        key = "rx_done" if self.received_complete else "rx_progress" if self.is_busy() and self.received else "rx_partial" if self.received else "rx_none"
        self.rx_status.set(self.t(key, count=len(self.received)))

    def poll_events(self):
        if self.poll_after_id:
            self.after_cancel(self.poll_after_id)
        self.poll_after_id = None
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.set_status(value)
                    self.append_log(value)
                elif kind == "progress":
                    current, total = value
                    self.progress.configure(value=100 * current / max(total, 1))
                    self.set_status(msg("tx_progress", current=current, total=total, seconds=time.monotonic() - self.started))
                elif kind == "received":
                    self.received = value
                    self.received_saved = False
                    preview = value[:20000].decode("ascii", errors="replace")
                    self.set_text(self.rx_preview, preview + (self.t("preview_limit") if len(value) > 20000 else ""))
                    self.update_rx_status()
                elif kind in {"done", "error"}:
                    self.worker = None
                    if kind == "error":
                        self.last_error = value
                        detail = friendly_error(value, self.language)
                        self.status.set(detail)
                        self.append_log(msg("log_cancel" if isinstance(value, Cancelled) else "log_error", detail=detail))
                    elif value[0] == "cts":
                        self.set_status(msg("cts_done"))
                        self.append_log(self.last_status)
                    elif value[0] == "send":
                        self.progress.configure(value=100)
                        basic = len(value) > 2 and value[2] == "basic"
                        self.set_status(msg("tx_basic_done" if basic else "tx_done", count=value[1]))
                        self.append_log(self.last_status)
                        if basic:
                            self.append_log(msg("basic_after_send"))
                    else:
                        self.received = value[1]
                        self.received_complete = True
                        self.progress.configure(value=100)
                        self.set_status(msg("rx_done", count=len(self.received)))
                        self.append_log(self.last_status)
                    self.update_controls()
                    self.update_rx_status()
                    if self.closing:
                        self.destroy()
                        return
        except queue.Empty:
            pass
        self.poll_after_id = self.after(75, self.poll_events)

    def append_log(self, value):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {self.rendered(value)}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.set_text(self.log, "")

    def save_received(self):
        if not self.received or self.is_busy():
            return
        suffix = ".hex" if self.received.lstrip().startswith(b":") else ".bas"
        stem = "reception" if self.language == "fr" else "received"
        if not self.received_complete:
            stem += "-partielle" if self.language == "fr" else "-partial"
        path = filedialog.asksaveasfilename(parent=self, title=self.t("save_receive_title"), initialfile=stem + suffix, defaultextension=suffix, filetypes=[(self.t("program_files"), f"*{suffix}"), (self.t("all_files"), "*.*")])
        if path:
            try:
                Path(path).write_bytes(self.received)
                self.received_saved = True
                self.set_status(msg("receive_saved", path=path))
            except OSError as error:
                self.show_error("save_error", error)

    def open_manual(self):
        anchor = "#english" if self.language == "en" else "#francais"
        webbrowser.open((resources() / "docs" / "README.html").as_uri() + anchor)

    def open_rom_dump(self):
        self.workspaces.select(self.rom_page)

    def on_close(self):
        if self.is_busy():
            if messagebox.askyesno(self.t("busy_title"), self.t("close_busy"), parent=self):
                self.closing = True
                self.cancel_transfer()
            return
        if self.received and not self.received_saved and not messagebox.askyesno(self.t("rx_title"), self.t("close_rx"), parent=self):
            return
        if self.basic_dirty and not messagebox.askyesno(self.t("unsaved"), self.t("close_source"), parent=self):
            return
        self.save_config()
        self.destroy()

    def destroy(self):
        if getattr(self, "rom_panel", None):
            self.rom_panel.cancel.set()
            self.rom_panel.destroy()
        for identifier in self.tk.splitlist(self.tk.call("after", "info")):
            try:
                self.after_cancel(identifier)
            except tk.TclError:
                pass
        super().destroy()


def main(rom_dump=False):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PRaimbault.SharpPCGLink")
    app = LinkApp()
    if rom_dump:
        app.open_rom_dump()
    app.mainloop()
