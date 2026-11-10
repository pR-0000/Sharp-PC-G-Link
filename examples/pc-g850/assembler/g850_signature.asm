; PC-G850/S/V/VS: RAM signature, no ROM calls or port access.
; FR: MON -> USER01FF -> R, envoyer HEX/BIN, G100, puis D180.
; EN: MON -> USER01FF -> R, send HEX/BIN, G100, then D180.
; 0180h: 47 38 35 30 = G850. Caller stack and normal RET convention.
; Copyright (c) 2026 P.RAIMBAULT. MIT licence.
    org 0x0100
    ld hl,signature
    ld de,0x0180
    ld bc,4
    ldir
    ret
signature:
    db 'G850'
