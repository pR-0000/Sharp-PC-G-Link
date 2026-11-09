# Developing Sharp PC-G Link

[Français](DEVELOPMENT.md) · [Home](../README.md#english)

The only public entry point is **Sharp PC-G Link.pyw**. `sharp_link/gui.py` owns the window, preferences and shared serial settings; `RomDumpPanel` is embedded as its second tab. Older interfaces remain available for manual sessions through `--rom-dump --manual` or `--session path/session.json`.

From the repository root, with Python 3.10+:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/render_manual.py
python tools/package_source.py --lang en
```

GUI tests use real Tk widgets and simulated ports. They require a graphical session, do not transfer to connected hardware, and do not use personal preferences.

To build the standalone Windows executable and archives:

```text
python -m pip install -r tools/requirements-build.txt
python tools/build_windows.py
```

Outputs go to `dist/` and to `deliverables/` beside the repository. The build embeds ROM agents, examples and offline guides. The target machine does not need Python. Archives exclude local environments, personal INI files and user ROMs.

`tools/setup/` retains console recovery scripts for broken `.pyw` associations. `tools/legacy/` holds older entry points; new users do not need them. The root launcher offers graphical dependency setup when needed.

See the [ROM guide](../romdump/AUTOMATIC_EN.md) to rebuild or test the Z80 code. The supplied agent binaries are sufficient for normal use.
