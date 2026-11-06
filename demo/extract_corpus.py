"""Verify and extract the bundled, unmodified Markdown 3.9 source distribution."""
import argparse
import hashlib
from pathlib import Path
import tarfile

EXPECTED = 'd2900fe1782bd33bdbbd56859defef70c2e78fc46668f8eb9df3128138f2cb6a'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='new parent directory')
args = parser.parse_args()
archive = Path(__file__).resolve().parents[1] / 'corpus/markdown-3.9.tar.gz'
if hashlib.sha256(archive.read_bytes()).hexdigest() != EXPECTED:
    raise SystemExit('Bundled corpus archive hash mismatch')
args.output.mkdir(parents=True, exist_ok=False)
with tarfile.open(archive, 'r:gz') as source:
    if any(Path(member.name).parts[0] != 'markdown-3.9' for member in source.getmembers()):
        raise SystemExit('Unexpected archive root')
    source.extractall(args.output, filter='data')
print((args.output / 'markdown-3.9').absolute())
