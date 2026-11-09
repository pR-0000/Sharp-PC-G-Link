; Original single-run ROM backup agent. MIT, (c) 2026 P.RAIMBAULT.
; FR: MON USER0AFF, R, charger l'agent, armer le PC, G100 une seule fois.
; EN: MON USER0AFF, R, upload agent, arm PC receiver, run G100 once.
; Native serial IOCS: BCE8=open, BCEB=close, BFAF=TX, BCE2=RX.
; No LCD/power/RAM-bank writes. ROM mapping restored BEFORE serial calls.
    ORG $0100
entry:
    push af
    push bc
    push de
    push hl
    push ix
    push iy
    ex af,af'
    push af
    ex af,af'
    exx
    push bc
    push de
    push hl
    exx
    ld a,i
    push af
    di
    ; Reject an unsupported native table before doing any I/O writes.
    ld hl,$BCE8
    call check_jump
    jp nz,restore_cpu
    ld hl,$BCEB
    call check_jump
    jp nz,restore_cpu
    ld hl,$BFAF
    call check_jump
    jp nz,restore_cpu
    ld hl,$BCE2
    call check_jump
    jp nz,restore_cpu
    ld a,(config_banks)
    or a
    jp z,restore_cpu
    cp 33
    jp nc,restore_cpu
    ld a,(config_reads)
    dec a
    cp 2
    jp nc,restore_cpu
    ld a,(config_port)
    cp $19
    jr z,.low_port
    cp $69
    jp nz,restore_cpu
    jr .valid
.low_port:
    ld a,(config_banks)
    cp 17
    jp nc,restore_cpu
.valid:
    in a,($19)
    ld (saved19),a
    ld a,(config_port)
    cp $69
    jr nz,.save_io
    in a,($69)
    ld (saved69),a
.save_io:
    in a,($15)
    ld (saved15),a
    in a,($18)
    ld (saved18),a
    call $BCE8
    ld hl,(config_start)
    ld (current_job),hl
    ld a,(config_banks)
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl                    ; 32 chunks per 16 KiB bank
    ld de,33                     ; vectors + 32 fixed chunks
    add hl,de
    ld (total_jobs),hl
.job:
    in a,($1F)
    bit 7,a
    jp nz,cleanup
    ld hl,(current_job)
    ld de,(total_jobs)
    or a
    sbc hl,de
    jr z,.end
    jp nc,cleanup
    ld a,1
    ld (capture_id),a
.read:
    call copy_job
    call build_header
    call send_frame
    jp c,cleanup
    ld a,(capture_id)
    inc a
    ld (capture_id),a
    ld b,a
    ld a,(config_reads)
    cp b
    jr nc,.read                   ; independent physical read, not resend
    ld hl,(current_job)
    inc hl
    ld (current_job),hl
    jr .job
.end:
    call clear_payload
    xor a
    ld (capture_id),a
    ld hl,0
    ld (payload_size),hl
    ld (source_address),hl
    ld a,$FF
    ld (source_bank),a
    call build_header
    call send_frame               ; capture=0, index=total, size=0 is END
cleanup:
    call restore_bank
    call $BCEB
    ld a,(saved18)
    out ($18),a
    ld a,(saved15)
    out ($15),a
restore_cpu:
    pop af                        ; IFF2 saved in P/V
    jp po,.disabled
    call pop_registers
    ei
    ret
.disabled:
    call pop_registers
    ret
; The return address of this helper sits above the saved register stack.
pop_registers:
    pop hl
    ld (return_helper),hl
    exx
    pop hl
    pop de
    pop bc
    exx
    ex af,af'
    pop af
    ex af,af'
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    jp return_helper_jump
return_helper_jump:
    jp 0
return_helper EQU return_helper_jump+1

check_jump:
    ld a,(hl)
    cp $C3
    ret

copy_job:
    ld hl,(current_job)
    ld a,h
    or l
    ld bc,64
    ld a,$FF
    ld (source_bank),a
    jr z,.copy
    dec hl
    ld a,h
    or a
    jr nz,.bank
    ld a,l
    cp 32
    jr nc,.bank
    ld h,a
    ld l,0
    add hl,hl
    ld de,$8000
    add hl,de
    jr .page
.bank:
    ld de,32
    or a
    sbc hl,de
    ld a,l
    and 31
    ld (page_index),a
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    srl h
    rr l
    ld a,l
    ld (source_bank),a
    ld b,a
    ld a,(config_port)
    cp $69
    ld a,b
    jr z,.extended
    ld a,(saved19)
    and $F0
    or b
    out ($19),a
    jr .mapped
.extended:
    out ($69),a
.mapped:
    ld a,(page_index)
    ld h,a
    ld l,0
    add hl,hl
    ld de,$C000
    add hl,de
.page:
    ld bc,512
.copy:
    ld (source_address),hl
    ld (payload_size),bc
    push hl
    push bc
    call clear_payload
    pop bc
    pop hl
    ld de,payload
    ldir
restore_bank:
    ld a,(saved19)
    out ($19),a
    ld a,(config_port)
    cp $69
    ret nz
    ld a,(saved69)
    out ($69),a
    ret

clear_payload:
    ld hl,payload
    ld de,payload+1
    ld bc,511
    ld (hl),0
    ldir
    ret

build_header:
    ld hl,magic
    ld de,packet
    ld bc,4
    ldir
    ld hl,config_tag
    ld bc,16
    ldir
    ld hl,(current_job)
    ld (packet+20),hl
    ld a,(source_bank)
    ld (packet+22),a
    ld a,(saved19)
    ld (packet+23),a
    ld a,(capture_id)
    ld (packet+24),a
    ld a,(config_banks)
    ld (packet+25),a
    ld hl,(source_address)
    ld (packet+26),hl
    ld hl,(payload_size)
    ld (packet+28),hl
    ld bc,542                     ; fixed-size header + padded 512-byte data
    ld (frame_size),bc
    ld hl,packet
    call crc16
    ld (hl),e
    inc hl
    ld (hl),d
    ret

send_frame:
    ld a,5
    ld (retries),a
.again:
    ld hl,packet
    ld bc,(frame_size)
    inc bc
    inc bc
.byte:
    ld a,(hl)
    push bc
    push hl
    push ix
    push iy
    call $BFAF
    pop iy
    pop ix
    pop hl
    pop bc
    ret c
    inc hl
    dec bc
    ld a,b
    or c
    jr nz,.byte
    call $BCE2                    ; raises RS: PC may now send ACK/NAK
    ret c
    cp $06
    ret z                         ; ACK also clears carry
    cp $15
    jr nz,.abort                  ; CAN or unknown response
    ld a,(retries)
    dec a
    ld (retries),a
    jr nz,.again
.abort:
    scf
    ret

; HL=bytes, BC=length -> DE=CRC16, HL immediately after covered bytes.
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

magic: db "PRD2"
saved19: db 0
saved69: db 0
saved15: db 0
saved18: db 0
current_job: dw 0
total_jobs: dw 0
capture_id: db 0
source_bank: db 0
source_address: dw 0
payload_size: dw 0
frame_size: dw 0
page_index: db 0
retries: db 0
config_magic: db "PCGSTR02"
config_banks: db 5
config_port: db $19
config_reads: db 2
config_start: dw 0
config_tag: ds 16,0
image_end:
packet EQU $0800
payload EQU packet+30
reserve_end EQU $0AFF
    ASSERT image_end <= packet
    ASSERT payload+512+2 <= reserve_end+1
