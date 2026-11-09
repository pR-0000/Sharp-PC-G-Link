# Transfer manual

[Français](TRANSFER.md) · [Home](../README.md#english)

## Prepare the connection

Select the model and serial port. Use an adapter matching the Sharp electrical levels and connector, with RTS/CTS. A standard RS-232 port cannot connect directly. If the FTDI adapter requires TXD/RXD/RTS#/CTS# inversion, configure it in its EEPROM; the software does not perform inversion.

Initial settings are **1200 baud / 7N1**, RTS/CTS enabled, XON/XOFF disabled, CR LF and EOF 1A. The initial delay is **50 ms per line**, with no extra character delay. **Recommended: 4800 / 8N1** selects the recommended baud rate and framing without changing the port, model or delays. The fields accept 7 or 8 data bits, N/E/O parity and 1 or 2 stop bits.

On the Sharp: **TEXT → Sio → Format**, matching baud/bits/parity/stop, **RS/CS**, **CR LF**, **EOF 1A**, then **ENTER**. For numbered listings, select **Line number = Yes** if available. The application does not configure the Sharp remotely. **Recheck this menu after RESET, on transfer errors or if R immediately returns to the monitor.** ROM backup requires 4800 / 8N1.

Profiles cover PC-E200, PC-G801/G802/G803/G805/G811/G813/G815/G820/G830/G850/G850S/G850V/G850VS. Selecting a model does not guarantee program compatibility with its RAM, display or ROM calls. PC-E500, PC-1600 and cassette recording are not supported.

## Send BASIC

1. Open a numbered ASCII `.bas` or `.txt`, or select a sample from **Examples**.
2. Optionally edit the listing in **BASIC source**. **Send BASIC transmits the editor contents**, including unsaved changes. Use **Save as** to keep a copy.
3. On the Sharp: back up data you want to keep, prepare an empty TEXT area if needed, then **TEXT → Sio → Load**.
4. Click **Send BASIC** on the PC and wait for the Sharp to return to its menu.
5. Open **TEXT → Edit** to inspect the listing; press Down if needed. The PC filename is not transmitted.
6. Convert with **TEXT → Basic → Basic←text**, switch to **BASIC / RUN MODE**, then type **RUN**.

Conversion replaces the existing BASIC program. Received text is not yet tokenized BASIC: **RUN cannot execute it before conversion**. Typing BASIC `LOAD` alone does not replace **TEXT → Sio → Load**. Tokenized BASIC images and cassette files are not accepted.

The software checks increasing line numbers from 1 to 65279, duplicates, order and lines exceeding 255 characters. Accented characters and unwanted controls are rejected. Line endings are normalized to CR LF with a single EOF 1A marker.

Included examples provide a message (`01_bonjour.bas`), the sum of squares from 1 to 10, result **385** (`02_calcul.bas`), and a number guessing game (`03_devine.bas`).

## Send a Z80 program

**BIN:** enter the origin address used during assembly. Bytes are converted automatically to Intel HEX. **HEX/IHX:** addresses come from the file; the BIN load address field is disabled. Checksums, lengths, overlaps and address limits are checked. Only records 00 (data) and 01 (end) are accepted.

Addresses are hexadecimal: `0100`, `0x0100` and `&H0100` are accepted. **Changing the load address does not relocate the code.** The **Entry point** field only displays the `G` command; it does not launch the program.

After backing up useful data: **MON → USERxxxx → R** on the Sharp, then **Send ASM** on the PC. Once loading finishes, enter **Gxxxx** with the documented entry point. On PC-G820, use **CALL #5,&HC000** to enter the monitor.

The USER suggestion covers the file through the end of its page; also allow RAM for variables and the stack. Accepted addresses are 0100–7FFFh, limited to 0100–17E2h for 8 KiB G801/G802/G803/G820 profiles. This check does not measure free RAM on the device. Assemble `.asm` sources before sending them.

### Included standalone example

Select **PC-G801 signature (.bin)** or **(.hex)**. Both represent the same 16-byte program, origin and entry **0100h**, without ROM calls or hardware access.

```text
MON
USER01FF
R
```

Click **Send ASM**, wait for completion, then enter:

```text
G100
D110
```

Memory at 0110h should start with **50 43 47 21**, ASCII `PCG!`. The program returns to the monitor with RET. Source is supplied in `examples/assembler/pcg801_signature.asm`.

## Receive and save

In the **Reception** panel, click **Receive**, wait for readiness, then start **TEXT → Sio → Save** on the Sharp. For BASIC, first convert using **TEXT → Basic → Text←basic**. For machine code, use `Wstart,end` in MON, such as `W100,113` for the example after execution.

**Save reception** retains received bytes without the final EOF 1A marker. The preview may visually substitute non-ASCII characters; the saved file preserves the original bytes. Without EOF, reception reports an error after 10 seconds of inactivity; partial data can still be saved. The software does not save it automatically.

The log displays settings, CTS waits, errors and completion messages. **Cancel** stops a wait; use BREAK on the Sharp if necessary. Completed PC transmission is not a file acknowledgement: check reception on the Sharp.

## Diagnostics and memory

**Check CTS** observes the signal for 60 seconds without writing UART bytes or reading incoming data. Opening the port still asserts RTS/DTR: this is not a passive voltage measurement. Cancel closes the port; stop the check before transferring. **Active CTS does not prove Load is running.**

**I/O DEVICE ERROR or R returns to the monitor:** first check TEXT → Sio → Format and ENTER, then the port, RS/CS, wiring, ground and adapter inversions. If the error precedes PC transmission, file bytes cannot be its cause. Close other serial software if the port is busy. A CTS wait times out after 20 seconds; check that the Sharp is waiting in Load or R. For missing characters, try 1200 baud on both devices and 100 ms per line.

**ERROR 10 after LOAD in BASIC:** use TEXT → Sio → Load, then Basic←text. **MEMORY OVER:** check `FRE` in BASIC/RUN and memory occupied by BASIC, TEXT, stored files and USER reservations.

**If FRE reports an inconsistent value near 64 KB on an 8 KB device: back up data, press RESET and answer Y to “MEMORY CLEAR O.K. ?”. This erases memory.** Check FRE and SIO format afterwards. The application does not read FRE or initiate RESET.

To release an old assembly reservation after backing up: `MON`, then `USER` displays the reservation; `USER00FF` releases it. Do not run the old code afterwards. This does not replace RESET with confirmed memory clear when memory state is inconsistent.

## Preferences and ROM backup

Language changes apply immediately. Language, model, port, baud rate, framing, delays, addresses and ROM directory are saved in **sharp_pc_g_link.ini** beside the launcher or executable. Existing log entries retain their original language. Updates preserve the existing file; the configuration template is `sharp_link/defaults.ini`.

The **ROM backup** tab uses a preassembled agent and two actions: send the dumper, then receive all data after a single G100. See the [ROM guide](../romdump/AUTOMATIC_EN.md) for compatibility limits and output files.

## References and development

[readrom](https://github.com/fu-sen/readrom) documents the monitor and backups; [z88dk](https://github.com/z88dk/z88dk/wiki/Platform---Sharp-PC) describes the Sharp family. The [z88dk SIO program](https://github.com/z88dk/z88dk/blob/master/examples/g800/send.py) provides a reference for RTS/CTS and line delays. See the [developer guide](DEVELOPMENT_EN.md) for tests and builds.
