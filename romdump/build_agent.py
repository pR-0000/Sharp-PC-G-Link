"""FR: construire l'agent ROM. EN: build the ROM staging agent. Stdlib only."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent

def ihex(data,start=0x100):
    lines=[]
    for offset in range(0,len(data),16):
        chunk=data[offset:offset+16];a=start+offset
        body=bytes((len(chunk),a>>8,a&255,0))+chunk
        lines.append(':'+(body+bytes((-sum(body)&255,))).hex().upper())
    return '\n'.join(lines+[':00000001FF'])+'\n'

def main():
    parser=argparse.ArgumentParser(description='Construire / Build ROM agent')
    parser.add_argument('--assembler',default=os.environ.get('SJASMPLUS','sjasmplus'))
    args=parser.parse_args();assembler=shutil.which(args.assembler)
    if not assembler:parser.error('SjASMPlus: --assembler / SJASMPLUS / PATH')
    out=HERE/'build';out.mkdir(exist_ok=True);base=out/'rom_dump'
    subprocess.run([assembler,'--nologo','--color=off',f'--raw={base.as_posix()}.bin',f'--sym={base.as_posix()}.sym',f'--lst={base.as_posix()}.lst',(HERE/'rom_dump.asm').as_posix()],cwd=HERE,check=True)
    data=base.with_suffix('.bin').read_bytes();assert len(data)==0x220
    base.with_suffix('.hex').write_text(ihex(data),encoding='ascii')
    info={'version':'0.1.0','bytes':len(data),'origin':'0100','next':'G100','reread':'G103','restart':'G106',
          'reserve':'USER1400','export':'W300,1400','bank_port':'19','sha256':hashlib.sha256(data).hexdigest(),
          'hardware_tested':False,'config_offset':0x1e0,'config_banks_offset':0x1e8,'config_tag_offset':0x1e9,
          'next_job_offset':int(re.search(r'^next_job: EQU 0x([0-9A-Fa-f]+)',base.with_suffix('.sym').read_text(),re.M)[1],16)-0x100}
    (out/'manifest.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    stream=out/'rom_stream'
    subprocess.run([assembler,'--nologo','--color=off',f'--raw={stream.as_posix()}.bin',f'--sym={stream.as_posix()}.sym',f'--lst={stream.as_posix()}.lst',(HERE/'rom_stream.asm').as_posix()],cwd=HERE,check=True)
    binary=stream.with_suffix('.bin').read_bytes()
    symbols={name:int(value,16) for name,value in re.findall(r'^(\w+): EQU 0x([0-9A-Fa-f]+)',stream.with_suffix('.sym').read_text(),re.M)}
    assert len(binary)<=0x700
    stream.with_suffix('.hex').write_text(ihex(binary),encoding='ascii')
    stream_info={'version':'0.2.0','origin':'0100','reserve':'USER0AFF','run':'G100','bytes':len(binary),
                 'sha256':hashlib.sha256(binary).hexdigest(),'hardware_tested':False,
                 'native_serial_entries':['BCE8','BCEB','BFAF','BCE2'],
                 'offsets':{key:symbols[key]-0x100 for key in ('config_magic','config_banks','config_port','config_reads','config_start','config_tag')}}
    # Record support only for the released binary; modified agents need revalidation.
    models=['PC-G805'] if stream_info['sha256']=='0f3f0fb3278a75570b03074754597991ce872ff3ce7c691cc4dbc8e2979a8208' else []
    stream_info.update(hardware_tested=bool(models),hardware_tested_models=models,
                       hardware_validation_scope='PC-G805 only; compatibility depends on firmware revision.' if models else 'Modified agent: hardware compatibility unverified.')
    (out/'stream_manifest.json').write_text(json.dumps(stream_info,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(info,indent=2))
    print(json.dumps(stream_info,indent=2))

if __name__=='__main__':main()
