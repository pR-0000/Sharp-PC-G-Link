"""Optional private G805 ROM test; actual UART TX/RX instructions execute.

Only the IOCS JP dispatch is followed directly at TX entry to observe its
returned waveform; no serial routine or CRC computation is mocked.
"""
from pathlib import Path
import hashlib
import unittest
import z80

from sharp_link.romstream import ACK,CAN,HEADER,WIRE_SIZE,make_stream_agent,parse_frame,stream_jobs

ROM_DIR=None


class NativeStreamMachine:
    RETURN=0x70
    def __init__(self,start=0,stop_first=False,brk=False,enabled=True):
        self.banks=[(ROM_DIR/f'banks/bank{i:02x}.bin').read_bytes() for i in range(4)]
        self.fixed=(ROM_DIR/'fixed.bin').read_bytes()
        assert hashlib.sha256(self.fixed).hexdigest()=='ad26e4b417efd2b98e47f60bca495690ab2ff888a81568f31183bd74df790777'
        self.ram=bytearray(8192);self.bank=0xa3;self.ports={0x15:0x41,0x18:2}
        self.tag=bytes(range(16));self.plan=stream_jobs(4);self.stop_first=stop_first;self.brk=brk
        self.frames=[];self.data=bytearray();self.active_tx=False;self.wave=[];self.rx=[];self.bytes=0
        self.cpu=z80.Z80Machine();self.cpu.memory[0x8000:0xc000]=self.fixed
        self.cpu.mark_addrs(0,0x8000,self.cpu.READ_MARK|self.cpu.WRITE_MARK)
        self.cpu.mark_addrs(0xc000,0x4000,self.cpu.READ_MARK)
        self.cpu.mark_addrs(0x8000,0x8000,self.cpu.WRITE_MARK)
        self.cpu.set_read_callback(self.read);self.cpu.set_write_callback(self.write)
        self.cpu.set_input_callback(self.input);self.cpu.set_output_callback(self.output)
        self.cpu.iff1=self.cpu.iff2=enabled
        self.block(0,(ROM_DIR/'base.bin').read_bytes())
        self.block(0x100,make_stream_agent(4,self.tag,start=start))
        for p,v in ((0x78ed,16),(0x78ee,0x82),(0x78ef,26),(0x7900,3)):self.write(p,v)
        self.cpu.set_breakpoint(0xbfaf);self.cpu.set_breakpoint(self.RETURN)

    def read(self,address):
        if address<0x8000:return self.ram[address&0x1fff]
        if address<0xc000:return self.fixed[address-0x8000]
        return self.banks[self.bank&15][address-0xc000]
    def write(self,address,value):
        assert address<0x8000,f'ROM write {address:04X}'
        self.ram[address&0x1fff]=value
    def block(self,address,data):
        for i,v in enumerate(data):self.write(address+i,v)
    def input(self,port):
        p=port&255
        if p==0x19:return self.bank
        if p in (0x15,0x18):return self.ports[p]
        assert p==0x1f,hex(p)
        pc=self.cpu.pc
        if pc==0x8f9f:return 0x80 if self.brk else 2
        if pc==0x8fca:
            answer=CAN if self.stop_first else ACK
            self.rx=[4]+[0 if answer>>i&1 else 4 for i in range(8)]
            return 4
        if pc==0x8fdc:return 4
        if pc==0x8fed:return self.rx.pop(0)
        if pc==0x908d:return 0
        return 2
    def output(self,port,value):
        p=port&255
        assert p in (0x19,0x15,0x18),hex(p)
        if p==0x19:self.bank=value
        else:
            self.ports[p]=value
            if p==0x18 and self.active_tx:self.wave.append(value)
    def run(self):
        c=self.cpu
        regs={name:0x1234+i*17 for i,name in enumerate(('af','bc','de','hl','ix','iy','alt_af','alt_bc','alt_de','alt_hl'))}
        for k,v in regs.items():setattr(c,k,v)
        enabled=c.iff1;c.pc=0x100;c.sp=0x1ef0
        self.block(c.sp,self.RETURN.to_bytes(2,'little'))
        tx_return=None
        for _ in range(30000):
            c.ticks_to_stop=100000;c.run()
            if c.pc==self.RETURN:break
            if c.pc==0xbfaf:
                assert self.bank==0xa3
                self.wanted=c.a;self.wave=[];self.active_tx=True
                tx_return=self.read(c.sp)|self.read(c.sp+1)<<8
                c.set_breakpoint(tx_return)
                assert self.read(0xbfaf)==0xc3
                c.pc=self.read(0xbfb0)|self.read(0xbfb1)<<8
            elif c.pc==tx_return:
                c.clear_breakpoint(tx_return);self.active_tx=False
                if not c.f&1:
                    assert len(self.wave)==10,self.wave
                    assert self.wave[0]==0x82 and self.wave[-1]==2
                    decoded=sum((not (v&0x80))<<i for i,v in enumerate(self.wave[1:-1]))
                    assert decoded==self.wanted
                    self.data.append(decoded);self.bytes+=1
                    if len(self.data)>=HEADER.size:
                        size=HEADER.unpack(self.data[:HEADER.size])[-1]
                        if len(self.data)==WIRE_SIZE:
                            frame=bytes(self.data);self.data.clear()
                            job,payload,details=parse_frame(frame,self.tag,self.plan,4,2)
                            if job:
                                expected=(bytes(self.ram[:64]) if job.index==0 else
                                          self.fixed[job.source-0x8000:job.source-0x8000+job.size] if job.bank==255 else
                                          self.banks[job.bank][job.source-0xc000:job.source-0xc000+job.size])
                                assert payload==expected
                            self.frames.append((job,payload,details))
                tx_return=None
        else:raise AssertionError(f'Native CPU timeout {c.pc:04X}')
        assert c.sp==0x1ef2 and self.bank==0xa3
        assert self.ports=={0x15:0x41,0x18:2}
        assert c.iff1==enabled and c.iff2==enabled
        assert all(getattr(c,k)==v for k,v in regs.items())
        return self.frames


class NativeStreamTests(unittest.TestCase):
    def test_native_transmitter_waveform_and_receiver_can(self):
        m=NativeStreamMachine(stop_first=True)
        frames=m.run();self.assertEqual(len(frames),1)
        self.assertEqual(frames[0][0].index,0)
    def test_native_last_rom_block_two_reads_and_end_ack(self):
        m=NativeStreamMachine(start=len(stream_jobs(4))-1,enabled=False)
        frames=m.run();self.assertEqual(len(frames),3)
        self.assertEqual(frames[0][0].source,0xfe00)
        self.assertEqual([x[2]['capture_id'] for x in frames],[1,2,0])
        self.assertIsNone(frames[-1][0])
    def test_native_break_exits_and_restores_mapping(self):
        self.assertFalse(NativeStreamMachine(brk=True).run())


def native_suite(directory):
    global ROM_DIR
    ROM_DIR=Path(directory)
    return unittest.defaultTestLoader.loadTestsFromTestCase(NativeStreamTests)
