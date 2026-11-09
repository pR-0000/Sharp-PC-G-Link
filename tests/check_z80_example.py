"""Optional independent assembly/CPU check; requires pyz80==1.3.0 and z80==1.2.0.

These are verification tools only, not application dependencies or bundled code.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import z80

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharp_link.protocol import parse_hex


def main():
    assembler = Path(sys.executable).parent / ("pyz80.exe" if sys.platform == "win32" else "pyz80")
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "signature.bin"
        subprocess.run([str(assembler), f"--obj={output}", str(ROOT / "examples/assembler/pcg801_signature.asm")], check=True)
        data = output.read_bytes()
    records, start, end, size = parse_hex((ROOT / "examples/assembler/pcg801_signature.hex").read_text().splitlines())
    hex_data = b"".join(bytes.fromhex(line[9:-2]) for line in records if line[7:9] == "00")
    assert data == hex_data
    assert data == (ROOT / "examples/assembler/pcg801_signature.bin").read_bytes()
    assert (start, end, size) == (0x100, 0x10F, 16)
    cpu = z80.Z80Machine()
    cpu.memory[0x100:0x110] = data
    cpu.pc, cpu.sp = 0x100, 0x1FF0
    cpu.memory[0x1FF0:0x1FF2] = bytes((0, 0x70))  # Mock monitor return address.
    cpu.set_breakpoint(0x7000)
    cpu.ticks_to_stop = 1000
    cpu.run()
    assert cpu.pc == 0x7000 and cpu.sp == 0x1FF2
    assert bytes(cpu.memory[0x110:0x114]) == b"PCG!"
    print("PASS : source assemble = HEX fourni ; signature PCG! a 0110 ; retour RET correct.")


if __name__ == "__main__":
    main()
