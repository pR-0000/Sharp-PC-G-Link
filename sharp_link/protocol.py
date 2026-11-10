"""Prepare documented TEXT/SIO and monitor Intel HEX streams, without hardware I/O."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

from .i18n import LocalizedError, tr

MODELS = (
    "PC-G801", "PC-E200", "PC-G802", "PC-G803", "PC-G805", "PC-G811",
    "PC-G813", "PC-G815", "PC-G820", "PC-G830", "PC-G850", "PC-G850S",
    "PC-G850V", "PC-G850VS",
)
SMALL_RAM_MODELS = {"PC-G801", "PC-G802", "PC-G803", "PC-G820"}
G850_RAM_MODELS = {"PC-G850", "PC-G850S", "PC-G850V", "PC-G850VS"}
# USER reservation ceiling with an empty user area (30,179 bytes).
# The remaining physical RAM is needed by the firmware and its stack.
G850_USER_MAX = 0x76E2
G80X_EXPANDED_USER_MAX = 0x77E2
MAX_FILE_BYTES = 256 * 1024
EOF = b"\x1a"


class FormatError(LocalizedError, ValueError):
    """An input cannot safely be sent in the selected format."""


@dataclass(frozen=True)
class PreparedFile:
    name: str
    kind: str
    lines: tuple[bytes, ...]
    preview: str
    note: str = ""
    start: int | None = None
    end: int | None = None
    data_bytes: int = 0
    reserve_limit: int = 0x7FFF

    @property
    def wire(self) -> bytes:
        return b"".join(self.lines) + EOF

    @property
    def size(self) -> int:
        return sum(map(len, self.lines)) + 1

    @property
    def reserve_end(self) -> int:
        assert self.end is not None
        return min(self.end | 0xFF, self.reserve_limit)


def read_source(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise FormatError("file_large")
    raw = path.read_bytes()
    try:
        # A UTF-8 BOM is a file encoding marker, never part of the Sharp stream.
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FormatError("not_text") from None


def clean_lines(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Some Sharp exports contain the DOS/SIO terminator. Accept only at EOF.
    text = text.rstrip("\n")
    if text.endswith("\x1a"):
        text = text[:-1].rstrip("\n")
    if "\x1a" in text:
        raise FormatError("embedded_eof")
    if not text.strip():
        raise FormatError("file_empty")
    for line_no, line in enumerate(text.split("\n"), 1):
        for char in line:
            if not (32 <= ord(char) <= 126):
                raise FormatError("non_ascii", line=line_no, char=char)
    return text.split("\n")


def intel_record(address: int, data: bytes, record_type: int = 0) -> str:
    body = bytes((len(data), address >> 8, address & 255, record_type)) + data
    return ":" + (body + bytes((-sum(body) & 255,))).hex().upper()


def parse_hex(lines: list[str]) -> tuple[list[str], int, int, int]:
    normalized: list[str] = []
    memory: dict[int, int] = {}
    eof_seen = False
    for line_no, original in enumerate(lines, 1):
        line = original.strip()
        if not line:
            continue
        if eof_seen:
            raise FormatError("hex_after_eof", line=line_no)
        if not re.fullmatch(r":[0-9a-fA-F]+", line) or len(line) % 2 != 1:
            raise FormatError("hex_invalid", line=line_no)
        record = bytes.fromhex(line[1:])
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 255:
            raise FormatError("hex_checksum", line=line_no)
        count, hi, lo, kind = record[:4]
        address = hi * 256 + lo
        if kind == 1:
            if count or address:
                raise FormatError("hex_bad_eof")
            eof_seen = True
        elif kind == 0:
            if not count:
                raise FormatError("hex_empty_record")
            if address < 0x0100 or address + count > 0x8000:
                raise FormatError("hex_range")
            for offset, value in enumerate(record[4:-1]):
                location = address + offset
                if location in memory:
                    raise FormatError("hex_overlap", address=location)
                memory[location] = value
        else:
            raise FormatError("hex_type", kind=kind)
        normalized.append(line.upper())
    if not eof_seen or not memory:
        raise FormatError("hex_missing_eof")
    return normalized, min(memory), max(memory), len(memory)


def prepare(text: str, name: str = "programme.bas", mode: str = "auto",
            model: str = "PC-G801", language: str = "fr", expanded_ram: bool = False) -> PreparedFile:
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise FormatError("file_large")
    lines = clean_lines(text)
    if mode == "auto":
        if next((line for line in lines if line.strip()), "").lstrip().startswith(":"):
            mode = "hex"
        elif Path(name).suffix.lower() in {".hex", ".ihx"}:
            mode = "hex"
        elif Path(name).suffix.lower() == ".bas":
            mode = "basic"
        else:
            mode = "text"
    if mode not in {"basic", "text", "hex"}:
        raise FormatError("bad_format")
    start = end = None
    count = 0
    notes: list[str] = []
    reserve_limit = ((G80X_EXPANDED_USER_MAX if expanded_ram else 0x17E2) if model in SMALL_RAM_MODELS else
                     G850_USER_MAX if model in G850_RAM_MODELS else 0x7FFF)
    if mode == "hex":
        lines, start, end, count = parse_hex(lines)
        if model in SMALL_RAM_MODELS and not expanded_ram and end > 0x17E2:
            raise FormatError("small_ram", end=end, model=model)
        if model in SMALL_RAM_MODELS and expanded_ram and end > G80X_EXPANDED_USER_MAX:
            raise FormatError("expanded_ram_range", end=end, model=model)
        if model in G850_RAM_MODELS and end > G850_USER_MAX:
            raise FormatError("g850_ram", end=end, model=model)
        notes.append(tr(language, "hex_note", count=count, start=start, end=end))
        if start != 0x0100:
            notes.append(tr(language, "entry_note"))
    elif mode == "basic":
        lines = [line for line in lines if line.strip()]
        previous = 0
        for index, line in enumerate(lines, 1):
            match = re.fullmatch(r"\s*(\d+)\s+(.+)", line)
            if not match or not previous < int(match[1]) <= 65279:
                raise FormatError("bad_basic_line", line=index)
            previous = int(match[1])
        notes.append(tr(language, "basic_note", count=len(lines)))
    else:
        notes.append(tr(language, "text_note"))
    if any(len(line) > 255 for line in lines):
        raise FormatError("long_line")
    wire_lines = tuple(line.encode("ascii") + b"\r\n" for line in lines)
    if model in SMALL_RAM_MODELS and mode != "hex" and sum(map(len, wire_lines)) > 5000:
        notes.append(tr(language, "large_text_note"))
    return PreparedFile(name, mode, wire_lines, "\n".join(lines), " ".join(notes), start, end, count, reserve_limit)


def parse_address(value: str) -> int:
    normalized = value.strip()
    if normalized.lower().startswith(("0x", "&h")):
        normalized = normalized[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{1,4}", normalized):
        raise FormatError("bad_address", value=value)
    return int(normalized, 16)


def prepare_binary(data: bytes, address: int, name: str = "programme.bin",
                   model: str = "PC-G801", language: str = "fr", expanded_ram: bool = False) -> PreparedFile:
    """BIN is a host file format: MON R still receives a validated Intel HEX stream."""
    if not data:
        raise FormatError("file_empty")
    if address < 0x100 or address + len(data) > 0x8000:
        raise FormatError("binary_range")
    records = [intel_record(address + offset, data[offset:offset + 16]) for offset in range(0, len(data), 16)]
    records.append(":00000001FF")
    prepared = prepare("\n".join(records), name, "hex", model, language, expanded_ram)
    dump = [f"{address + offset:04X}  " + " ".join(f"{byte:02X}" for byte in data[offset:offset + 16]).ljust(47)
            + "  |" + "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data[offset:offset + 16]) + "|"
            for offset in range(0, min(len(data), 20000), 16)]
    return replace(prepared, kind="binary", preview="\n".join(dump))


def instructions(program: PreparedFile, model: str) -> str:
    if program.kind in {"hex", "binary"}:
        # Reserve a whole page when possible; this is a recommendation, never sent as a command.
        expanded = program.reserve_limit == G80X_EXPANDED_USER_MAX
        end = min(program.reserve_end, 0x17E2) if model in SMALL_RAM_MODELS and not expanded else program.reserve_end
        mon = "CALL #5,&HC000" if model == "PC-G820" else "MON"
        return (
            "Sur le Sharp, avant l'envoi\n\n"
            f"1. BASIC, mode RUN : {mon} puis ENTER.\n"
            f"2. Dans le moniteur : USER{end:04X} puis ENTER.\n"
            "   Sauvegarder d'abord les programmes présents ; USER réserve la mémoire.\n"
            "3. Taper R puis ENTER pour attendre le transfert.\n"
            "4. Cliquer sur Envoyer ici.\n\n"
            "Après réception\n\n"
            "Lancer avec G suivi de l'adresse d'entrée indiquée par l'auteur. "
            "Pour notre exemple : G100, puis D110 pour voir la signature.\n\n"
            "Une adresse de chargement ne garantit pas le point d'entrée ni la compatibilité du programme."
        )
    return (
        "Sur le Sharp, avant l'envoi\n\n"
        "1. TEXT → Sio → Format : régler les paramètres affichés au-dessus.\n"
        "2. Sauvegarder le contenu TEXT/BASIC à conserver.\n"
        "3. TEXT → Sio → Load : attendre la réception.\n"
        "4. Cliquer sur Envoyer ici.\n\n"
        "Après réception\n\n" + (
            "TEXT → Basic → Basic←text (Basic<text), puis BASIC en mode RUN : RUN.\n\n"
            "Le transfert arrive dans TEXT ; la conversion vers BASIC est nécessaire."
            if program.kind == "basic" else
            "Le texte est disponible dans TEXT → Edit. Un source .asm doit encore être assemblé ; "
            "il n'est pas directement exécutable."
        )
    )
