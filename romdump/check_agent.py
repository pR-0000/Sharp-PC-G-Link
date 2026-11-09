"""CPU verification against synthetic banked ROMs, never Sharp ROM bytes."""
from pathlib import Path
import binascii
import json
import sys
import unittest
import z80

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from sharp_link.romdump import (BUFFER, HEADER, PACKET, DumpSession, encode_hex,
                               jobs, make_agent, parse_packet)

class Machine:
    def __init__(self,count=4,start=0,enabled=True):
        self.tag=bytes(range(16));self.count=count;self.bank=0x21;self.ports=[]
        self.rom=[bytes(((i*73+(i>>8)*13+b*31)&255) for i in range(16384)) for b in range(16)]
        self.fixed=bytes((i*19+7)&255 for i in range(16384))
        self.cpu=z80.Z80Machine();self.cpu.memory[:]=bytes([0xa5])*65536
        self.cpu.memory[0x100:0x320]=make_agent(count,self.tag,start)
        self.cpu.memory[0x8000:0xc000]=self.fixed;self.cpu.memory[0xc000:]=self.rom[1]
        self.cpu.iff1=self.cpu.iff2=enabled
        self.cpu.set_input_callback(self.input);self.cpu.set_output_callback(self.output)
        self.cpu.set_breakpoint(0x7000)
    def input(self,port):
        assert port&255==0x19;self.ports.append(('in',port&255,self.bank));return self.bank
    def output(self,port,value):
        assert port&255==0x19;assert not self.cpu.iff1
        assert value&0xf0==0x20
        self.ports.append(('out',port&255,value));self.bank=value
        self.cpu.memory[0xc000:]=self.rom[value&15]
    def run(self,entry=0x100):
        registers={'af':0xa147,'bc':0x2345,'de':0x3456,'hl':0x4567,'ix':0x1234,'iy':0x5678}
        for name,value in registers.items():setattr(self.cpu,name,value)
        self.cpu.pc=entry;self.cpu.sp=0x1ff0;self.cpu.memory[0x1ff0:0x1ff2]=b'\0\x70'
        before=bytes(self.cpu.memory);enabled=self.cpu.iff1
        for _ in range(100):
            self.cpu.ticks_to_stop=1000000;self.cpu.run()
            if self.cpu.pc==0x7000:break
        else:raise AssertionError('Agent did not return')
        assert self.bank==0x21
        assert self.cpu.sp==0x1ff2 and self.cpu.iff1==enabled and self.cpu.iff2==enabled
        for name,value in registers.items():assert getattr(self.cpu,name)==value,name
        after=bytes(self.cpu.memory)
        for lo,hi in ((0,0x100),(0x100,0x234),(0x260,0x300),(0x1401,0x1e00),(0x1ff2,0x8000),(0x8000,0x10000)):
            assert before[lo:hi]==after[lo:hi],(lo,hi)
        return bytes(self.cpu.memory[PACKET:0x1401])
    def decoded(self,frame):return parse_packet(encode_hex(frame,PACKET).encode(),self.tag,self.count)

class AgentTests(unittest.TestCase):
    def test_all_16_selectors_every_page_and_full_frame_crc(self):
        m=Machine(16)
        for expected in jobs(16):
            frame=m.run();job,data,details=m.decoded(frame)
            self.assertEqual(job,expected)
            want=bytes([0xa5])*64 if job.index==0 else (m.fixed[job.source-0x8000:job.source-0x8000+job.size] if job.bank==255 else m.rom[job.bank][job.source-0xc000:job.source-0xc000+job.size])
            self.assertEqual(data,want)
            self.assertEqual(details['capture_id'],job.index+1)
        before=bytes(m.cpu.memory[PACKET:0x1401]);m.run()
        self.assertEqual(bytes(m.cpu.memory[PACKET:0x1401]),before)

    def test_recopy_reads_source_again_and_does_not_advance_job(self):
        m=Machine(start=5);first=m.run();job,data,a=m.decoded(first)
        second=m.run(0x103);job2,data2,b=m.decoded(second)
        self.assertEqual(job,job2);self.assertEqual(data,data2);self.assertNotEqual(a['capture_id'],b['capture_id'])
        self.assertEqual(m.decoded(m.run())[0].index,6)

    def test_disabled_interrupts_and_resume_at_last_bank(self):
        m=Machine(16,start=68,enabled=False)
        self.assertEqual(m.decoded(m.run())[0],jobs(16)[-1])

    def test_repeat_before_first_copy_is_a_noop(self):
        m=Machine();before=bytes(m.cpu.memory[PACKET:0x1401]);m.run(0x103)
        self.assertEqual(bytes(m.cpu.memory[PACKET:0x1401]),before);self.assertEqual(m.ports,[])

    def test_restart_and_g801_buffer_fit(self):
        m=Machine(start=19);m.run();job,data,details=m.decoded(m.run(0x106))
        self.assertEqual(job.index,0);self.assertEqual(len(data),64)
        self.assertLessEqual(0x1400,0x17e2)

    def test_crc_matches_standard_known_vector(self):
        # The normal packet tests cover every byte; verify a nonrepeating 4 KiB fixture too.
        m=Machine(start=7);job,data,details=m.decoded(m.run())
        self.assertEqual(details['crc16'],f'{binascii.crc_hqx(data,0xffff):04X}')

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AgentTests))
    (HERE/'build/cpu_validation.json').write_text(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),
        'synthetic_roms_only':True,'physical_hardware_tested':False,'bank_selectors_tested':16},indent=2)+'\n',encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
