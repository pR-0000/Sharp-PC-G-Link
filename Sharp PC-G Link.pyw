"""Unique public launcher: double-click, then use either application tab."""
import sys
import traceback
from pathlib import Path

try:
    from sharp_link.config import config_path, load_settings
    language = load_settings(config_path())["language"]
    from sharp_link.bootstrap import ensure_runtime
    if not ensure_runtime(Path(__file__).resolve(), language):
        sys.exit(0)
    if "--manual" in sys.argv or "--session" in sys.argv:
        # Compatibility with launchers embedded in older backup sessions.
        from sharp_link.romdump_gui import main
        main()
    else:
        from sharp_link.gui import main
        main(rom_dump="--rom-dump" in sys.argv)
except Exception:
    from sharp_link.bootstrap import show_startup_error
    show_startup_error(traceback.format_exc())
    sys.exit(1)
