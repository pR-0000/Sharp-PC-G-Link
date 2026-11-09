"""Single-run native-IOCS ROM backup, framed binary protocol and local sessions.

FR/EN: 512-byte blocks, CRC16, ACK/NAK, independent reads, explicit END.
No serial port is opened on import. Firmware compatibility requires hardware
validation for each model/revision; PC-G805 firmware support does not imply
compatibility with every firmware revision or the other selectable profiles.
"""
from __future__ import annotations

import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import time
import uuid

from .protocol import MODELS
from .romdump import RomError, require, template_folder, encode_hex
from .transport import Cancelled, check_cancel, drain, open_port

HEADER = struct.Struct('<4s16sHBBBBHH')
MAGIC = b'PRD2'
ACK, NAK, CAN = 6, 21, 24
BLOCK = 512
WIRE_SIZE = HEADER.size+BLOCK+2


@dataclass(frozen=True)
class StreamJob:
    index: int
    bank: int
    source: int
    size: int


def profile(model):
    require(model in MODELS,'Modèle non pris en charge.','Unsupported model.')
    extended = model.startswith('PC-G850')
    return {'bank_port': 0x69 if extended else 0x19,
            'default_banks': 32 if extended else (5 if model in ('PC-G801','PC-E200') else 16),
            'maximum_banks': 32 if extended else 16,
            'hardware_tested': model == 'PC-G805'}


def stream_jobs(count, bank_port=0x19):
    require(bank_port in (0x19,0x69) and 1 <= count <= (32 if bank_port==0x69 else 16),
            'Plan de banques invalide.','Invalid bank plan.')
    return ([StreamJob(0,255,0,64)] +
            [StreamJob(i+1,255,0x8000+i*BLOCK,BLOCK) for i in range(32)] +
            [StreamJob(33+bank*32+page,bank,0xc000+page*BLOCK,BLOCK)
             for bank in range(count) for page in range(32)])


def make_stream_agent(count, tag, bank_port=0x19, reads=2, start=0):
    plan = stream_jobs(count,bank_port)
    require(len(tag)==16 and reads in (1,2) and 0 <= start <= len(plan),
            'Configuration agent invalide.','Invalid agent configuration.')
    folder = template_folder()
    info = json.loads((folder/'stream_manifest.json').read_text())
    image = bytearray((folder/'rom_stream.bin').read_bytes())
    require(hashlib.sha256(image).hexdigest()==info['sha256'],
            'Agent corrompu : réinstaller.','Corrupted agent: reinstall.')
    offsets=info['offsets']
    require(image[offsets['config_magic']:offsets['config_magic']+8]==b'PCGSTR02',
            'Signature agent incorrecte.','Invalid agent signature.')
    for key,value in (('config_banks',count),('config_port',bank_port),('config_reads',reads)):
        image[offsets[key]]=value
    image[offsets['config_start']:offsets['config_start']+2]=start.to_bytes(2,'little')
    image[offsets['config_tag']:offsets['config_tag']+16]=tag
    return bytes(image)


def frame_bytes(job, tag, count, capture=1, payload=b'', saved=3):
    """Reference encoder used by CPU/protocol tests, never a fake ROM source."""
    header=HEADER.pack(MAGIC,tag,job.index,job.bank,saved,capture,count,job.source,len(payload))
    require(len(payload)<=BLOCK,'Bloc trop long.','Block too long.')
    body=header+payload+bytes(BLOCK-len(payload))
    return body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')


def parse_frame(raw, tag, plan, count, reads):
    require(len(raw)==WIRE_SIZE,'Trame ROM tronquée.','Truncated ROM frame.')
    magic,nonce,index,bank,saved,capture,banks,source,size=HEADER.unpack(raw[:HEADER.size])
    require(magic==MAGIC and size<=BLOCK,
            'Longueur de trame ROM invalide.','Invalid ROM frame length.')
    require(binascii.crc_hqx(raw[:-2],0xffff)==int.from_bytes(raw[-2:],'little'),
            'CRC ROM incorrect.','ROM CRC mismatch.')
    require(nonce==tag and banks==count,'Agent d’une autre session : recharger le bon agent.',
            'Agent belongs to another session: reload the correct agent.')
    require(not any(raw[HEADER.size+size:-2]),'Remplissage de trame invalide.','Invalid frame padding.')
    if capture==0:
        require((index,bank,source,size)==(len(plan),255,0,0),
                'Fin de sauvegarde incohérente.','Inconsistent backup end frame.')
        return None,b'',{'saved_bank_port':saved,'capture_id':0}
    require(index<len(plan) and 1<=capture<=reads,'Numéro de bloc/lecture invalide.','Invalid block/read number.')
    job=plan[index]
    require((bank,source,size)==(job.bank,job.source,job.size),
            'Banque ou adresse incohérente.','Inconsistent bank or address.')
    return job,raw[HEADER.size:HEADER.size+size],{'saved_bank_port':saved,'capture_id':capture}


class StreamSession:
    def __init__(self,path):
        self.path=Path(path)
        self.info=json.loads((self.path/'session.json').read_text(encoding='utf-8'))
        require(self.info.get('version')==2,'Session manuelle : utiliser « Ancien mode manuel ».','Manual session: use “Older manual mode”.')
        self.model=self.info['model'];self.bank_count=self.info['bank_count'];self.tag=bytes.fromhex(self.info['tag'])
        expected=profile(self.model)
        require(self.info['bank_port']==expected['bank_port'] and len(self.tag)==16 and self.info['required_reads'] in (1,2),
                'Session invalide.','Invalid session.')
        self.plan=stream_jobs(self.bank_count,self.info['bank_port'])
        for key,record in self.info['blocks'].items():
            index=int(key)
            require(0<=index<len(self.plan),'Index de bloc invalide.','Invalid block index.')
            data=self.chunk_file(index).read_bytes()
            require(len(data)==self.plan[index].size and hashlib.sha256(data).hexdigest()==record['sha256'],
                    'Un bloc local a été modifié.','A local block was modified.')
            require(set(record['capture_ids']).issubset(set(range(1,self.info['required_reads']+1))) and
                    len(record['capture_ids'])==len(set(record['capture_ids'])) and record['reads']==len(record['capture_ids']),
                    'Historique de lectures invalide.','Invalid read history.')

    @classmethod
    def create(cls,path,model,count=None,reads=2):
        settings=profile(model);count=settings['default_banks'] if count is None else count
        stream_jobs(count,settings['bank_port'])
        require(reads in (1,2),'Choisir une ou deux lectures.','Choose one or two reads.')
        path=Path(path)
        require(not path.exists() or not any(path.iterdir()),'Choisir un dossier vide.','Choose an empty folder.')
        path.mkdir(parents=True,exist_ok=True)
        for name in ('chunks','captures'):(path/name).mkdir()
        info={'version':2,'model':model,'bank_count':count,'bank_port':settings['bank_port'],
              'tag':uuid.uuid4().hex,'required_reads':reads,'blocks':{},'complete':False,
              'hardware_tested':settings['hardware_tested'],'created_utc':datetime.now(timezone.utc).isoformat()}
        (path/'session.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
        result=cls(path);result.write_agent();return result

    def chunk_file(self,index):return self.path/'chunks'/f'{index:04d}.bin'

    def pending(self):
        return next((j for j in self.plan if self.info['blocks'].get(str(j.index),{}).get('reads',0)<self.info['required_reads']),None)

    def write_agent(self):
        job=self.pending();start=job.index if job is not None else len(self.plan)
        data=make_stream_agent(self.bank_count,self.tag,self.info['bank_port'],self.info['required_reads'],start)
        path=self.path/'agent-auto.hex';path.write_text(encode_hex(data,0x100),encoding='ascii');return path

    def save(self):
        temporary=self.path/'session.json.tmp'
        temporary.write_text(json.dumps(self.info,indent=2)+'\n',encoding='utf-8');temporary.replace(self.path/'session.json')

    def accept(self,raw):
        job,data,details=parse_frame(raw,self.tag,self.plan,self.bank_count,self.info['required_reads'])
        if job is None:
            require(self.pending() is None,'Il manque des blocs : reprendre la session.','Missing blocks: resume the session.')
            (self.path/'captures/end.prd').write_bytes(raw)
            self.assemble()
            self.info['complete']=True;self.save();return None
        key=str(job.index);digest=hashlib.sha256(data).hexdigest();record=self.info['blocks'].get(key)
        capture=self.path/'captures'/f'{job.index:04d}-r{details["capture_id"]}.prd'
        if capture.exists() and capture.read_bytes()!=raw:
            (self.path/'captures'/f'conflict-{uuid.uuid4().hex[:10]}.prd').write_bytes(raw)
        elif not capture.exists():capture.write_bytes(raw)
        if record:
            require(digest==record['sha256'],
                    'Lectures ROM différentes : copie précédente conservée. Arrêter puis reprendre.',
                    'ROM reads differ: previous copy retained. Stop and resume.')
        else:
            self.chunk_file(job.index).write_bytes(data)
            record={'sha256':digest,'reads':0,'capture_ids':[],**{'saved_bank_port':details['saved_bank_port']}}
            self.info['blocks'][key]=record
        if details['capture_id'] not in record['capture_ids']:
            record['capture_ids'].append(details['capture_id']);record['reads']=len(record['capture_ids'])
        self.info['complete']=False;self.save();return job

    def assemble(self):
        require(self.pending() is None,'Session incomplète.','Incomplete session.')
        (self.path/'base.bin').write_bytes(self.chunk_file(0).read_bytes())
        fixed=b''.join(self.chunk_file(i).read_bytes() for i in range(1,33))
        (self.path/'fixed.bin').write_bytes(fixed)
        directory=self.path/'banks';directory.mkdir(exist_ok=True)
        hashes={};groups={};uniform=[]
        for bank in range(self.bank_count):
            data=b''.join(self.chunk_file(33+bank*32+p).read_bytes() for p in range(32))
            (directory/f'bank{bank:02x}.bin').write_bytes(data)
            digest=hashlib.sha256(data).hexdigest();hashes[f'{bank:02x}']=digest;groups.setdefault(digest,[]).append(bank)
            if len(set(data))==1:uniform.append(bank)
        same=fixed==(directory/'bank00.bin').read_bytes()
        exported=self.model=='PC-G801' and same and self.bank_count>=5
        if exported:
            out=self.path/'g800';out.mkdir(exist_ok=True)
            (out/'base.bin').write_bytes((self.path/'base.bin').read_bytes())
            for bank in range(self.bank_count):(out/f'rom{bank:02x}.bin').write_bytes((directory/f'bank{bank:02x}.bin').read_bytes())
        report={'model':self.model,'protocol':'PRD2','sampled_bank_selectors':self.bank_count,
                'bank_port':f'{self.info["bank_port"]:02X}','required_reads':self.info['required_reads'],
                'all_blocks_verified':True,'explicit_end_received':True,'bank_sha256':hashes,
                'fixed_matches_bank00':same,'equal_bank_groups':[x for x in groups.values() if len(x)>1],
                'uniform_banks':uniform,'g800_export_created':exported,'physical_rom_size_proven':False,
                'native_iocs_hardware_profile_verified':profile(self.model)['hardware_tested'],
                'hardware_validation_scope':'PC-G805 only; compatibility depends on firmware revision.'}
        (self.path/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def receive_stream(settings,cancel,notify,session,factory=open_port):
    """One open port, receive/verify/persist then ACK; NAK corrupted frames.

    BREAK on Sharp remains necessary if the PC/cable disappears while native
    IOCS waits for CS or an ACK. No incomplete dump is reported as complete.
    """
    check_cancel(cancel)
    require((settings.baud,settings.data_bits,settings.parity,settings.stop_bits)==(4800,8,'N',1),
            'Le dumper automatique utilise 4800 / 8N1.','Automatic backup uses 4800 / 8N1.')
    with factory(settings) as port:
        last=time.monotonic();received=False;bad=0

        def read_exact(size):
            nonlocal last,received
            data=bytearray()
            while len(data)<size:
                check_cancel(cancel)
                chunk=port.read(size-len(data))
                if chunk:data.extend(chunk);last=time.monotonic();received=True
                elif time.monotonic()-last>(settings.idle_timeout if received else settings.receive_timeout):
                    raise RomError('Délai dépassé. Vérifier 4800/8N1, G100 et le profil ; BREAK sur le Sharp puis Reprendre.',
                                   'Timeout. Check 4800/8N1, G100 and the profile; press BREAK on Sharp, then Resume.')
            return bytes(data)

        def control(value):
            start=time.monotonic()
            while not port.cts:
                check_cancel(cancel)
                if time.monotonic()-start>settings.stall_timeout:
                    raise RomError('Le Sharp ne demande pas l’acquittement (CTS). BREAK puis Reprendre.',
                                   'Sharp is not requesting acknowledgement (CTS). BREAK, then Resume.')
                cancel.wait(0.01)
            require(port.write(bytes([value]))==1,'Acquittement incomplet.','Incomplete acknowledgement.')

        notify('armed',str(session.path))
        while True:
            # Fixed wire length means even a corrupted magic/length field can
            # be NAKed without waiting for bytes from a nonexistent longer frame.
            raw=read_exact(WIRE_SIZE)
            crc_ok=binascii.crc_hqx(raw[:-2],0xffff)==int.from_bytes(raw[-2:],'little')
            if not crc_ok:
                (session.path/'captures'/f'rejected-{uuid.uuid4().hex[:10]}.prd').write_bytes(raw)
                bad+=1;notify('retry',bad)
                require(bad<5,'Trop d’erreurs CRC : BREAK puis Reprendre.','Too many CRC errors: BREAK, then Resume.')
                control(NAK);continue
            try:job=session.accept(raw)
            except RomError:
                control(CAN)
                raise
            control(ACK);bad=0
            if job is None:
                drain(port,settings,cancel)  # deliver final ACK before closing FTDI
                notify('complete',str(session.path));return session.path
            record=session.info['blocks'][str(job.index)]
            notify('block',{'index':job.index,'bank':job.bank,'source':job.source,'reads':record['reads'],
                            'verified_reads':sum(x['reads'] for x in session.info['blocks'].values()),
                            'total_reads':len(session.plan)*session.info['required_reads']})
