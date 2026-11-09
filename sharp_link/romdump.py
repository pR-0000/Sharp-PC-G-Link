"""ROM staging protocol and resumable local sessions, no hardware on import.

FR: sauvegarde privee des ROM via le moniteur; EN: private ROM backup via MON.
"""
from __future__ import annotations
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import time
import uuid

from .protocol import intel_record
from .transport import Cancelled, Settings, check_cancel, open_port

MODELS=('PC-G801','PC-G805')
PACKET=0x300
BUFFER=0x400
GUARD=0x1400
HEADER=struct.Struct('<4s16sBBBBHHHBB')

class RomError(ValueError):
    def __init__(self,fr,en):self.fr,self.en=fr,en;super().__init__(en)
    def render(self,language):return self.fr if language=='fr' else self.en

def require(condition,fr,en):
    if not condition:raise RomError(fr,en)

@dataclass(frozen=True)
class Job:
    index:int
    bank:int
    source:int
    size:int

def jobs(bank_count):
    require(1<=bank_count<=16,'Nombre de banques : 1 à 16.','Bank count must be 1..16.')
    return [Job(0,255,0,64)]+[Job(i+1,255,0x8000+i*4096,4096) for i in range(4)]+[
        Job(5+b*4+p,b,0xc000+p*4096,4096) for b in range(bank_count) for p in range(4)]

def encode_hex(data,start):
    return '\n'.join([intel_record(start+i,data[i:i+16]) for i in range(0,len(data),16)]+[':00000001FF'])+'\n'

def decode_hex(raw):
    try:text=raw.decode('ascii')
    except UnicodeError:raise RomError('Réception non ASCII. Vérifier la trame série.','Non-ASCII reception. Check serial framing.') from None
    text=text.rstrip('\r\n\x1a')
    memory={};end=False
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        require(not end,'Données après la fin HEX.','Data after HEX end record.')
        try:
            require(line.startswith(':') and len(line)%2==1,'Ligne HEX invalide.','Invalid HEX line.')
            record=bytes.fromhex(line[1:])
        except ValueError:raise RomError('Ligne HEX invalide.','Invalid HEX line.') from None
        require(len(record)>=5 and len(record)==record[0]+5 and not sum(record)%256,
                'Longueur ou checksum HEX incorrect.','Invalid HEX length or checksum.')
        count,hi,lo,kind=record[:4];address=hi*256+lo
        if kind==1:
            require(count==0 and address==0,'Fin HEX invalide.','Invalid HEX end record.');end=True;continue
        require(kind==0 and count>0 and address+count<=65536,'Type ou adresse HEX invalide.','Invalid HEX type or address.')
        for i,value in enumerate(record[4:-1]):
            require(address+i not in memory,'Adresses HEX superposées.','Overlapping HEX records.')
            memory[address+i]=value
    require(end and bool(memory),'Réception HEX incomplète.','Incomplete HEX reception.')
    return memory

def template_folder():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'romdump/build'

def make_agent(bank_count,tag,start_job=0):
    require(len(tag)==16 and 0<=start_job<len(jobs(bank_count)),'Configuration agent invalide.','Invalid agent configuration.')
    folder=template_folder();info=json.loads((folder/'manifest.json').read_text())
    data=bytearray((folder/'rom_dump.bin').read_bytes())
    require(hashlib.sha256(data).hexdigest()==info['sha256'],'Agent corrompu : reconstruire ou réinstaller.','Corrupted agent: rebuild or reinstall.')
    require(data[info['config_offset']:info['config_offset']+8]==b'PCGDMP01','Signature agent incorrecte.','Invalid agent signature.')
    data[info['config_banks_offset']]=bank_count
    data[info['config_tag_offset']:info['config_tag_offset']+16]=tag
    data[info['next_job_offset']]=start_job
    return bytes(data)

def parse_packet(raw,tag,bank_count):
    memory=decode_hex(raw)
    expected=set(range(PACKET,GUARD))
    require(expected.issubset(memory) and set(memory).issubset(expected|{GUARD}),
            'Bloc tronqué ou mauvaise plage : utiliser W300,1400.','Truncated block or wrong range: use W300,1400.')
    data=bytes(memory[a] for a in range(PACKET,GUARD))
    magic,nonce,index,bank,saved,capture_id,source,size,crc,count,marker=HEADER.unpack(data[:32])
    require(magic==b'PRD1' and marker==0x5a,'En-tête absent ou invalide. Relancer G100.','Missing/invalid header. Run G100 again.')
    require(nonce==tag,'Ce bloc appartient à une autre session.','This block belongs to another session.')
    require(count==bank_count and index<len(jobs(count)),'Plan de banques incohérent.','Inconsistent bank plan.')
    job=jobs(count)[index]
    require((bank,source,size)==(job.bank,job.source,job.size),'Adresse ou banque incohérente.','Inconsistent address or bank.')
    require(not any(data[32:256]),'Zone de garde du paquet modifiée.','Packet guard area was modified.')
    payload=data[256:256+size]
    require(not any(data[256+size:]),'Fin du tampon modifiée.','Buffer tail was modified.')
    require(binascii.crc_hqx(payload,0xffff)==crc,'CRC ROM incorrect : refaire W300,1400.','ROM CRC mismatch: repeat W300,1400.')
    if GUARD in memory:require(memory[GUARD]==0,'Octet de garde modifié.','Guard byte was modified.')
    return job,payload,{'saved_bank_port':saved,'crc16':f'{crc:04X}','capture_id':capture_id}

def receive_hex(settings:Settings,cancel,notify,factory=open_port):
    """MON EOF record is sufficient; the trailing SIO 1A byte is optional."""
    check_cancel(cancel);raw=bytearray()
    with factory(settings) as port:
        start=last=time.monotonic()
        while True:
            check_cancel(cancel)
            part=port.read(min(max(port.in_waiting,1),4096));now=time.monotonic()
            if part:
                raw.extend(part);last=now;notify(len(raw))
                require(len(raw)<=20000,'Réception trop longue.','Reception too long.')
                # A complete Intel EOF record is a protocol end, not an idle timeout.
                lines=bytes(raw).replace(b'\x1a',b'').splitlines()
                if any(line.strip().upper()==b':00000001FF' for line in lines):
                    decode_hex(bytes(raw));return bytes(raw)
                if b'\x1a' in part:
                    decode_hex(bytes(raw));return bytes(raw)
            elif now-last>(settings.idle_timeout if raw else settings.receive_timeout):
                raise RomError('Réception incomplète ou délai dépassé. Refaire W300,1400.','Incomplete reception or timeout. Repeat W300,1400.')

class DumpSession:
    def __init__(self,path):
        self.path=Path(path);self.info=json.loads((self.path/'session.json').read_text(encoding='utf-8'))
        self.model=self.info['model'];self.bank_count=self.info['bank_count'];self.tag=bytes.fromhex(self.info['tag'])
        require(self.model in MODELS and len(self.tag)==16,'Session invalide.','Invalid session.')
        self.plan=jobs(self.bank_count)
        require(self.info['required_reads'] in (1,2),'Lectures demandées invalides.','Invalid required read count.')
        # A resumed session is accepted only if its recorded local files still match.
        for key,record in self.info['blocks'].items():
            index=int(key);require(0<=index<len(self.plan),'Index de bloc invalide.','Invalid block index.')
            data=self.chunk_file(index).read_bytes()
            require(len(data)==self.plan[index].size and hashlib.sha256(data).hexdigest()==record['sha256'],
                    'Un bloc sauvegardé a été modifié.','A saved block was modified.')

    @classmethod
    def create(cls,path,model,bank_count,required_reads=2):
        require(model in MODELS,'Choisir G801 ou G805.','Choose G801 or G805.')
        jobs(bank_count);path=Path(path)
        require(not path.exists() or not any(path.iterdir()),'Choisir un dossier vide pour la nouvelle session.','Choose an empty folder for a new session.')
        require(required_reads in (1,2),'Une ou deux lectures indépendantes.','Choose one or two independent reads.')
        path.mkdir(parents=True,exist_ok=True);(path/'chunks').mkdir();(path/'captures').mkdir()
        info={'version':1,'model':model,'bank_count':bank_count,'required_reads':required_reads,'tag':uuid.uuid4().hex,
              'created_utc':datetime.now(timezone.utc).isoformat(),'blocks':{},'complete':False,'hardware_tested':False}
        (path/'session.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
        session=cls(path);session.write_agent();return session

    def extended_copy(self,bank_count,path=None):
        """Extend a local copy; preserve the original session and validated reads.

        Historical captures keep their original header bank count. The replacement
        agent uses the same nonce and starts at the first missing block.
        """
        jobs(bank_count)
        require(bank_count>self.bank_count,'Le nouveau plan doit être plus grand.','The new plan must be larger.')
        destination=Path(path) if path is not None else self.path.with_name(self.path.name+f'-{bank_count}banks-'+uuid.uuid4().hex[:6])
        require(not destination.exists(),'Le dossier de destination existe déjà.','Destination folder already exists.')
        destination.mkdir(parents=True)
        for folder in ('chunks','captures'):
            shutil.copytree(self.path/folder,destination/folder)
        info=json.loads(json.dumps(self.info))
        info['capture_bank_counts']=sorted(set(info.get('capture_bank_counts',[self.bank_count])+[bank_count]))
        info.update(bank_count=bank_count,complete=False,extended_from=str(self.path),
                    extended_utc=datetime.now(timezone.utc).isoformat())
        (destination/'session.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
        if (self.path/'report.json').exists():shutil.copy2(self.path/'report.json',destination/'previous_report.json')
        session=type(self)(destination);session.write_agent();return session

    def chunk_file(self,index):return self.path/'chunks'/f'{index:02d}.bin'
    def pending(self):
        return next((j for j in self.plan if self.info['blocks'].get(str(j.index),{}).get('reads',0)<self.info['required_reads']),None)
    def write_agent(self):
        job=self.pending();index=job.index if job else 0
        agent=make_agent(self.bank_count,self.tag,index)
        (self.path/'agent.hex').write_text(encode_hex(agent,0x100),encoding='ascii')
        return self.path/'agent.hex'
    def save(self):
        temp=self.path/'session.json.tmp'
        temp.write_text(json.dumps(self.info,indent=2)+'\n',encoding='utf-8');temp.replace(self.path/'session.json')
    def accept(self,raw):
        capture=self.path/'captures'/f'incoming-{uuid.uuid4().hex[:12]}.hex';capture.write_bytes(raw)
        job,data,details=parse_packet(raw,self.tag,self.bank_count)
        record=self.info['blocks'].get(str(job.index));digest=hashlib.sha256(data).hexdigest()
        if record:
            require(record['sha256']==digest,'Les deux lectures diffèrent : bloc conservé, refaire G103 puis W300,1400.',
                    'The two reads differ: first block retained; repeat G103 then W300,1400.')
            if details['capture_id'] not in record['capture_ids']:
                record['reads']+=1;record['capture_ids'].append(details['capture_id'])
        else:
            self.chunk_file(job.index).write_bytes(data)
            record={'sha256':digest,'reads':1,'capture_ids':[details['capture_id']],**details};self.info['blocks'][str(job.index)]=record
        self.info['complete']=self.pending() is None;self.save()
        if self.info['complete']:self.assemble()
        return job
    def assemble(self):
        require(self.pending() is None,'Session incomplète.','Session incomplete.')
        (self.path/'base.bin').write_bytes(self.chunk_file(0).read_bytes())
        fixed=b''.join(self.chunk_file(i).read_bytes() for i in range(1,5));(self.path/'fixed.bin').write_bytes(fixed)
        bankdir=self.path/'banks';bankdir.mkdir(exist_ok=True);hashes={};groups={};uniform=[]
        for bank in range(self.bank_count):
            data=b''.join(self.chunk_file(5+bank*4+p).read_bytes() for p in range(4))
            (bankdir/f'bank{bank:02x}.bin').write_bytes(data)
            digest=hashlib.sha256(data).hexdigest();hashes[f'{bank:02x}']=digest;groups.setdefault(digest,[]).append(bank)
            if len(set(data))==1:uniform.append(bank)
        same=fixed==(bankdir/'bank00.bin').read_bytes()
        # Native PUTC selects bank 04 for the font: a four-bank export is incomplete.
        g800=self.model=='PC-G801' and same and self.bank_count>=5
        if g800:
            directory=self.path/'g800';directory.mkdir(exist_ok=True)
            (directory/'base.bin').write_bytes(self.chunk_file(0).read_bytes())
            for bank in range(self.bank_count):(directory/f'rom{bank:02x}.bin').write_bytes((bankdir/f'bank{bank:02x}.bin').read_bytes())
        report={'model':self.model,'sampled_bank_selectors':self.bank_count,'required_reads':self.info['required_reads'],
                'all_blocks_verified':True,'bank_sha256':hashes,'equal_bank_groups':[g for g in groups.values() if len(g)>1],
                'uniform_banks':uniform,'fixed_matches_bank00':same,'g800_export_created':g800,
                'font_bank04_sampled':self.bank_count>=5,
                'physical_rom_size_proven':False,'contrast_command_identified':False,
                'note':'Equal/uniform banks are observations, not proof of physical ROM capacity. No LCD-port writes performed.'}
        (self.path/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        return report
