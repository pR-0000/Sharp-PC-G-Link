# ROM backup: legacy manual mode

[Français](README.md) · [Home](../README.md#english)

For a new backup, use the root launcher’s **ROM backup** tab: [automatic guide](AUTOMATIC_EN.md). This document describes the manual mode retained for historical-format backups.

## Preparation

Run `python "Sharp PC-G Link.pyw" --rom-dump --manual`. The interface supports FR/EN and uses Link’s INI file. Set **4800 / 8N1**, **RS/CS**, **CR LF**, **EOF 1A** in **TEXT → Sio → Format**, then ENTER. Check these values on errors or if R immediately returns to the monitor.

Back up programs you want to keep: the agent replaces the program in RAM. Select the model, port and bank selector count. Keep **two independent reads per block**. The selector count does not establish physical ROM capacity.

## Upload and receive

1. Click **New session** and choose the parent directory; a unique subfolder is created.
2. On the Sharp: **MON → USER1400 → R**, then **Upload agent** on the PC. On PC-G820, CALL #5,&HC000 replaces MON.
3. For each block, enter **G100** on the Sharp, wait for the monitor, click **Receive block**, then enter **W300,1400** on the Sharp.
4. For the second read, use **G103**, then **Receive block → W300,1400**. Follow the displayed commands until completion.

G100 advances after copying; G103 rereads the same source. Retransmitting the W buffer alone does not count as an independent read. On interruption or invalid CRC, repeat **Receive block → W300,1400**, without advancing with G100.

## Resume and files

**Resume** opens `session.json`, checks hashes and prepares the agent at the first incomplete block. Reload it with MON → USER1400 → R and follow the displayed commands. Do not mix machines or firmware revisions.

`base.bin` holds 64 bytes of RAM vectors; `fixed.bin` the 8000h–BFFFh window; `banks/` holds 16 KB windows per selector. `report.json` describes hashes, mirrors and integrity. `chunks/`, `captures/` and `session.json` support recovery. g800 export depends on the profile and mapping checks; user ROMs are not distributed.

The manual agent runs in RAM, saves/restores bank register 19h and uses the monitor for transmission. It does not call ROM serial routines. This mode retains its own profile limits: models using bank port 69h require the automatic workflow.

See the [developer guide](../docs/DEVELOPMENT_EN.md) to rebuild agents and run checks.
