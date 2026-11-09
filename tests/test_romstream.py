import binascii
from pathlib import Path
import tempfile
import threading
import unittest

from sharp_link.romstream import (ACK,NAK,CAN,HEADER,StreamSession,StreamJob,frame_bytes,
                                  parse_frame,profile,stream_jobs,make_stream_agent,receive_stream)
from sharp_link.romdump import RomError
from sharp_link.transport import Settings,Cancelled


def frames(session):
    for job in session.plan:
        data=bytes((i*37+job.index)&255 for i in range(job.size))
        for capture in range(1,session.info['required_reads']+1):
            yield frame_bytes(job,session.tag,session.bank_count,capture,data)
    yield frame_bytes(StreamJob(len(session.plan),255,0,0),session.tag,session.bank_count,0)


class Port:
    def __init__(self,data):self.data=bytearray(data);self.written=bytearray();self.closed=False;self.cts=True
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def read(self,count):
        result=bytes(self.data[:min(count,17)]);del self.data[:len(result)];return result
    def write(self,data):self.written.extend(data);return len(data)
    @property
    def out_waiting(self):return 0


class RomStreamTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def session(self,reads=2):return StreamSession.create(self.root/'rom','PC-G801',1,reads)
    def test_profiles_cover_all_uploader_models_and_extended_g850_banks(self):
        from sharp_link.protocol import MODELS
        for model in MODELS:
            settings=profile(model)
            self.assertEqual(settings['hardware_tested'], model == 'PC-G805')
            self.assertEqual(settings['bank_port'],0x69 if model.startswith('PC-G850') else 0x19)
        self.assertEqual(len(stream_jobs(32,0x69)),1057)
        self.assertEqual(stream_jobs(32,0x69)[-1],StreamJob(1056,31,0xfe00,512))
        with self.assertRaises(RomError):stream_jobs(17)
    def test_agent_configuration_and_8kb_memory_budget(self):
        data=make_stream_agent(32,bytes(16),0x69,start=1056)
        self.assertLessEqual(len(data),0x700)
        for count,port in ((0,0x19),(33,0x69),(17,0x19)):
            with self.assertRaises(RomError):make_stream_agent(count,bytes(16),port)
    def test_crc_covers_header_and_every_payload_byte(self):
        s=self.session();raw=next(frames(s))
        for index in range(len(raw)):
            bad=bytearray(raw);bad[index]^=1
            with self.assertRaises(RomError):parse_frame(bad,s.tag,s.plan,1,2)
    def test_foreign_session_and_missing_end_are_rejected(self):
        s=self.session();raw=frame_bytes(s.plan[0],bytes(16),1,1,bytes(64))
        with self.assertRaises(RomError):s.accept(raw)
        with self.assertRaises(RomError):s.accept(frame_bytes(StreamJob(len(s.plan),255,0,0),s.tag,1,0))
        self.assertFalse(s.info['complete'])
    def test_duplicate_ack_retry_is_not_an_independent_read(self):
        s=self.session();raw=next(frames(s));s.accept(raw);s.accept(raw)
        self.assertEqual(s.info['blocks']['0']['reads'],1)
        s.accept(frame_bytes(s.plan[0],s.tag,1,2,raw[HEADER.size:HEADER.size+64]))
        self.assertEqual(s.info['blocks']['0']['reads'],2)
    def test_conflicting_read_preserves_accepted_chunk_and_capture(self):
        s=self.session();raw=next(frames(s));s.accept(raw)
        before=(s.path/'captures/0000-r1.prd').read_bytes()
        with self.assertRaises(RomError):s.accept(frame_bytes(s.plan[0],s.tag,1,1,bytes(64)))
        self.assertEqual((s.path/'captures/0000-r1.prd').read_bytes(),before)
        self.assertEqual(s.chunk_file(0).read_bytes(),raw[HEADER.size:HEADER.size+64])
    def test_resume_checks_hashes_and_resumes_first_missing_block(self):
        s=self.session();raws=iter(frames(s));s.accept(next(raws));s.accept(next(raws))
        resumed=StreamSession(s.path);self.assertEqual(resumed.pending().index,1)
        resumed.chunk_file(0).write_bytes(bytes(64))
        with self.assertRaises(RomError):StreamSession(s.path)
    def test_one_receiver_session_saves_all_frames_and_requires_explicit_end(self):
        s=self.session();wire=b''.join(frames(s));p=Port(wire);events=[]
        result=receive_stream(Settings('fake',baud=4800,data_bits=8),threading.Event(),lambda *args:events.append(args),s,factory=lambda _:p)
        self.assertEqual(result,s.path);self.assertTrue(p.closed);self.assertTrue(s.info['complete'])
        self.assertEqual(bytes(p.written),bytes([ACK])*(len(s.plan)*2+1))
        self.assertEqual((s.path/'banks/bank00.bin').stat().st_size,16384)
        self.assertEqual(events[-1][0],'complete')
    def test_bad_crc_is_naked_and_identical_retransmission_accepted(self):
        for index in (0,12,22,24,28,-1):
            with self.subTest(corrupted_byte=index):
                s=StreamSession.create(self.root/f'rom{index}','PC-G801',1)
                wire=list(frames(s));bad=bytearray(wire[0]);bad[index]^=1
                p=Port(bytes(bad)+b''.join(wire))
                receive_stream(Settings('fake',baud=4800,data_bits=8),threading.Event(),lambda *args:None,s,factory=lambda _:p)
                self.assertEqual(p.written[0],NAK);self.assertTrue(s.info['complete'])
                self.assertEqual(s.info['blocks']['0']['reads'],2)
    def test_cancel_does_not_open_hardware(self):
        s=self.session();cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):receive_stream(Settings('fake',baud=4800,data_bits=8),cancel,lambda *args:None,s,factory=lambda _:self.fail('opened'))
    def test_truncated_stream_never_produces_a_complete_report(self):
        s=self.session();wire=list(frames(s));p=Port(b''.join(wire[:-1]))
        with self.assertRaises(RomError):
            receive_stream(Settings('fake',baud=4800,data_bits=8,idle_timeout=0.002),threading.Event(),lambda *args:None,s,factory=lambda _:p)
        self.assertIsNone(s.pending());self.assertFalse(s.info['complete'])
        self.assertFalse((s.path/'report.json').exists());self.assertTrue(p.closed)


if __name__=='__main__':unittest.main()
