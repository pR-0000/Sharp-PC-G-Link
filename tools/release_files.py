"""Shared publication filters for GitHub, source and Windows releases."""
from pathlib import Path

EXCLUDED_DIRECTORIES = {'.git', '.venv', '__pycache__', 'dist', 'deliverables', 'rom-dumps'}
EXCLUDED_FILES = {'sharp_pc_g_link.ini', 'sharp_pc_g_link.ini.tmp', 'hardware_validation.json',
                  'cpu_validation.json', 'stream_cpu_validation.json'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.log', '.exe', '.sym', '.lst'}


def is_public_file(relative: Path) -> bool:
    parts = tuple(part.lower() for part in relative.parts)
    if not parts or parts[0] == 'build' or any(p in EXCLUDED_DIRECTORIES for p in parts):
        return False
    if relative.suffix.lower() in EXCLUDED_SUFFIXES or relative.name.lower() in EXCLUDED_FILES:
        return False
    if relative.name.lower().endswith('_cpu_validation.json'):
        return False
    if parts[0] == 'docs' and (relative.name.startswith('VALIDATION.') or relative.name.startswith('ROM_G801_VALIDATION')):
        return False
    return True


def source_files(root: Path):
    return sorted(p for p in root.rglob('*') if p.is_file() and is_public_file(p.relative_to(root)))


def portable_files(root: Path):
    top = {'README.md', 'LICENSE.txt', 'LICENSE_FR.txt', 'NOTICE.md'}
    folders = {'examples', 'licenses', 'romdump', 'docs'}
    return [p for p in source_files(root) if p.relative_to(root).parts[0] in folders or p.name in top]
