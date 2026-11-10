"""Portable UTF-8 INI settings, with read-only migration from the 1.0 JSON file."""
import configparser
import json
import os
from pathlib import Path
import sys

DEFAULTS = {
    "language": "fr", "model": "PC-G801", "expanded_ram": "no", "port": "", "baud": "1200",
    "data_bits": "7", "parity": "N", "stop_bits": "1",
    "line_delay_ms": "50", "char_delay_ms": "0", "load_address": "0100", "entry_address": "0100", "rom_directory": "",
}
SECTIONS = {
    "interface": ("language", "model"),
    "serial": ("port", "baud", "data_bits", "parity", "stop_bits", "line_delay_ms", "char_delay_ms"),
    "assembler": ("load_address", "entry_address", "expanded_ram"),
    "rom": ("rom_directory",),
}


def config_path() -> Path:
    folder = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    return folder / "sharp_pc_g_link.ini"


def legacy_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home()))) if sys.platform == "win32" else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "Sharp PC-G Link" / "settings.json"


def load_settings(path: Path, legacy: Path | None = None) -> dict[str, str]:
    values = dict(DEFAULTS)
    parser = configparser.ConfigParser(interpolation=None)
    if path.exists():
        try:
            parser.read_string(path.read_text(encoding="utf-8-sig"))
            for section, keys in SECTIONS.items():
                for key in keys:
                    if parser.has_option(section, key):
                        values[key] = parser.get(section, key)
        except (OSError, UnicodeError, configparser.Error):
            return dict(DEFAULTS)
    elif legacy is not None:
        try:
            old = json.loads(legacy.read_text(encoding="utf-8"))
            if isinstance(old, dict):
                for key in DEFAULTS:
                    if key in old:
                        values[key] = str(old[key])
        except (OSError, ValueError):
            pass
    if values["language"] not in ("fr", "en"):
        values["language"] = "fr"
    values["expanded_ram"] = "yes" if values["expanded_ram"].strip().lower() in ("yes", "true", "1", "on") else "no"
    # Older INIs have no framing keys; malformed values must not discard other preferences.
    values["parity"] = values["parity"].strip().upper()
    values["parity"] = {"NONE": "N", "EVEN": "E", "ODD": "O"}.get(values["parity"], values["parity"])
    for key, choices in (("data_bits", ("7", "8")), ("parity", ("N", "E", "O")),
                         ("stop_bits", ("1", "2"))):
        values[key] = values[key].strip()
        if values[key] not in choices:
            values[key] = DEFAULTS[key]
    return values


def save_settings(path: Path, values: dict) -> None:
    parser = configparser.ConfigParser(interpolation=None)
    for section, keys in SECTIONS.items():
        parser[section] = {key: str(values.get(key, DEFAULTS[key])) for key in keys}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".ini.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            parser.write(stream)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
