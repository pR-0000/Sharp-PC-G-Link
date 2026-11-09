"""Release boundaries and offline documentation navigation."""
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from tools.release_files import is_public_file, source_files
from tools.render_manual import render_all

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.anchors = [], set()
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if 'id' in attributes:
            self.anchors.add(attributes['id'])
        if tag == 'a' and 'href' in attributes:
            self.links.append(attributes['href'])


class PublicationTests(unittest.TestCase):
    def test_private_files_and_reports_are_excluded_but_agents_remain(self):
        for name in ('sharp_pc_g_link.ini', 'sharp_pc_g_link.ini.tmp',
                     '.venv/Lib/serial.py', 'rom-dumps/backup/bank00.bin',
                     'docs/VALIDATION.md', 'docs/ROM_G801_VALIDATION.html',
                     'romdump/hardware_validation.json', 'romdump/build/cpu_validation.json',
                     'romdump/build/stream_cpu_validation.json', 'romdump/build/rom_stream.lst',
                     'build/Sharp PC-G Link.spec', 'dist/Sharp PC-G Link.exe'):
            with self.subTest(name=name):
                self.assertFalse(is_public_file(Path(name)))
        for name in ('README.md', 'romdump/build/rom_stream.bin',
                     'romdump/build/stream_manifest.json', 'sharp_link/defaults.ini'):
            self.assertTrue(is_public_file(Path(name)), name)

    def test_bilingual_readme_has_valid_language_anchors_and_no_stale_links(self):
        text = (ROOT/'README.md').read_text(encoding='utf-8')
        self.assertLess(text.index('id="francais"'), text.index('id="english"'))
        self.assertIn('[English](#english)', text)
        self.assertFalse((ROOT/'README_EN.md').exists())
        for path in source_files(ROOT):
            if path.suffix == '.md':
                for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                    parsed = urlsplit(link)
                    if not parsed.scheme:
                        target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
                        self.assertTrue(target.exists(), f'{path}: {link}')
                        if parsed.fragment:
                            self.assertIn(f'id="{parsed.fragment}"', target.read_text(encoding='utf-8'))

    def test_offline_manual_preserves_anchors_and_relocates_english_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'docs').mkdir()
            (root/'romdump').mkdir()
            (root/'README.md').write_text(
                '[English](#english)\n\n<a id="english"></a>\n\n## English\n\n'
                '[Guide](docs/GUIDE_EN.md)\n', encoding='utf-8')
            (root/'NOTICE.md').write_text('# Notices\n', encoding='utf-8')
            (root/'docs/GUIDE_EN.md').write_text('[Home](../README.md#english)\n', encoding='utf-8')
            render_all(root)
            manual = Links((root/'docs/README.html').read_text(encoding='utf-8'))
            self.assertIn('english', manual.anchors)
            self.assertIn('#english', manual.links)
            self.assertIn('GUIDE_EN.html', manual.links)
            guide = Links((root/'docs/GUIDE_EN.html').read_text(encoding='utf-8'))
            self.assertIn('README.html#english', guide.links)

    def test_help_opens_matching_section_of_the_single_manual(self):
        from sharp_link.gui import LinkApp, resources
        class App:
            language = 'en'
        app = App()
        with patch('sharp_link.gui.webbrowser.open') as browser:
            LinkApp.open_manual(app)
            browser.assert_called_once_with((resources()/'docs/README.html').as_uri()+'#english')
            app.language = 'fr'
            LinkApp.open_manual(app)
            self.assertTrue(browser.call_args.args[0].endswith('/docs/README.html#francais'))
