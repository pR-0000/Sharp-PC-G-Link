; PC-G850/S/V/VS: six 144-column, eight-pixel-high LCD bands.
; FR: MON -> USER02FF -> R, envoyer HEX/BIN, G100. Une touche pour quitter.
; EN: MON -> USER02FF -> R, send HEX/BIN, G100. Any key returns.
; IOCS BFD0h: HL=data, B=pixel columns, D=cell row, E=cell column.
; IOCS BCFDh: wait for a key. No LCD ports or bank registers are written.
; Sources: g800 iocs.c, https://ver0.sakura.ne.jp/pc/
; Copyright (c) 2026 P.RAIMBAULT. MIT licence.
    org 0x0100
entry:
    push af
    push bc
    push de
    push hl
    push ix
    push iy
    ld hl,patterns
    ld de,0
    ld c,6
row_loop:
    ld a,(hl)
    push hl
    ld hl,buffer
    ld b,144
fill:
    ld (hl),a
    inc hl
    djnz fill
    ld hl,buffer
    ld b,144
    push bc
    push de
    call 0xBFD0
    pop de
    pop bc
    pop hl
    inc hl
    inc d
    dec c
    jr nz,row_loop
    call 0xBCFD
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    ret
patterns:
    db 0xFF,0x00,0xAA,0x55,0xF0,0x0F
    defs 0x0200-$,0
buffer:
    defs 144,0
    assert $ == 0x0290
