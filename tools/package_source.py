"""FR: archive autonome pour GitHub. EN: standalone GitHub source archive."""
from pathlib import Path
import argparse
import hashlib
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sharp_link import __version__
from tools.release_files import source_files
from tools.render_manual import render_all

def main():
    parser=argparse.ArgumentParser(description='Archive source FR/EN / FR/EN source archive')
    parser.add_argument('--lang',choices=('fr','en'),default='fr')
    parser.add_argument('--output',type=Path,default=ROOT.parent/'deliverables')
    args=parser.parse_args()
    render_all(ROOT)
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/f'Sharp_PC-G_Link_{__version__}_GitHub.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in source_files(ROOT):
            relative=file.relative_to(ROOT)
            archive.write(file,ROOT.name+'/'+relative.as_posix())
    with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.SHA256.txt').write_text(f'{digest}  {path.name}\n',encoding='ascii')
    print(('Archive verifiee : ' if args.lang=='fr' else 'Verified archive: ')+str(path))

if __name__=='__main__':main()
