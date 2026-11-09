"""Convert a raw Z80 binary to 16-bit Intel HEX (standard library only)."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sharp_link.protocol import intel_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--address", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()
    data = args.source.read_bytes()
    if not data or args.address < 0x100 or args.address + len(data) > 0x8000:
        parser.error("Le binaire doit être non vide, dans la plage 0100–7FFFh. Vérifier la mémoire du modèle.")
    if args.source.resolve() == args.destination.resolve():
        parser.error("La destination doit être différente du binaire source.")
    records = [intel_record(args.address + index, data[index:index + 16]) for index in range(0, len(data), 16)]
    records.append(":00000001FF")
    # Exclusive creation protects an existing program from a command-line typo.
    with args.destination.open("x", encoding="ascii", newline="\n") as stream:
        stream.write("\n".join(records) + "\n")
    print(f"{len(data)} octets, {args.address:04X}–{args.address + len(data) - 1:04X} : {args.destination}")


if __name__ == "__main__":
    main()
