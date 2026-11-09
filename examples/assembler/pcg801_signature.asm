; Sharp PC-G801 - demonstration sans appel ROM ni acces aux ports.
; Copyright (c) 2026 P.RAIMBAULT
; Origine 0x0100, signature source 0x010C, destination 0x0110.
; Dans MON : USER01FF, R, transfert du .hex, G100, puis D110.
; D110 doit commencer par 50 43 47 21 (ASCII PCG!).
; z88dk-z80asm -b pcg801_signature.asm
; ou pyz80 --obj=pcg801_signature.bin pcg801_signature.asm
; Le .hex fourni est deja pret ; aucun assembleur requis pour l'essai.

        org 0x0100
        ld hl,signature
        ld de,0x0110
        ld bc,4
        ldir
        ret
signature:
        defb 0x50,0x43,0x47,0x21
