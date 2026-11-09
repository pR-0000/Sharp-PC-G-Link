# Automatic ROM backup

[Français](AUTOMATIC.md) · **English** · [Sharp PC-G Link](../README.md#english)

The workflow is simply **send the dumper, then receive ROM data**. Identifiers, verification files and output folders are prepared automatically.

## Back up your ROM

Two actions are enough; **there is no session to create or resume manually**.

1. Choose the model and **4800 / 8N1**, also in Sharp **TEXT → Sio → Format**. The destination folder is remembered; if blank, it is requested on the first upload.
2. Back up programs you want to keep: the dumper replaces the assembly program in RAM. On G801 enter **MON → USER0AFF → R**, then click **1. Send dumper** on the PC.
3. Wait for loading to finish. Click **2. Receive entire ROM** on the PC, then enter **G100 once** on Sharp.
4. Wait for verified completion. Use **Open folder** to find the images and verification report. Each completed backup automatically gets its own dated subfolder, preserving earlier backups.

Independent reads, CRC, audit captures and recovery information are managed automatically. After interruption, press **BREAK on Sharp**, send the dumper again, and restart reception in the same window; verified blocks are retained. No W or G103 commands are needed between blocks.

The automatic dumper uses firmware routines: hardware support is established for the **PC-G805**; other profiles and ROM revisions require verification. Probed selectors do not establish physical ROM size. Personal ROMs are excluded from the project and release archives.

## Settings and errors

**On transfer errors or R returning immediately to the monitor, check TEXT → Sio → Format first**, especially after RESET. Select **4800 baud, 8 data bits, no parity, 1 stop, RS/CS, CR LF, EOF 1A**, then ENTER, with matching PC settings. The PC cannot configure Sharp remotely. PC-G820 enters the monitor through **CALL #5,&HC000**; instructions adapt to the model.

The G801 profile defaults to five selectors, including **font bank 04**. Bank/read options apply when sending the dumper; retain two reads. E200/G80X/G81X/G820/G830 profiles use port 19h, G850 profiles port 69h. Native routine compatibility depends on the firmware revision.

## Files and integrity

In the dated subfolder: `base.bin` contains 64 bytes of RAM vectors, `fixed.bin` the 8000h–BFFFh window, and `banks/` the sampled 16 KB windows. `report.json` records SHA-256 and identical/uniform banks. G801 receives a `g800/` export when the fixed window matches bank 00 and at least five banks were read.

`session.json`, `chunks/` and `captures/` are verification and recovery details retained automatically. Session describes internal storage, not a step users must perform. Do not alter these files during reception. Earlier completed backups are preserved.

Each 544-byte frame carries an identifier, address, bank, read number and CRC-16/CCITT-FALSE. The PC saves before ACK; a failed CRC requests retransmission, up to five attempts. Two matching reads and a valid END marker are required for success. Retransmitting a packet does not count as a new independent read.

## Development and older backups

[rom_stream.asm](rom_stream.asm) contains the original 678-byte agent. It uses native BCE8h/BCEBh/BFAFh/BCE2h routines and restores the bank before each call. No LCD port or RAM-bank selector is modified. `sharp_link/romstream.py` implements the protocol; `sharp_link/romstream_gui.py` the interface.

```text
python romdump/build_agent.py --assembler "path/to/sjasmplus.exe"
python -m unittest discover -s tests -v
python romdump/check_stream.py --rom-dir "path/to/ROM-backup"
```

Advanced users can reopen an existing backup after closing the application: `python "Sharp PC-G Link.pyw" --rom-dump --session "path/session.json"`. Older manual backups open their historical interface. For a new backup, simply use the ROM backup tab.

Bank ports are cross-checked with [MAME](https://github.com/mamedev/mame/blob/master/src/mame/sharp/pce220.cpp) and [g800](https://ver0.sakura.ne.jp/pc/g800src.0.11.4.tgz). Serial calls target PC-G805 firmware; no ROM is distributed.
