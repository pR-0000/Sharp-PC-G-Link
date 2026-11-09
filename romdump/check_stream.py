"""CPU tests of the one-run agent with synthetic ROMs and mocked native IOCS.

Optional --rom-dir executes real G805 serial routines on selected complete
frames, including RX ACK and BREAK; no Sharp ROM is distributed.
"""
from pathlib import Path
import argparse
import json
import sys
import unittest

import z80

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from sharp_link.romstream import HEADER,ACK,NAK,CAN,make_stream_agent,parse_frame,stream_jobs


class StreamMachine:
    RETURN=0x70
    def __init__(self,count=1,port=0x19,start=0,reads=2,enabled=True):
        self.tag=bytes(range(16));self.count=count;self.port=port;self.reads=reads
        self.cpu=z80.Z80Machine();self.cpu.memory[:]=bytes([0xa5])*65536
        self.bank19=0xa3;self.bank69=19;self.initial19=self.bank19;self.initial69=self.bank69
        self.io={0x15:0x41,0x18:0x02};self.writes=[];self.frames=[];self.partial=bytearray()
        self.responses=lambda index:ACK;self.break_after=None;self.bytes=0
        self.rom=[bytes((i*73+(i>>8)*13+bank*31)&255 for i in range(16384)) for bank in range(32)]
        self.cpu.memory[0x8000:0xc000]=bytes((i*19+7)&255 for i in range(16384))
        for entry in (0xbce8,0xbceb,0xbfaf,0xbce2):
            self.cpu.memory[entry:entry+3]=b'\xc3\x00\x80'
            self.cpu.set_breakpoint(entry)
        self.fixed=bytes(self.cpu.memory[0x8000:0xc000])
        self.cpu.memory[0xc000:]=self.rom[self.bank69 if port==0x69 else self.bank19&15]
        binary=make_stream_agent(count,self.tag,port,reads,start)
        self.cpu.memory[0x100:0x100+len(binary)]=binary
        self.cpu.iff1=self.cpu.iff2=enabled
        self.cpu.set_input_callback(self.input);self.cpu.set_output_callback(self.output)
        self.cpu.set_breakpoint(self.RETURN)

    def input(self,port):
        p=port&255
        if p==0x19:return self.bank19
        if p==0x69:return self.bank69
        if p==0x1f:return 0
        assert p in self.io,p
        return self.io[p]

    def output(self,port,value):
        p=port&255;self.writes.append((p,value))
        assert not self.cpu.iff1
        assert p in (0x19,0x69,0x15,0x18),hex(p)
        if p==0x19:
            assert value&0xf0==self.initial19&0xf0
            self.bank19=value;self.bank69=value&15
            self.cpu.memory[0xc000:]=self.rom[value&15]
        elif p==0x69:
            assert self.port==0x69
            self.bank69=value;self.bank19=(self.bank19&0xf0)|(value&15)
            self.cpu.memory[0xc000:]=self.rom[value]
        else:self.io[p]=value

    def ret(self):
        c=self.cpu;c.pc=int.from_bytes(c.memory[c.sp:c.sp+2],'little');c.sp+=2

    def native(self):
        c=self.cpu;entry=c.pc;value=c.a
        assert self.bank19==self.initial19
        if self.port==0x69:assert self.bank69==self.initial69
        carry=False;answer=0
        if entry==0xbfaf:
            self.bytes+=1
            if self.break_after is not None and self.bytes>=self.break_after:carry=True
            else:self.partial.append(value)
        elif entry==0xbce2:
            raw=bytes(self.partial);self.partial.clear()
            job,data,details=parse_frame(raw,self.tag,stream_jobs(self.count,self.port),self.count,self.reads)
            if job is not None:
                expected=(bytes([0xa5])*64 if job.index==0 else
                          self.fixed[job.source-0x8000:job.source-0x8000+job.size] if job.bank==255 else
                          self.rom[job.bank][job.source-0xc000:job.source-0xc000+job.size])
                assert data==expected,(job,data[:16],expected[:16])
            self.frames.append((job,data,details,raw));answer=self.responses(len(self.frames))
        # Deliberately destroy more registers than the observed ROM does.
        for reg in ('bc','de','hl','ix','iy','alt_bc','alt_de','alt_hl','alt_af'):setattr(c,reg,0xdead)
        c.af=(answer<<8)|int(carry)
        self.ret()

    def run(self):
        c=self.cpu
        registers={name:(0x1234+i*0x111)&65535 for i,name in enumerate(
            ('af','bc','de','hl','ix','iy','alt_af','alt_bc','alt_de','alt_hl'))}
        for name,value in registers.items():setattr(c,name,value)
        c.pc=0x100;c.sp=0x1ef0;c.memory[c.sp:c.sp+2]=self.RETURN.to_bytes(2,'little')
        enabled=c.iff1
        for _ in range(2000000):
            c.ticks_to_stop=1000000;c.run()
            if c.pc==self.RETURN:break
            if c.pc in (0xbce8,0xbceb,0xbfaf,0xbce2):self.native()
        else:raise AssertionError(f'CPU timeout {c.pc:04X}')
        assert c.sp==0x1ef2
        assert c.iff1==enabled and c.iff2==enabled
        assert all(getattr(c,key)==value for key,value in registers.items())
        assert self.bank19==self.initial19
        if self.port==0x69:assert self.bank69==self.initial69
        assert self.io=={0x15:0x41,0x18:0x02}
        return self.frames


class StreamAgentTests(unittest.TestCase):
    def test_complete_run_automatically_sends_two_independent_reads_and_end(self):
        m=StreamMachine();frames=m.run();plan=stream_jobs(1)
        self.assertEqual(len(frames),len(plan)*2+1)
        for index,job in enumerate(plan):
            self.assertEqual(frames[index*2][0],job)
            self.assertEqual(frames[index*2+1][0],job)
            self.assertEqual([x[2]['capture_id'] for x in frames[index*2:index*2+2]],[1,2])
        self.assertIsNone(frames[-1][0])

    def test_all_32_extended_banks_can_be_selected_without_low_nibble_truncation(self):
        # Sample every bank's last page; run from its first outstanding job and
        # cancel after the first frame to keep this test independent of earlier jobs.
        for bank in range(32):
            with self.subTest(bank=bank):
                m=StreamMachine(32,0x69,start=33+bank*32+31,reads=1)
                m.responses=lambda index:CAN
                self.assertEqual(m.run()[0][0].bank,bank)
                self.assertIn((0x69,bank),m.writes)

    def test_resume_last_block_and_disabled_interrupts(self):
        m=StreamMachine(5,start=len(stream_jobs(5))-1,enabled=False)
        frames=m.run();self.assertEqual(len(frames),3)
        self.assertEqual(frames[0][0].source,0xfe00)
        self.assertEqual(frames[0][0].bank,4)
        self.assertIsNone(frames[-1][0])

    def test_nak_retransmits_identical_frame_without_counting_another_read(self):
        m=StreamMachine(1,start=len(stream_jobs(1))-1)
        m.responses=lambda index:NAK if index==1 else ACK
        frames=m.run();self.assertEqual(len(frames),4)
        self.assertEqual(frames[0][3],frames[1][3])
        self.assertEqual(frames[2][2]['capture_id'],2)

    def test_five_naks_abort_without_end(self):
        m=StreamMachine();m.responses=lambda index:NAK
        self.assertEqual(len(m.run()),5)
        self.assertTrue(all(x[0] is not None for x in m.frames))

    def test_break_during_transmission_returns_without_marking_success(self):
        m=StreamMachine();m.break_after=17
        self.assertFalse(m.run())

    def test_unsupported_native_table_returns_without_io_writes(self):
        m=StreamMachine();m.cpu.memory[0xbfaf]=0xff
        self.assertFalse(m.run());self.assertFalse(m.writes)

    def test_completed_resume_still_sends_explicit_end(self):
        m=StreamMachine(start=len(stream_jobs(1)))
        self.assertIsNone(m.run()[0][0])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rom-dir',type=Path)
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StreamAgentTests)
    if args.rom_dir:
        from check_stream_native import native_suite
        suite.addTests(native_suite(args.rom_dir))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (HERE/'build/stream_cpu_validation.json').write_text(json.dumps(
        {'tests':result.testsRun,'passed':result.wasSuccessful(),'physical_hardware_tested':False,
         'native_serial_checked':bool(args.rom_dir),'bank69_selectors_tested':32},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())


if __name__=='__main__':main()
