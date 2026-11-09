; Original Z80 ROM staging agent, MIT, (c) 2026 P.RAIMBAULT.
; FR: G100 bloc suivant; G103 relire le dernier; G106 recommencer.
; EN: G100 next block; G103 reread last; G106 restart.
; MON USER1400 reserves all state, packet and 4 KiB buffer on an 8 KiB G801.
; Native MON W300,1400 sends the framed copy. This agent has no ROM calls.
; Port 19h banking: fu-sen/readrom, MAME pce220.cpp, g800 io.c.
    ORG $0100
    jp next_entry
    jp repeat_entry
    jp reset_entry
next_entry:
    push af
    xor a
    jr enter
repeat_entry:
    push af
    ld a,1
    jr enter
reset_entry:
    push af
    ld a,2
enter:
    push bc
    push de
    push hl
    push ix
    push iy
    ld (entry_mode),a
    ld a,i
    push af                     ; P/V saves the caller's IFF2
    di
    ld a,(config_banks)
    dec a
    cp 16
    jp nc,finish                ; accepted count: 1..16
    inc a
    add a,a
    add a,a
    add a,5
    ld b,a                      ; base + 4 fixed + 4*bank count
    ld a,(entry_mode)
    cp 2
    jr nz,.select
    xor a
    ld (next_job),a
    dec a
    ld (last_job),a
.select:
    ld a,(entry_mode)
    dec a
    ld a,(last_job)
    jr z,.chosen
    ld a,(next_job)
.chosen:
    cp b
    jp nc,finish
    ld (current_job),a
    ld hl,packet
    ld (hl),0
    ld de,packet+1
    ld bc,$1100                 ; clear packet through guard at 1400h
    ldir
    in a,($19)
    ld (saved_bank),a
    ld (packet+22),a
    ld a,(current_job)
    ld (packet+20),a
    ld hl,0
    ld bc,$0040
    ld d,$FF                    ; FF = vector/fixed-window snapshot
    or a
    jr z,.copy
    ld bc,$1000
    dec a
    cp 4
    jr nc,.banked
    rlca
    rlca
    rlca
    rlca
    add a,$80
    ld h,a
    jr .copy
.banked:
    sub 4
    ld e,a
    srl a
    srl a
    ld d,a                      ; requested low-nibble ROM bank
    ld a,(saved_bank)
    and $F0
    or d
    out ($19),a
    ld a,e
    and 3
    rlca
    rlca
    rlca
    rlca
    add a,$C0
    ld h,a
.copy:
    ld a,d
    ld (packet+21),a
    ld (packet+24),hl
    ld (packet+26),bc
    ld de,buffer
    ldir
    ld a,(saved_bank)
    out ($19),a                 ; restore mapping before returning to ROM
    ld hl,buffer
    ld bc,(packet+26)
    call crc16
    ld (packet+28),de
    ld hl,config_tag
    ld de,packet+4
    ld bc,16
    ldir
    ld a,(copy_counter)
    inc a
    ld (copy_counter),a
    ld (packet+23),a
    ld a,(config_banks)
    ld (packet+30),a
    ld a,$5A
    ld (packet+31),a
    ld a,(current_job)
    ld (last_job),a
    inc a
    ld (next_job),a
    ld hl,packet_magic
    ld de,packet
    ld bc,4
    ldir                        ; commit marker written last
finish:
    pop af
    jp po,return_disabled
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    ei
    ret
return_disabled:
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    ret

; HL=bytes, BC=length -> DE=CRC-16/CCITT-FALSE (FFFF, polynomial 1021).
crc16:
    ld de,$FFFF
.byte:
    ld a,(hl)
    xor d
    ld d,a
    push bc
    ld b,8
.bit:
    sla e
    rl d
    jr nc,.next
    ld a,d
    xor $10
    ld d,a
    ld a,e
    xor $21
    ld e,a
.next:
    djnz .bit
    pop bc
    inc hl
    dec bc
    ld a,b
    or c
    jr nz,.byte
    ret
packet_magic: db "PRD1"
state_start:
entry_mode: db 0
next_job: db 0
last_job: db $FF
current_job: db 0
saved_bank: db 0
copy_counter: db 0
    ASSERT $ <= $02E0
    ds $02E0-$,0
config_magic: db "PCGDMP01"
config_banks: db 4
config_tag: ds 16,0
    ds $0300-$,0
packet: ds 32,0
image_end:
buffer EQU $0400
reserve_end EQU $1400
    ASSERT image_end == $0320
