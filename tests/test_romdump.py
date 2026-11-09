import binascii
import json
from pathlib import Path
import tempfile
import threading
import unittest

from sharp_link.protocol import prepare
from sharp_link.romdump import (BUFFER, GUARD, HEADER, PACKET, DumpSession, RomError,
                               decode_hex, encode_hex, jobs, make_agent, parse_packet, receive_hex)
from sharp_link.transport import Cancelled, Settings

TAG=bytes(range(16))

def packet(job,tag=TAG,banks=4,capture=1,payload=None,guard=False):
    if payload is None:payload=bytes((job.index*31+i)&255 for i in range(job.size))
    data=bytearray(GUARD-PACKET+int(guard))
    data[:32]=HEADER.pack(b'PRD1',tag,job.index,job.bank,0x21,capture,job.source,job.size,
                          binascii.crc_hqx(payload,0xffff),banks,0x5a)
    data[256:256+len(payload)]=payload
    return encode_hex(data,PACKET).encode('ascii')

class RomDumpTests(unittest.TestCase):
    def test_plans_include_ram_vectors_fixed_window_and_all_bank_pages(self):
        self.assertEqual(len(jobs(4)),21);self.assertEqual(len(jobs(16)),69)
        self.assertEqual((jobs(4)[0].source,jobs(4)[0].size),(0,64))
        self.assertEqual((jobs(16)[-1].bank,jobs(16)[-1].source),(15,0xf000))
        for count in (0,17):
            with self.assertRaises(RomError):jobs(count)

    def test_agent_config_is_bound_to_session_and_resumes_at_requested_job(self):
        agent=make_agent(4,TAG,7)
        self.assertEqual(agent[0x1e8],4);self.assertEqual(agent[0x1e9:0x1f9],TAG)
        prepared=prepare(encode_hex(agent,0x100),mode='hex',model='PC-G801')
        self.assertEqual(prepared.data_bytes,544)
        with self.assertRaises(RomError):make_agent(4,TAG[:8])

    def test_packet_accepts_both_monitor_endpoint_conventions_and_all_byte_values(self):
        for guard in (False,True):
            raw=packet(jobs(4)[8],guard=guard)
            job,data,details=parse_packet(raw,TAG,4)
            self.assertEqual(job.index,8);self.assertEqual(len(set(data)),256)
            self.assertEqual(details['capture_id'],1)

    def test_wrong_session_bank_count_and_missing_byte_are_rejected(self):
        raw=packet(jobs(4)[0])
        for tag,count in ((bytes(16),4),(TAG,3)):
            with self.assertRaises(RomError):parse_packet(raw,tag,count)
        memory=decode_hex(raw);del memory[0x450]
        broken=b''.join((encode_hex(bytes([value]),address).split(':00000001FF')[0]).encode() for address,value in memory.items())+b':00000001FF\n'
        with self.assertRaises(RomError):parse_packet(broken,TAG,4)

    def test_hex_overlap_checksum_truncation_and_trailing_records_are_rejected(self):
        raw=packet(jobs(4)[1])
        for bad in (raw[:-15],raw.replace(b':',b';',1),raw+raw,raw[:40]+b'0'+raw[41:]):
            with self.assertRaises(RomError):decode_hex(bad)

    def test_internal_crc_detects_corruption_even_with_valid_hex_checksums(self):
        memory=decode_hex(packet(jobs(4)[1]));memory[BUFFER]^=1
        raw=encode_hex(bytes(memory[a] for a in range(PACKET,GUARD)),PACKET).encode()
        with self.assertRaises(RomError):parse_packet(raw,TAG,4)

    def test_rereceiving_same_copy_does_not_count_as_independent_read(self):
        with tempfile.TemporaryDirectory() as folder:
            session=DumpSession.create(Path(folder)/'rom','PC-G801',4)
            raw=packet(jobs(4)[0],tag=session.tag)
            session.accept(raw);session.accept(raw)
            self.assertEqual(session.info['blocks']['0']['reads'],1)
            session.accept(packet(jobs(4)[0],tag=session.tag,capture=2))
            self.assertEqual(session.info['blocks']['0']['reads'],2)

    def test_mismatched_second_read_never_replaces_first(self):
        with tempfile.TemporaryDirectory() as folder:
            session=DumpSession.create(Path(folder)/'rom','PC-G801',4)
            session.accept(packet(jobs(4)[0],tag=session.tag))
            first=session.chunk_file(0).read_bytes()
            with self.assertRaises(RomError):session.accept(packet(jobs(4)[0],tag=session.tag,capture=2,payload=bytes(64)))
            self.assertEqual(session.chunk_file(0).read_bytes(),first)

    def test_resume_checks_saved_hashes_and_never_reuses_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'rom';session=DumpSession.create(path,'PC-G801',4,1)
            session.accept(packet(jobs(4)[0],tag=session.tag))
            restored=DumpSession(path);self.assertEqual(restored.pending().index,1)
            with self.assertRaises(RomError):DumpSession.create(path,'PC-G801',4)
            restored.chunk_file(0).write_bytes(bytes(64))
            with self.assertRaises(RomError):DumpSession(path)

    def test_complete_dump_reconstructs_banks_and_reports_aliases_without_capacity_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            session=DumpSession.create(Path(folder)/'rom','PC-G801',5,1)
            for job in session.plan:
                payload=bytes([job.source>>12])*job.size
                # Fixed 8000 pages match bank00's C000 pages in this synthetic ROM.
                if 1<=job.index<=4:payload=bytes([(job.source+0x4000)>>12])*job.size
                session.accept(packet(job,tag=session.tag,banks=session.bank_count,payload=payload))
            self.assertTrue(session.info['complete'])
            report=json.loads((session.path/'report.json').read_text())
            self.assertTrue(report['g800_export_created']);self.assertFalse(report['physical_rom_size_proven'])
            self.assertEqual(len(report['equal_bank_groups'][0]),5)
            self.assertEqual((session.path/'base.bin').stat().st_size,64)
            self.assertEqual((session.path/'g800/rom03.bin').stat().st_size,16384)
            self.assertEqual((session.path/'g800/rom04.bin').stat().st_size,16384)

    def test_wrong_model_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for model,count in (('PC-G850',16),('PC-G801',0),('PC-G801',17)):
                with self.assertRaises(RomError):DumpSession.create(Path(folder)/'bad',model,count)

    def test_extend_old_g801_dump_preserves_original_and_all_validated_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            original=DumpSession.create(Path(folder)/'old','PC-G801',4,2)
            for job in original.plan:
                for capture in (1,2):original.accept(packet(job,tag=original.tag,capture=capture))
            before=(original.path/'session.json').read_bytes()
            upgraded=original.extended_copy(5,Path(folder)/'extended')
            self.assertEqual((original.path/'session.json').read_bytes(),before)
            self.assertTrue(DumpSession(original.path).info['complete'])
            self.assertEqual(upgraded.pending().index,21)
            self.assertEqual(upgraded.info['capture_bank_counts'],[4,5])
            self.assertEqual(upgraded.tag,original.tag)
            self.assertEqual(upgraded.info['blocks'],original.info['blocks'])
            self.assertEqual(len(list((upgraded.path/'captures').glob('*.hex'))),42)
            self.assertFalse((original.path/'g800').exists())
            self.assertFalse((upgraded.path/'g800').exists())
            for job in upgraded.plan[21:]:
                for capture in (1,2):upgraded.accept(packet(job,tag=upgraded.tag,banks=5,capture=capture))
            self.assertTrue(DumpSession(upgraded.path).info['complete'])
            self.assertEqual((upgraded.path/'banks/bank04.bin').stat().st_size,16384)
            self.assertEqual(make_agent(5,upgraded.tag,21)[0x1e8],5)

    def test_stream_receiver_accepts_hex_eof_without_sio_1a_and_closes_port(self):
        raw=packet(jobs(4)[0])
        class Port:
            def __init__(self):self.data=bytearray(raw);self.closed=False
            def __enter__(self):return self
            def __exit__(self,*args):self.closed=True
            @property
            def in_waiting(self):return min(len(self.data),53)
            def read(self,count):chunk=bytes(self.data[:count]);del self.data[:count];return chunk
        port=Port();result=receive_hex(Settings('fake'),threading.Event(),lambda count:None,factory=lambda settings:port)
        self.assertTrue(port.closed);self.assertEqual(decode_hex(result),decode_hex(raw))

    def test_cancel_before_receive_does_not_open_serial(self):
        event=threading.Event();event.set()
        with self.assertRaises(Cancelled):receive_hex(Settings('fake'),event,lambda count:None,factory=lambda _:self.fail('opened port'))

if __name__=='__main__':unittest.main()
