"""Optional Z80 CPU checks; requires z80==1.2.0, never a Sharp ROM."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest

import z80

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sharp_link.protocol import prepare,prepare_binary

FOLDER=ROOT/'examples/pc-g850/assembler'


class G850ExamplesTests(unittest.TestCase):
    def machine(self,name):
        cpu=z80.Z80Machine()
        cpu.memory[:]=bytes([0xA5])*65536
        binary=(FOLDER/(name+'.bin')).read_bytes()
        cpu.memory[0x100:0x100+len(binary)]=binary
        cpu.pc=0x100;cpu.sp=0x7E00
        cpu.memory[0x7E00:0x7E02]=bytes([0,0x70])
        for field,value in [('af',0x1234),('bc',0x5678),('de',0x9ABC),('hl',0x1357),('ix',0x2468),('iy',0x369C)]:
            setattr(cpu,field,value)
        for address in (0x7000,0xBFD0,0xBCFD):cpu.set_breakpoint(address)
        cpu.set_input_callback(lambda port:self.fail('Unexpected port input'))
        cpu.set_output_callback(lambda port,value:self.fail('Unexpected port output'))
        return cpu

    def run_machine(self,cpu):
        bands=[];waits=0
        for _ in range(100):
            cpu.ticks_to_stop=20000
            cpu.run()
            if cpu.pc==0x7000:return bands,waits
            if cpu.pc in (0xBFD0,0xBCFD):
                if cpu.pc==0xBFD0:
                    bands.append((cpu.d,cpu.e,bytes(cpu.memory[cpu.hl:cpu.hl+cpu.b])))
                else:waits+=1
                address=cpu.memory[cpu.sp]+256*cpu.memory[cpu.sp+1]
                cpu.sp+=2;cpu.pc=address
                for name in ('af','bc','de','hl','ix','iy'):setattr(cpu,name,0xCCCC)
        self.fail('CPU did not return to its caller')

    def test_signature_writes_only_its_reserved_result_and_returns(self):
        cpu=self.machine('g850_signature')
        before=bytes(cpu.memory)
        bands,waits=self.run_machine(cpu)
        self.assertEqual((bands,waits),([],0))
        self.assertEqual(bytes(cpu.memory[0x180:0x184]),b'G850')
        self.assertEqual(cpu.sp,0x7E02)
        self.assertEqual(bytes(cpu.memory[:0x180]),before[:0x180])
        self.assertEqual(bytes(cpu.memory[0x184:]),before[0x184:])

    def test_lcd_covers_all_six_rows_preserves_registers_and_uses_reserved_buffer(self):
        cpu=self.machine('g850_lcd')
        regs={name:getattr(cpu,name) for name in ('af','bc','de','hl','ix','iy')}
        before=bytes(cpu.memory)
        bands,waits=self.run_machine(cpu)
        expected=[(row,0,bytes([pattern])*144) for row,pattern in enumerate((255,0,170,85,240,15))]
        self.assertEqual(bands,expected)
        self.assertEqual(waits,1)
        self.assertEqual(cpu.sp,0x7E02)
        self.assertEqual({name:getattr(cpu,name) for name in regs},regs)
        self.assertEqual(bytes(cpu.memory[:0x200]),before[:0x200])
        self.assertEqual(bytes(cpu.memory[0x290:0x7DD0]),before[0x290:0x7DD0])
        self.assertEqual(bytes(cpu.memory[0x7E00:]),before[0x7E00:])

    def test_shipped_bin_hex_and_manifest_are_identical_for_all_g850_profiles(self):
        manifest=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
        for name,info in manifest['programs'].items():
            binary=(FOLDER/(name+'.bin')).read_bytes()
            text=(FOLDER/(name+'.hex')).read_text(encoding='ascii')
            self.assertEqual(hashlib.sha256(binary).hexdigest(),info['sha256_bin'])
            self.assertEqual(hashlib.sha256((FOLDER/(name+'.hex')).read_bytes()).hexdigest(),info['sha256_hex'])
            for model in manifest['models']:
                a=prepare_binary(binary,0x100,name+'.bin',model=model)
                b=prepare(text,name+'.hex',model=model)
                self.assertEqual(a.wire,b.wire)
                self.assertGreaterEqual(int(info['user_command'][4:],16),a.end)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang',choices=('fr','en'),default='fr')
    parser.parse_args()
    unittest.main(argv=[sys.argv[0]],verbosity=2)
