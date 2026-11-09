"""Build an offline Windows executable and separate portable/source archives."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sharp_link import __version__
from tools.release_files import source_files, portable_files
DELIVERABLES = ROOT.parent / "deliverables"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("L'exécutable Windows doit être construit sous Windows.")
    from tools.render_manual import render_all
    render_all(ROOT)
    if not args.skip_build:
        # Apply the same filters to embedded resources as to the public archives.
        with tempfile.TemporaryDirectory(prefix='sharp-link-resources-') as temporary:
            staging = Path(temporary)
            for path in portable_files(ROOT):
                target = staging / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            subprocess.run([
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
                "--windowed", "--name", "Sharp PC-G Link", "--noupx",
                "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
                "--specpath", str(ROOT / "build"),
                "--add-data", f"{staging / 'examples'};examples",
                "--add-data", f"{staging / 'romdump'};romdump",
                "--add-data", f"{staging / 'docs'};docs",
                "--add-data", f"{staging / 'LICENSE.txt'};.",
                "--add-data", f"{staging / 'LICENSE_FR.txt'};.",
                str(ROOT / "Sharp PC-G Link.pyw"),
            ], cwd=ROOT, check=True)
    exe = ROOT / "dist" / "Sharp PC-G Link.exe"
    if not exe.is_file():
        raise SystemExit("Exécutable absent.")
    DELIVERABLES.mkdir(exist_ok=True)
    portable = DELIVERABLES / f"Sharp_PC-G_Link_{__version__}_Windows.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(exe, "Sharp PC-G Link/Sharp PC-G Link.exe")
        # First run creates preferences; updates never replace an existing user's INI.
        for path in portable_files(ROOT):
            relative = path.relative_to(ROOT)
            if path.is_file():
                archive.write(path, "Sharp PC-G Link/" + relative.as_posix())
    sources = DELIVERABLES / f"Sharp_PC-G_Link_{__version__}_Sources.zip"
    with zipfile.ZipFile(sources, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(ROOT):
            relative = path.relative_to(ROOT)
            archive.write(path, "Sharp PC-G Link/" + relative.as_posix())
    checksums = []
    for path in (exe, portable, sources):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None
        checksums.append(f"{digest}  {path.name}")
        print(f"{path} ({path.stat().st_size:,} octets)")
    (DELIVERABLES / f"Sharp_PC-G_Link_{__version__}_SHA256.txt").write_text("\n".join(checksums) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
