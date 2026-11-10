"""FR/EN: rebuild the supplied PC-G850 Z80 examples with SjASMPlus."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sharp_link.protocol import intel_record


def main():
    parser=argparse.ArgumentParser(description='Construire les exemples Z80 G850 / Build G850 Z80 examples')
    parser.add_argument('--assembler',default=os.environ.get('SJASMPLUS','sjasmplus'),help='SjASMPlus / PATH / SJASMPLUS')
    parser.add_argument('--lang',choices=('fr','en'),default='fr',help='Langue / Language')
    args=parser.parse_args()
    assembler=shutil.which(args.assembler)
    if not assembler:parser.error('SjASMPlus : --assembler / SJASMPLUS / PATH')
    folder=ROOT/'examples/pc-g850/assembler'
    manifest={'origin':'0100','entry':'0100','models':['PC-G850','PC-G850S','PC-G850V','PC-G850VS'],'programs':{}}
    for name,reserve in [('g850_signature','USER01FF'),('g850_lcd','USER02FF')]:
        base=folder/name
        subprocess.run([assembler,'--nologo','--color=off',f'--raw={base.with_suffix(".bin").as_posix()}',
                        base.with_suffix('.asm').as_posix()],cwd=folder,check=True)
        data=base.with_suffix('.bin').read_bytes()
        text='\n'.join([intel_record(0x100+i,data[i:i+16]) for i in range(0,len(data),16)]+[':00000001FF'])+'\n'
        with base.with_suffix('.hex').open('w',encoding='ascii',newline='\n') as stream:stream.write(text)
        manifest['programs'][name]={'bytes':len(data),'last_address':f'{0xff+len(data):04X}',
            'user_command':reserve,'run_command':'G100',
            'sha256_bin':hashlib.sha256(data).hexdigest(),
            'sha256_hex':hashlib.sha256(base.with_suffix('.hex').read_bytes()).hexdigest()}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Exemples G850 construits.' if args.lang=='fr' else 'G850 examples built.')


if __name__=='__main__':main()
