"""Legacy launcher; normal use starts the root Sharp PC-G Link.pyw."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sharp_link.gui import main
main(rom_dump=True)
